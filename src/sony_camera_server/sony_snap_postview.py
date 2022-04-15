#!/usr/bin/env python3

"""Snap a picture with a Sony camera and download it using postview."""


import os.path
import urllib
import sys
import argparse
import logging
import datetime
import shutil

from . import sony_imgdev
from . import ssdp


def snap_picture(dev):
    """Snap a picture using the Sony Imaging Device.

    .. Keyword Arguments:
    :param dev: The device to snap a picture with.

    .. Returns:
    :returns: A string with the postview URL.

    """
    status = sony_imgdev.get_status(dev)
    if status == "ContentsTransfer":
        dev.camera.setCameraFunction(params=["Remote Shooting"])
        sony_imgdev.await_state(dev, "IDLE")
    dev.camera.setShootMode(params=["still"])
    sony_imgdev.await_state(dev, "IDLE")
    res = dev.camera.actTakePicture()
    sony_imgdev.await_state(dev, "IDLE")
    return res.get("result", [[""]])[0][0]


def delete_picture(dev, url):
    """Delete the given picture on the camera.

    .. Keyword Arguments:
    :param dev: The imaging device to interface with.
    :param url: The postview URL to delete.

    """
    status = sony_imgdev.get_status(dev)
    if status != "ContentsTransfer":
        dev.camera.setCameraFunction(params=["Contents Transfer"])
        sony_imgdev.await_state(dev, "ContentsTransfer")

    # The postview does not give any hint of the actual file URI, so we need to
    # trawl the contents tree and delete the most recent file.
    latest, fd = None, None
    for base, fil in sony_imgdev.sony_media_walk(dev, "flat"):
        created_time = datetime.datetime.fromisoformat(fil["createdTime"])
        if not latest or created_time > latest:
            latest = created_time
            fd = fil

    if fil:
        logging.info(f"Deleting: {fd['uri']}")
        dev.avContent.deleteContent(params=[{"uri": [fd["uri"]]}])
        sony_imgdev.await_state(dev, "ContentsTransfer")

    if status != "ContentsTransfer":
        dev.camera.setCameraFunction(params=["Remote Shooting"])
        sony_imgdev.await_state(dev, "IDLE")


def main(output, delete):
    """Find a camera, snap a picture and download it."""
    try:
        scan = ssdp.SSDPDiscoverer(ssdp.SONY_SERVICE_TYPE)
        devs = sony_imgdev.find_devices(scan, fast_setup=True)
        logging.info(f"Devices: {devs}")
        if not devs:
            print("No device found.")
            return -1
        postview_url = snap_picture(devs[0])
        if not postview_url:
            print("No postview URL available.")
            return -2
        if not output:
            parse_res = urllib.parse.urlparse(postview_url)
            output = os.path.basename(parse_res.path)
        with open(output, "wb") as fw:
            with urllib.request.urlopen(postview_url) as resp:
                shutil.copyfileobj(resp, fw)
        if delete:
            delete_picture(devs[0], postview_url)
        return 0
    except sony_imgdev.SonyDeviceError as err:
        print(f"Imaging device error: {err}")
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
    kdesc = "Snap a picture with a Sony camera and download it using postview."
    parser = argparse.ArgumentParser(description=kdesc, formatter_class=fmtr)
    parser.add_argument("output", default="", nargs="?", type=str,
                        help="The name of the output image file.")
    parser.add_argument("-v", "--verbosity", metavar="N",
                        action="store_const", const=logging.INFO,
                        help="Be more verbose.")
    parser.add_argument("-d", "--delete", action="store_true",
                        help="Delete the file after transferring the image.")
    return parser.parse_args(argv)


def run():
    """Run the application."""
    ARGS = parse_arguments(sys.argv[1:])
    logging.basicConfig(level=ARGS.verbosity)
    return main(ARGS.output, ARGS.delete)


if __name__ == '__main__':
    sys.exit(run())
