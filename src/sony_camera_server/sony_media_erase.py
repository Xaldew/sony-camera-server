#!/usr/bin/env python3

"""Utilities for erasing all media from a Sony camera."""

import sys
import argparse
import logging

from . import ssdp
from . import device_cache
from . import sony_imgdev


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
            It must be "yes" (the default), "no" or None (meaning
            an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            msg = "Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n"
            sys.stdout.write(msg)


def erase_all_files(dev):
    """Erase all files on the device.

    Make sure backup and desired files these before calling this function.

    .. Keyword Arguments:
    :param dev: The Sony Imaging Devices to erase all files from.

    """
    try:
        state = sony_imgdev.get_status(dev)
        if state != "ContentsTransfer":
            dev.camera.setCameraFunction(params=["Contents Transfer"])
            sony_imgdev.await_state(dev, "ContentsTransfer")

        uris = []
        for _, fil in sony_imgdev.sony_media_walk(dev, "flat"):
            uris.append(fil["uri"])

        for chk in chunks(uris, 100):
            dev.avContent.deleteContent(params=[{"uri": chk}])
            sony_imgdev.await_state(dev, "ContentsTransfer")

        if state != "ContentsTransfer":
            dev.camera.setCameraFunction(params=["Remote Shooting"])
            sony_imgdev.await_state(dev, "IDLE")
    except sony_imgdev.SonyDeviceError as err:
        logging.warning("Device: %s unresponsive: %s", dev, err)


def main(device_name, force):
    """Start running the med Streamer."""
    try:
        scan = ssdp.SSDPDiscoverer(ssdp.SONY_SERVICE_TYPE)
        cache = device_cache.DeviceCache()
        dev = cache.find_device(scan, device_name)
        if not dev:
            print(f"Device not found: {dev}")
            return -1
        if force:
            logging.info("Erasing device: %s", dev)
            erase_all_files(dev)
        elif query_yes_no(f"Really erase all files on '{dev.device_name}?"):
            logging.info("Erasing device: %s", dev)
            erase_all_files(dev)
        else:
            logging.info("Cancelled device erasure.")
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
    parser.add_argument("-n", "--device-name", type=str, default="",
                        help="Partial name of the Sony device to prefer.")
    parser.add_argument("-f", "--force", action="store_true",
                        help="No interactive prompting.")
    return parser.parse_args(argv)


def run():
    """Run the application."""
    ARGS = parse_arguments(sys.argv[1:])
    logging.basicConfig(level=ARGS.verbosity)
    return main(ARGS.device_name, ARGS.force)


if __name__ == '__main__':
    sys.exit(run())
