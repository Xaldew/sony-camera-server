#!/usr/bin/env python3

"""Utilities for creating a Sony based network camera."""

# pylint: disable=invalid-name, line-too-long

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


class SonyRequestHandler(http.server.BaseHTTPRequestHandler):
    """Handler for a HTTP Request for a Sony device."""

    MJPEG_BOUNDS = "--boundarydonotcross"

    def __str__(self):
        return "SonyMJPGStreamer"

    def _root_request(self):
        """Prepare a simple HTML root page with an image tag."""
        bind, port = self.server.server_address
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<!DOCTYPE html>")
        self.wfile.write(b"<html><head></head><body>")
        msg = f"<img src={bind}:{port}/liveview.mjpg />"
        self.wfile.write(msg.encode())
        self.wfile.write(b"</body></html>")

    def _mjpeg_request(self):
        """Handle a MJPEG request.

        The client requests the liveview: Activate a queue to dynamically update
        the image tag.

        """
        if not self.server.activate():
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
                img = self.server.get_frame()
                self.wfile.write(f"--{self.MJPEG_BOUNDS}\r\n".encode())
                self.send_header("Content-type", "image/jpeg")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0")
                self.send_header("Content-length", str(len(img)))
                self.send_header("X-Timestamp", now)
                self.end_headers()
                self.wfile.write(img)
                now = time.time()
                dt = now - then
                sec_per_frame = 1.0 / self.server.fps
                if dt < sec_per_frame:
                    self.server.deactivate()
                    now = time.time()
                    dt = now - then
                    time.sleep(max(0, sec_per_frame - dt))
                    if not self.server.activate():
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
        self.server.deactivate()

    def do_GET(self):
        """Handle the HTTP GET request."""
        if (self.path.endswith("index.html") or self.path == "/"):
            self._root_request()
        elif self.path.endswith("liveview.mjpg"):
            self._mjpeg_request()
        elif self.path.endswith("favicon.ico"):
            self.send_response(404)

    # def do_POST(self):
    #     """Handle the HTTP POST request."""


class SonyMJPGStreamer(http.server.ThreadingHTTPServer):
    """Sony Motion JPEG Streamer server."""

    def __init__(self,
                 server_address, RequestHandlerClass,
                 max_threads=2,
                 fps=60):
        super().__init__(server_address, RequestHandlerClass)
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


def start_mjpeg_stream(bind, port):
    """Start running a MJPEG Streamer."""
    try:
        server = SonyMJPGStreamer((bind, port), SonyRequestHandler)
        SONY_SERVICE_TYPE = "urn:schemas-sony-com:service:ScalarWebAPI:1"
        disc = ssdp.SSDPDiscoverer(SONY_SERVICE_TYPE)
        dev = sony_imgdev.create_sony_imaging_device(disc)
        res = dev.camera.startLiveview()
        url = res.get("result", {})[0]
        lv = sony_streams.LiveviewStreamThread(url, server.add_frame)
        lv.start()

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
    kdesc = "Local Motion JPEG streaming for the Sony Imaging Device."
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
