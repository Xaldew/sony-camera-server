#!/usr/bin/env python3

"""Utilities for transferring media from a Sony camera."""


import os.path
import urllib
import time
import sys
import argparse
import logging
import shutil

import ssdp
import sony_imgdev


class SonyDeviceError(Exception):
    """A class for miscellaneous Sony Device Errors."""


def find_files_uri(dev, uri, view):
    """List all files in the given URI."""
    arg = {"uri": uri, "view": view}
    res = dev.avContent.getContentCount(params=[arg])
    res = res.get("result", [{"count": 0}])
    cnt = res[0]["count"]
    iters = (cnt > 0) + cnt // 100
    for i in range(0, iters):
        carg = {"uri": uri,
                "stIdx": i * 100,
                "cnt": 100,
                "view": view}
        res = dev.avContent.getContentList(params=[carg])
        contents = res.get("result", [[]])
        for f in contents[0]:
            yield f


def sony_media_walk(dev, view):
    """Walk over the media hierarchy on the Sony Imaging Device."""
    res = dev.avContent.getSchemeList()
    schemes = res.get("result", [[]])
    srcs = []
    for sch in schemes:
        res = dev.avContent.getSourceList(params=sch)
        storage = res.get("result", [[]])
        srcs.extend(storage[0])
    for s in srcs:
        iters = [("", find_files_uri(dev, s["source"], view))]
        while iters:
            base, files = iters.pop()
            for f in files:
                if f.get("contentKind", "") == "directory":
                    folder = os.path.join(base, f.get("title", ""))
                    rec = find_files_uri(dev, f.get("uri", ""), view)
                    iters.append((folder, rec))
                yield base, f


def find_devices(scan):
    """Find all present Sony Imaging Devices.

    .. Keyword Arguments:
    :param scan: A SSDP scanner.

    .. Returns:
    :returns: A list of imaging devices.

    """
    devices = dict()
    for rsp in scan.query():
        if "SonyImagingDevice" not in rsp.get("server", ""):
            continue
        if "location" not in rsp:
            continue
        devices[rsp["location"]] = rsp
    return [sony_imgdev.SonyImagingDevice(d, fast_setup=True)
            for d in devices.keys()]


def dump_files(devs, view, output_dir):
    """Dump all found files on each device in the given output directory.

    .. Keyword Arguments:
    :param devs: A list of Sony Imaging Devices.
    :param view: The mode to dump the files in.
    :param output_dir: The directory the files will be dumped in.

    """
    for dev in devs:
        try:
            state = get_status(dev)
            if state != "ContentsTransfer":
                dev.camera.setCameraFunction(params=["Contents Transfer"])
                await_state(dev, "ContentsTransfer")
            out = os.path.join(output_dir, dev.device_name)
            os.makedirs(out, exist_ok=True)
            for fold, fil in sony_media_walk(dev, view):
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
                            with (open(file_name, "wb") as fw,
                                  urllib.request.urlopen(url) as resp):
                                shutil.copyfileobj(resp, fw)
                        except (urllib.error.HTTPError, urllib.error.URLError):
                            logging.warning(f"Unable to download: {url}")
            if state != "ContentsTransfer":
                dev.camera.setCameraFunction(params=["Remote Shooting"])
                await_state(dev, "IDLE")
        except SonyDeviceError as err:
            logging.warning(f"Device: {dev} unresponsive: {err}")


def get_status(dev):
    """Retrieve the current status of the device.

    .. Keyword Arguments:
    :param dev: The device to query.

    .. Returns:
    :returns: The current status of the camera.
    :rtype: A string.

    """
    ev = dev.camera.getEvent(params=[False])
    if "result" not in ev:
        raise SonyDeviceError("Unexpected response from getEvent")
    return ev["result"][1]["cameraStatus"]


def await_state(dev, state, tries=10, sleep_secs=1):
    """Await state change on the device up to the specified number of tries.

    .. Keyword Arguments:
    :param dev: The device to query.
    :param state: The state to wait for.
    :param tries: The number of attempts (default 10).
    :param sleep_secs: Number of seconds to sleep between attempts (default 1).

    """
    for t in range(0, tries):
        camera_state = get_status(dev)
        if camera_state == state:
            return
        time.sleep(sleep_secs)
    raise SonyDeviceError(f"Device state not reached after {tries} attempts")


def main(view, output_dir):
    """Start running the med Streamer."""
    try:
        scan = ssdp.SSDPDiscoverer(ssdp.SONY_SERVICE_TYPE)
        devs = find_devices(scan)
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


if __name__ == '__main__':
    ARGS = parse_arguments(sys.argv[1:])
    logging.basicConfig(level=ARGS.verbosity)
    sys.exit(main(ARGS.folder_view, ARGS.output_dir))
