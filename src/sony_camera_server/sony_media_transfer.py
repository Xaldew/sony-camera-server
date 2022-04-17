#!/usr/bin/env python3

"""Utilities for transferring media from a Sony camera."""


import os.path
import urllib
import sys
import argparse
import logging
import shutil

from . import ssdp
from . import device_cache
from . import sony_imgdev


def dump_device_files(dev, view, output_dir):
    """Dump all the files from the device in the given output_dir.

    Note that the device is assumed to be in Contents Transfer mode for this
    function.

    .. Keyword Arguments:
    :param dev: The device to use
    :param view: The view to dump them with.
    :param output_dir: The output directory.

    """
    for fold, fil in sony_imgdev.sony_media_walk(dev, view):
        if fil["contentKind"] == "directory" and view == "date":
            date_fold = os.path.join(output_dir, fold, fil["title"])
            os.makedirs(date_fold, exist_ok=True)
        else:
            for orig in fil["content"]["original"]:
                fil_orig = orig["fileName"]
                file_name = os.path.join(output_dir, fil_orig)
                if view == "date":
                    file_name = os.path.join(output_dir, fold, fil_orig)
                url = orig["url"]
                try:
                    with open(file_name, "wb") as fw:
                        with urllib.request.urlopen(url) as resp:
                            shutil.copyfileobj(resp, fw)
                except (urllib.error.HTTPError,
                        urllib.error.URLError) as err:
                    logging.warning("Download error %s: %s", url, err)


def dump_files(devs, view, output_dir):
    """Dump all found files on each device in the given output directory.

    .. Keyword Arguments:
    :param devs: A list of Sony Imaging Devices.
    :param view: The mode to dump the files in.
    :param output_dir: The directory the files will be dumped in.

    """
    for dev in devs:
        try:
            state = sony_imgdev.get_status(dev)
            if state != "ContentsTransfer":
                dev.camera.setCameraFunction(params=["Contents Transfer"])
                sony_imgdev.await_state(dev, "ContentsTransfer")
            out = os.path.join(output_dir, dev.device_name)
            os.makedirs(out, exist_ok=True)
            dump_device_files(dev, view, out)
            if state != "ContentsTransfer":
                dev.camera.setCameraFunction(params=["Remote Shooting"])
                sony_imgdev.await_state(dev, "IDLE")
        except sony_imgdev.SonyDeviceError as err:
            logging.warning("Device: %s unresponsive: %s", dev, err)


def main(device_name, view, output_dir):
    """Start running the med Streamer."""
    try:
        scan = ssdp.SSDPDiscoverer(ssdp.SONY_SERVICE_TYPE)
        cache = device_cache.DeviceCache()
        if device_name:
            dev = cache.find_device(scan, device_name)
            if not dev:
                print(f"Device not found: {dev}")
                return -1
            devs = [dev]
        else:
            devs = cache.scan_devices(scan)
        logging.info("Devices: %s", devs)
        dump_files(devs, view, output_dir)
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
    kdesc = "Media Transferring from a Sony Imaging Device."
    parser = argparse.ArgumentParser(description=kdesc, formatter_class=fmtr)
    parser.add_argument("-v", "--verbosity", metavar="N", type=int,
                        default=logging.WARNING,
                        choices=range(logging.NOTSET, logging.CRITICAL),
                        help="Set logging verbosity level.")
    parser.add_argument("-f", "--folder-view", default="flat",
                        choices={"flat", "date"},
                        help="Which mode should the media be dumped in.")
    parser.add_argument("-n", "--device-name", type=str, default="",
                        help="Partial name of the Sony device to prefer.")
    parser.add_argument("-o", "--output-dir", default=os.getcwd(),
                        help="Where should the media be dumped?")
    return parser.parse_args(argv)


def run():
    """Run the application."""
    ARGS = parse_arguments(sys.argv[1:])
    logging.basicConfig(level=ARGS.verbosity)
    return main(ARGS.device_name, ARGS.folder_view, ARGS.output_dir)


if __name__ == '__main__':
    sys.exit(run())
