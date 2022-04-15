#!/usr/bin/env python3

"""Utilities for transferring media from a Sony camera."""


import os.path
import urllib
import sys
import argparse
import logging
import shutil

from . import ssdp
from . import sony_imgdev


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
            for fold, fil in sony_imgdev.sony_media_walk(dev, view):
                if fil["contentKind"] == "directory" and view == "date":
                    date_fold = os.path.join(out, fold, fil["title"])
                    os.makedirs(date_fold, exist_ok=True)
                else:
                    for orig in fil["content"]["original"]:
                        fil_orig = orig["fileName"]
                        file_name = os.path.join(out, fil_orig)
                        if view == "date":
                            file_name = os.path.join(out, fold, fil_orig)
                        url = orig["url"]
                        try:
                            with open(file_name, "wb") as fw:
                                with urllib.request.urlopen(url) as resp:
                                    shutil.copyfileobj(resp, fw)
                        except (urllib.error.HTTPError, urllib.error.URLError):
                            logging.warning(f"Unable to download: {url}")
            if state != "ContentsTransfer":
                dev.camera.setCameraFunction(params=["Remote Shooting"])
                sony_imgdev.await_state(dev, "IDLE")
        except sony_imgdev.SonyDeviceError as err:
            logging.warning(f"Device: {dev} unresponsive: {err}")


def main(view, output_dir):
    """Start running the med Streamer."""
    try:
        scan = ssdp.SSDPDiscoverer(ssdp.SONY_SERVICE_TYPE)
        devs = sony_imgdev.find_devices(scan, fast_setup=True)
        logging.info(f"Devices: {devs}")
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
    parser.add_argument("-v", "--verbosity", metavar="N",
                        action="store_const", const=logging.INFO,
                        help="Be more verbose.")
    parser.add_argument("-f", "--folder-view", default="flat",
                        choices={"flat", "date"},
                        help="Which mode should the media be dumped in.")
    parser.add_argument("-o", "--output-dir", default=os.getcwd(),
                        help="Where should the media be dumped?")
    return parser.parse_args(argv)


def run():
    """Run the application."""
    ARGS = parse_arguments(sys.argv[1:])
    logging.basicConfig(level=ARGS.verbosity)
    return main(ARGS.folder_view, ARGS.output_dir)


if __name__ == '__main__':
    sys.exit(run())
