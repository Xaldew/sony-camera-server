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
from . import device_cache
from . import ssdp


def is_jpeg(fil):
    """Check if this file is a JPEG.

    .. Keyword Arguments:
    :param fil: The current file name.

    .. Types:
    :type fil: A string.

    .. Returns:
    :returns: True if it is a JPEG, otherwise False.
    :rtype: Boolean.

    """
    _, ext = os.path.splitext(fil)
    ext = ext.lower()
    if ext in [".jpeg", ".jpg"]:
        return True
    else:
        return False


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
    for _, fil in sony_imgdev.sony_media_walk(dev, "flat"):
        created_time = datetime.datetime.fromisoformat(fil["createdTime"])
        if not latest or created_time > latest:
            latest = created_time
            fd = fil
    if fd:
        logging.info(f"Deleting: {fd['uri']}")
        dev.avContent.deleteContent(params=[{"uri": [fd["uri"]]}])
        sony_imgdev.await_state(dev, "ContentsTransfer")

    if status != "ContentsTransfer":
        dev.camera.setCameraFunction(params=["Remote Shooting"])
        sony_imgdev.await_state(dev, "IDLE")


def snap_picture(dev):
    """Snap a picture using the Sony Imaging Device.

    Note: This method does not wait for camera IDLING after taking a picture.

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
    return res.get("result", [[""]])[0][0]


def postview_download(dev, url, output, delete):
    """Download the picture using the postview feature.

    .. Keyword Arguments:
    :param dev: The Sony Imaging Device.
    :param url: The postview URL of the image.
    :param output: The desired name of the output file.
    :param delete: Should the on-camera picture be deleted?

    """
    if not output:
        parse_res = urllib.parse.urlparse(url)
        output = os.path.basename(parse_res.path)
    with open(output, "wb") as fw:
        with urllib.request.urlopen(url) as resp:
            shutil.copyfileobj(resp, fw)
    if delete:
        delete_picture(dev, url)


def save_file(fd, output):
    """Save the given Sony file descriptor at the given output file.

    .. Keyword Arguments:
    :param fd: The Sony file-descriptor to save.
    :param output: The desired output file-name.

    """
    if not output:
        for fil in fd["content"]["original"]:
            url = fil["url"]
            file_name = fil["fileName"]
            with open(file_name, "wb") as fw:
                with urllib.request.urlopen(url) as resp:
                    shutil.copyfileobj(resp, fw)
    elif output and is_jpeg(output):
        for fil in fd["content"]["original"]:
            url = fil["url"]
            file_name = fil["fileName"]
            if is_jpeg(file_name):
                with open(output, "wb") as fw:
                    with urllib.request.urlopen(url) as resp:
                        shutil.copyfileobj(resp, fw)
                        break
    elif output:
        # User have specified something that is not a JPEG, download first
        # non-jpeg original file.
        for fil in fd["content"]["original"]:
            url = fil["url"]
            file_name = fil["fileName"]
            if not is_jpeg(file_name):
                with open(output, "wb") as fw:
                    with urllib.request.urlopen(url) as resp:
                        shutil.copyfileobj(resp, fw)
                        break


def download_original(dev, output, delete):
    """Download the latest picture and optionally delete it.

    .. Keyword Arguments:
    :param dev: The Sony Imaging Device.
    :param output: The local filename to save the picture as.
    :param delete: Should the on-camera picture be deleted?

    """
    status = sony_imgdev.get_status(dev)
    if status != "ContentsTransfer":
        dev.camera.setCameraFunction(params=["Contents Transfer"])
        sony_imgdev.await_state(dev, "ContentsTransfer")

    # The postview does not give any hint of the actual file URI, so we need to
    # trawl the contents tree and delete the most recent file.
    latest, fd = None, None
    for _, fil in sony_imgdev.sony_media_walk(dev, "flat"):
        created_time = datetime.datetime.fromisoformat(fil["createdTime"])
        if not latest or created_time > latest:
            latest = created_time
            fd = fil

    if fd:
        save_file(fd, output)

    if delete and fd:
        logging.info(f"Deleting: {fd['uri']}")
        dev.avContent.deleteContent(params=[{"uri": [fd["uri"]]}])
        sony_imgdev.await_state(dev, "ContentsTransfer")

    if status != "ContentsTransfer":
        dev.camera.setCameraFunction(params=["Remote Shooting"])
        sony_imgdev.await_state(dev, "IDLE")



def main(output, device_name, store_mode, delete):
    """Find a camera, snap a picture and download it."""
    try:
        scan = ssdp.SSDPDiscoverer(ssdp.SONY_SERVICE_TYPE)
        cache = device_cache.DeviceCache()
        dev = cache.find_device(scan, device_name)
        logging.info("Using device: %s", dev)
        if not dev:
            print("No device found.")
            return -1
        postview_url = snap_picture(dev)
        if store_mode == "postview":
            sony_imgdev.await_state(dev, "IDLE")
            postview_download(dev, postview_url, output, delete)
        elif store_mode == "original":
            sony_imgdev.await_state(dev, "IDLE")
            download_original(dev, output, delete)
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
    parser.add_argument("-v", "--verbosity", metavar="N", type=int,
                        default=logging.WARNING,
                        choices=range(logging.NOTSET, logging.CRITICAL),
                        help="Set logging verbosity level.")
    parser.add_argument("-s", "--store-mode", type=str, default="none",
                        choices={"none", "postview", "original"},
                        help="How (if at all) should the image be stored?")
    parser.add_argument("-d", "--delete", action="store_true",
                        help="Delete the file after transferring the image.")
    parser.add_argument("-n", "--device-name", type=str, default="",
                        help="Partial name of the Sony device to prefer.")
    return parser.parse_args(argv)


def run():
    """Run the application."""
    ARGS = parse_arguments(sys.argv[1:])
    logging.basicConfig(level=ARGS.verbosity)
    return main(ARGS.output, ARGS.device_name, ARGS.store_mode, ARGS.delete)


if __name__ == '__main__':
    sys.exit(run())
