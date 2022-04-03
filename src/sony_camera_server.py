#!/usr/bin/env python3

"""Utilities for creating a Sony based network camera."""

# pylint: disable=invalid-name, line-too-long

import os.path
import json
import time
import sys
import argparse
import http
import http.server
import threading
import queue

import ssdp
import sony_imgdev
import sony_streams


SONY_SERVICE_TYPE = "urn:schemas-sony-com:service:ScalarWebAPI:1"


class SonyRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Handler for a HTTP Request for a Sony device."""

    MJPEG_BOUNDS = "--boundarydonotcross"

    def __init__(self, *args, **kwargs):
        """Initialize the HTML Request handler."""
        parent = os.path.dirname(os.path.abspath(__file__))
        directory = os.path.join(parent, 'res')
        super().__init__(*args, directory=directory, **kwargs)

    def _mjpeg_request(self):
        """Handle a MJPEG request.

        The client requests the liveview, activate a queue to update the image
        tag.

        """
        streamer = self.server.streamer
        if not streamer.activate():
            self.send_response(http.HTTPStatus.TOO_MANY_REQUESTS)
            return

        self.send_response(http.HTTPStatus.OK)
        self.send_header("Content-Type", f"multipart/x-mixed-replace;boundary={self.MJPEG_BOUNDS}")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        now = then = time.time()
        while True:
            try:
                img = streamer.get_frame()
                self.wfile.write(f"--{self.MJPEG_BOUNDS}\r\n".encode())
                self.send_header("Content-type", "image/jpeg")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0")
                self.send_header("Content-length", str(len(img)))
                self.send_header("X-Timestamp", now)
                self.end_headers()
                self.wfile.write(img)
                now = time.time()
                dt = now - then
                sec_per_frame = 1.0 / streamer.fps
                if dt < sec_per_frame:
                    streamer.deactivate()
                    now = time.time()
                    dt = now - then
                    time.sleep(max(0, sec_per_frame - dt))
                    if not streamer.activate():
                        break
                    now = time.time()
                dt = now - then
                then = now
                # print(f"Frametime: {dt:8.5} s ({1.0/dt:5.1f} fps)", end="\r")
            except KeyboardInterrupt:
                self.wfile.write(f"--{self.MJPEG_BOUNDS}--\r\n".encode())
                break
            except BrokenPipeError:
                break
        streamer.deactivate()

    def do_GET(self):
        """Handle the HTTP GET request."""
        if self.path.endswith("liveview.mjpg"):
            self._mjpeg_request()
        else:
            try:
                super().do_GET()
            except BrokenPipeError:
                pass

    def _send_post_response(self, result):
        self.send_response(http.HTTPStatus.OK)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        try:
            self.wfile.write(json.dumps(result).encode())
        except BrokenPipeError:
            pass

    def do_POST(self):
        """Handle the HTTP POST request."""
        content_length = int(self.headers['Content-Length'])
        args = json.loads(self.rfile.read(content_length).decode())
        if self.path.endswith("server"):
            result = self.server._server(args)
            self._send_post_response(result)
        elif self.path.endswith("guide"):
            result = self.server._guide(args)
            self._send_post_response(result)
        elif self.path.endswith("camera"):
            result = self.server._camera(args)
            self._send_post_response(result)
        elif self.path.endswith("system"):
            result = self.server._system(args)
            self._send_post_response(result)
        elif self.path.endswith("avContent"):
            result = self.server._avContent(args)
            self._send_post_response(result)
        else:
            self.send_response(http.HTTPStatus.NOT_IMPLEMENTED)


class MJPEGStreamer:
    """Motion JPEG stream manager."""

    def __init__(self, max_threads=4, fps=30):
        """Construct a new MJPEG streamer.

        .. Keyword Arguments:
        :param max_threads: Maximum number of threads. (default 4)
        :param fps: Frame rate to aim for each client. (default 30)

        """
        self.fps = fps
        self.act_threads = 0
        self.max_threads = max_threads
        self.thread_map = {}
        self.queues = [queue.Queue() for _ in range(self.max_threads)]
        self.enabled = [False for _ in range(self.max_threads)]

    def _next_idx(self):
        """Retrieve the next free thread index."""
        for idx, active in enumerate(self.enabled):
            if not active:
                return idx
        return -1

    def activate(self):
        """Activate the queues associated with the calling thread."""
        tid = threading.get_ident()
        idx = self._next_idx()
        if idx < 0:
            return False
        self.thread_map[tid] = idx
        self.act_threads += 1
        self.enabled[idx] = True
        return True

    def get_frame(self):
        """Retrieve a frame for the currently active thread."""
        tid = threading.get_ident()
        idx = self.thread_map[tid]
        if idx < 0:
            return bytes()
        # TODO: Add a large timeout based on FPS to handle crashed streams.
        return self.queues[idx].get()

    def deactivate(self):
        """Deactivate the queues associated with the calling thread."""
        tid = threading.get_ident()
        idx = self.thread_map[tid]
        if idx < 0:
            return
        self.enabled[idx] = False
        with self.queues[idx].mutex:
            self.queues[idx].queue.clear()
        self.act_threads -= 1

    def add_frame(self, frame):
        """Add a frame to the streamer."""
        for active, lifo in zip(self.enabled, self.queues):
            if active:
                lifo.put(frame)


class SonyCameraServer(http.server.ThreadingHTTPServer):
    """Sony camera server."""

    def __init__(self, server_address, RequestHandlerClass, streamer):
        """Create a new Sony network camera server."""
        super().__init__(server_address, RequestHandlerClass)
        self.streamer = streamer
        self.discover = ssdp.SSDPDiscoverer(SONY_SERVICE_TYPE)
        self.devices = self._find_devices()
        self.active_device = None
        self.liveview = None
        if len(self.devices) == 1:
            self.active_device = self.devices[0]
            self._start_liveview()

    def _server(self, params):
        if not self.active_device:
            return {"error": [404, "No Device Connected"]}
        method = params.get("method", "")
        if method == "getDevices":
            devs = [d.device_name for d in self.devices]
            return {"error": [0, "Ok"], "result": devs}
        elif method == "refreshDevices":
            devs = [d.device_name for d in self._find_devices()]
            return {"error": [0, "Ok"], "result": devs}

    def _system(self, params):
        return self._method(self.active_device.system, params)

    def _guide(self, params):
        return self._method(self.active_device.guide, params)

    def _camera(self, params):
        return self._method(self.active_device.camera, params)

    def _avContent(self, params):
        return self._method(self.active_device.avContent, params)

    def _method(self, endpoint, params):
        if not self.active_device:
            return {"error": [404, "No Device Connected"]}
        method = params.pop("method", "")
        if not method:
            return {"error": [501, "Not implemented"]}
        method = getattr(endpoint, method)
        return method(**params)

    def _start_liveview(self):
        res = self.active_device.camera.startLiveview()
        callback = self.streamer.add_frame
        if "result" in res:
            url = res["result"][0]
            self._stop_liveview()
            self.liveview = sony_streams.LiveviewStreamThread(url, callback)
            self.liveview.start()

    def _stop_liveview(self):
        if self.active_device and self.liveview:
            self.liveview.exit()
            self.liveview.join()

    def _find_devices(self):
        devices = list()
        for rsp in self.discover.query():
            if ("SonyImagingDevice" in rsp.get("server", "") and
                    "location" in rsp):
                dev = sony_imgdev.SonyImagingDevice(rsp["location"])
                devices.append(dev)
        return devices


def start_mjpeg_stream(bind, port):
    """Start running a MJPEG Streamer."""
    try:
        streamer = MJPEGStreamer()
        server = SonyCameraServer((bind, port), SonyRequestHandler, streamer)
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 0


def parse_arguments(argv):
    """Parse the given argument vector.

    .. Keyword Arguments:
    :param argv: The arguments to be parsed.

    .. Types:
    :type argv: A list of strings.

    .. Returns:
    :returns: The parsed arguments.
    :rtype: A argparse namespace object.

    """
    fmtr = argparse.RawDescriptionHelpFormatter
    kdesc = "Web Server for controlling a Sony Imaging Device."
    parser = argparse.ArgumentParser(description=kdesc, formatter_class=fmtr)
    parser.add_argument("-p", "--port", metavar="N", type=int,
                        default=8080,
                        help="The host webserver port.")
    parser.add_argument("-b", "--bind", metavar="IP",
                        default="localhost",
                        help="Network interface to bind to.")

    return parser.parse_args(argv)


if __name__ == '__main__':
    ARGS = parse_arguments(sys.argv[1:])
    sys.exit(start_mjpeg_stream(ARGS.bind, ARGS.port))
