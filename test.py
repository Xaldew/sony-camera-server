#!/usr/bin/env python

"""Testing..."""

import sys
import time
import socket

from src import ssdp
from src import sony_imgdev
from src import sony_streams


class JPEGWriter:
    """Simple JPEG frame dumper."""

    def __init__(self, fmt="frame_%02d.jpeg"):
        self.cnt = 0
        self.fmt = fmt

    def __str__(self):
        return "JPEGWriter"

    def __call__(self, jpeg_img):
        with open(self.fmt % self.cnt, "wb") as file:
            file.write(jpeg_img)
        self.cnt += 1


SONY_SERVICE_TYPE = "urn:schemas-sony-com:service:ScalarWebAPI:1"

def main():
    """Shut it."""
    disc = ssdp.SSDPDiscoverer(SONY_SERVICE_TYPE)
    dev = sony_imgdev.create_sony_imaging_device(disc)
    print(dev)
    print(dev.guide.getVersions())
    print(dev.guide.getVersions())
    # res = dev.camera.startLiveview()
    # url = res.get("result", {})[0]
    # lv = sony_streams.LiveviewStreamThread(url, JPEGWriter())
    # lv.start()
    try:
        while True:
            time.sleep(100)
    except (KeyboardInterrupt, SystemExit):
        pass

    # print(dev.avContent.getContentCount())
    # print(dev.camera.setShootMode(params=["still"]))
    # while True:
    #     res = dev.camera.getEvent(params=[False])
    #     cam_status = res.get("result", {})[1].get("cameraStatus")
    #     if cam_status == "IDLE":
    #         break
    #     print(cam_status)
    # print(dev.camera.actTakePicture())

    return 0


if __name__ == '__main__':
    sys.exit(main())
