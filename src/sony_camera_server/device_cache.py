#!/usr/bin/env python3

"""Cache previously created Sony Imaging devices."""

import os
import pickle
import logging

from . import sony_imgdev


class DeviceCache:
    """Sony Imaging Device caching mechanism."""

    def __init__(self):
        # Read on disk cache.
        self.cache = {}
        cwd = os.getcwd()
        if "XDG_RUNTIME_DIR" in os.environ:
            cache_dir = os.environ["XDG_RUNTIME_DIR"]
            cache_file = "sony_device_cache"
        else:
            cache_dir = cwd
            cache_file = ".sony_device_cache"
        self.cache_file = os.path.join(cache_dir, cache_file)
        try:
            with open(self.cache_file, "rb") as f:
                self.cache = pickle.load(f)
        except (OSError, pickle.PickleError) as err:
            logging.warning("Unable to read cache: %s", err)
            self.cache = {}

    def __del__(self):
        # Update on disk cache.
        logging.info("Writing cache to file %s.", self.cache_file)
        with open(self.cache_file, "wb") as f:
            pickle.dump(self.cache, f)

    def add(self, ssdp_dev):
        """Add a new Sony Imaging Device to the cache.

        .. Keyword Arguments:
        :param ssdp_dev: A SSDP discovered Sony device.

        .. Types:
        :type ssdp_dev: A dictionary.

        .. Returns:
        :returns: A complete Sony Imaging Device.

        """
        key = tuple(sorted(ssdp_dev.items()))
        if key not in self.cache:
            self.cache[key] = sony_imgdev.SonyImagingDevice(ssdp_dev["location"])
            return self.cache[key]
        else:
            return self.cache[key]

    def find_device(self, ssdp, name=""):
        """Return the first found Sony Imaging Device.

        Searches the cache and optionally scans the network for a device
        matching `name`.  If empty, it returns the first found device in the
        cache, or scans the network if the cache is empty.

        .. Keyword Arguments:
        :param ssdp: A SSDP discoverer.
        :param name: The name of the device to search for. (default "")

        .. Returns:
        :returns: A sony imaging device, or None.

        """
        if not self.cache:
            self.scan_devices(ssdp)
            return next(iter(self.cache.values()), None)
        if not name:
            return next(iter(self.cache.values()))
        for d in self.cache.values():
            if name.lower() in d.device_name.lower():
                return d

    def scan_devices(self, ssdp):
        """Scan the network for Sony Imaging Devices.

        .. Keyword Arguments:
        :param ssdp: A SSDP discoverer.

        .. Types:
        :type ssdp: A SSDPDiscoverer instance.

        .. Returns:
        :returns: A list of all detected devices.

        """
        devices = {}
        for rsp in ssdp.query():
            if "SonyImagingDevice" not in rsp.get("server", ""):
                continue
            if "location" not in rsp:
                continue
            devices[rsp["location"]] = self.add(rsp)
        return list(devices.values())
