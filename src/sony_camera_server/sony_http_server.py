#!/usr/bin/env python3

"""Utilities for creating a Sony based network camera."""

# pylint: disable=invalid-name, line-too-long

import os.path
import urllib
import json
import time
import sys
import argparse
import http
import http.server
import threading
import queue
import logging

from . import ssdp
from . import device_cache
from . import sony_imgdev
from . import sony_streams


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
        if not self.server.liveview_available():
            self.send_header("Retry-After", 120)
            self.send_response(http.HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if not streamer.activate():
            self.send_header("Retry-After", 120)
            self.send_response(http.HTTPStatus.TOO_MANY_REQUESTS)
            return

        ctype = f"multipart/x-mixed-replace;boundary={self.MJPEG_BOUNDS}"
        caching = ", ".join(["no-store", "no-cache", "must-revalidate",
                             "pre-check=0", "post-check=0", "max-age=0"])
        self.send_response(http.HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", caching)
        self.send_header("Pragma", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        now = then = time.time()
        while True:
            try:
                img = streamer.get_frame()
                self.wfile.write(f"--{self.MJPEG_BOUNDS}\r\n".encode())
                self.send_header("Content-type", "image/jpeg")
                self.send_header("Cache-Control", caching)
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
            except (KeyboardInterrupt, queue.Empty):
                self.wfile.write(f"--{self.MJPEG_BOUNDS}--\r\n".encode())
                break
            except BrokenPipeError:
                break
        streamer.deactivate()

    def _forward_device_file(self):
        """Download and forward files from the Sony imaging device."""
        # TODO: Should create separate URLs for RAW/JPEG, etc...
        dev = self.server.active_device
        if not dev:
            self.send_response(http.HTTPStatus.SERVICE_UNAVAILABLE)
            return
        for _, f in sony_imgdev.sony_media_walk(dev, "flat"):
            if f["uri"] == os.path.basename(self.path):
                url = f["content"]["original"][0]["url"]
                try:
                    with urllib.request.urlopen(url) as req:
                        data = req.read()
                except (urllib.error.HTTPError, urllib.error.URLError):
                    self.send_response(http.HTTPStatus.SERVICE_UNAVAILABLE)
                    return
                self.send_response(http.HTTPStatus.OK)
                self.send_header("Content-type", self._mime_type(f))
                self.end_headers()
                self.wfile.write(data)

    def _mime_type(self, fil):
        """Attempt to find the mime-type of the Sony file descriptor."""
        if fil["contentKind"] == "still":
            obj = fil["content"]["original"][0]["stillObject"]
            if obj == "jpeg":
                return "image/jpeg"
            elif obj == "raw":
                # TODO: Could also be image/x-sony-sr2 or image/x-sony-srf
                # depending on camera...
                return "image/x-sony-arw"
        elif fil["contentKind"].startswith("movie"):
            return "video/mp4"

    def do_GET(self):
        """Handle the HTTP GET request."""
        if self.path.endswith("liveview.mjpg"):
            self._mjpeg_request()
        elif (self.path.startswith("/image:content") or
              self.path.startswith("/video:content") or
              self.path.startswith("/audio:content")):
            self._forward_device_file()
        else:
            try:
                super().do_GET()
            except BrokenPipeError:
                pass

    def _send_post_response(self, result):
        try:
            data = json.dumps(result).encode()
        except OSError:
            logging.warning(f"Failed to JSON encode: {result}")
            self.send_response(http.HTTPStatus.BAD_GATEWAY)
            return
        self.send_response(http.HTTPStatus.OK)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:
            pass

    def do_POST(self):
        """Handle the HTTP POST request."""
        content_length = int(self.headers['Content-Length'])
        args = json.loads(self.rfile.read(content_length).decode())
        ep = os.path.basename(self.path)
        if ep == "server":
            result = self.server._server(args)
            self._send_post_response(result)
        elif self.server.is_accessible_endpoint(ep):
            result = self.server._method(ep, args)
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
        self.discover = ssdp.SSDPDiscoverer(ssdp.SONY_SERVICE_TYPE)
        self.cache = device_cache.DeviceCache()
        self.devices = []
        self.active_device = None
        self.liveview = None
        self.status = None
        self._find_devices()
        if len(self.devices) >= 1:
            self._change_device(self.devices[0].device_name)

    def is_accessible_endpoint(self, ep):
        """Check if `ep` is an accessible endpoint."""
        if self.active_device:
            return ep in self.active_device.endpoints
        else:
            return False

    def _server(self, params):
        method = params.get("method", "")
        if method == "getDevices":
            devs = [d.device_name for d in self.devices]
            return {"error": [0, "Ok"], "result": devs}
        elif method == "refreshDevices":
            devs = [d.device_name for d in self._find_devices()]
            return {"error": [0, "Ok"], "result": devs}
        elif method == "changeDevice":
            dev = params.get("params", [{}])[0].get("device", "")
            res = self._change_device(dev)
            return {"error": [0, "Ok"], "result": res}
        elif method == "getEndpoints":
            if not self.active_device:
                return {"error": [404, "No Device Connected"]}
            eps = self.active_device.endpoints
            return {"error": [0, "Ok"], "result": eps}

    def _method(self, endpoint, params):
        if not self.active_device:
            return {"error": [404, "No Device Connected"]}
        method = params.pop("method", "")
        if not method:
            return {"error": [501, "Not implemented"]}
        ep = getattr(self.active_device, endpoint)
        method = getattr(ep, method)
        return method(**params)

    def _start_liveview(self):
        """Ask the server to start the liveview."""
        if not self.active_device:
            return False
        res = self.active_device.camera.startLiveview()
        callback = self.streamer.add_frame
        if "result" in res:
            url = res["result"][0]
            self._stop_liveview()
            self.liveview = sony_streams.LiveviewStreamThread(url, callback)
            self.liveview.start()

    def _stop_liveview(self):
        """Stop the liveview."""
        if self.active_device and self.liveview:
            self.liveview.exit()
            self.liveview.join()

    def _find_devices(self):
        self.devices = self.cache.scan_devices(self.discover)
        return self.devices

    def _update_status(self):
        """Attempt to update device status."""
        if not self.active_device:
            return False
        dev = self.active_device
        res = dev.camera.getEvent(params=[False])
        if "result" in res:
            self.status = res["result"]
            return True
        else:
            return False

    def _change_device(self, dev):
        """Attempt to change the active device."""
        new_dev = None
        for d in self.devices:
            if dev != d.device_name:
                continue
            new_dev = d
        # Only change active device if it is different from the active one.
        cur_dev_name = ""
        if self.active_device:
            cur_dev_name = self.active_device.device_name
        if new_dev and new_dev.device_name != cur_dev_name:
            logging.info(f"Changing devices {cur_dev_name} -> {new_dev}")
            self.active_device = new_dev
            self._update_status()
            self._start_liveview()

    def liveview_available(self):
        """Check if the liveview is available."""
        if not self._update_status():
            return False
        self.active_device.camera.startLiveview()
        return self.status[3]["liveviewStatus"]


def start_mjpeg_stream(bind, port, liveview_threads, liveview_fps):
    """Start running a MJPEG Streamer."""
    try:
        streamer = MJPEGStreamer(max_threads=liveview_threads, fps=liveview_fps)
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
    parser.add_argument("-v", "--verbosity", metavar="N", type=int,
                        default=logging.WARNING,
                        choices=range(logging.NOTSET, logging.CRITICAL),
                        help="Set logging verbosity level.")
    parser.add_argument("-f", "--liveview-fps", metavar="FPS", type=float,
                        default=15.0,
                        help="Target FPS for the liveview stream.")
    parser.add_argument("-t", "--liveview-threads", metavar="N", type=int,
                        default=4,
                        help="Number of allowed streamer threads at once.")
    return parser.parse_args(argv)


def run():
    """Run the application."""
    ARGS = parse_arguments(sys.argv[1:])
    logging.basicConfig(level=ARGS.verbosity)
    return start_mjpeg_stream(ARGS.bind, ARGS.port,
                              ARGS.liveview_threads, ARGS.liveview_fps)


if __name__ == '__main__':
    sys.exit(run())
