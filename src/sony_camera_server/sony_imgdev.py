#!/usr/bin/env python3

"""Utilities for discovering SSDP and SonyImaging services."""

# pylint: disable=invalid-name, redefined-builtin, no-name-in-module
# pylint: disable=too-many-instance-attributes, too-many-locals

import re
import os
import time
import socket
import collections
import urllib.request
import json
import functools
import logging

from xml.etree import cElementTree
from . import xml2dict


UPnPService = collections.namedtuple("UPnPService", ["SCPDURL",
                                                     "controlURL",
                                                     "eventSubURL",
                                                     "sericeId",
                                                     "serviceType"])

ScalarWebAPI = collections.namedtuple("ScalarWebAPI", ["Services",
                                                       "LiveView_URL",
                                                       "DefaultFunction"])

ScalarWebService = collections.namedtuple("ScalarWebService", ["type", "url"])


class SonyDeviceError(Exception):
    """A class for miscellaneous Sony Device Errors."""


def parse_upnp_device_definition(upnp_dd):
    """Parse the XML device definition file."""
    root = cElementTree.XML(upnp_dd)
    root = xml2dict.XmlDictConfig(root)

    upnp_prefix = "{urn:schemas-upnp-org:device-1-0}"
    # _upnp_version = root.get(f"{upnp_prefix}specVersion", "")
    device = root.get(f"{upnp_prefix}device", "")
    name = device.get(f"{upnp_prefix}friendlyName", "")

    # Retrieve all services
    dd_services = device.get(f"{upnp_prefix}serviceList", "")
    dd_serv = dd_services.get(f"{upnp_prefix}service", "")

    # Are these service definitions ever actually used?
    upnp_services = []
    for srv in dd_serv:
        scpdurl = srv.get(f"{upnp_prefix}SCPDURL", "")
        control_url = srv.get(f"{upnp_prefix}controlURL", "")
        event_suburl = srv.get(f"{upnp_prefix}eventSubURL", "")
        service_id = srv.get(f"{upnp_prefix}serviceId", "")
        service_type = srv.get(f"{upnp_prefix}serviceType", "")
        upnp_services.append(UPnPService(scpdurl, control_url, event_suburl,
                                         service_id, service_type))

    # Retrieve functions relevant to the Sony AV extension "ScalarWebAPI".
    sony_prefix = "{urn:schemas-sony-com:av}X_ScalarWebAPI"
    scalarweb_devinfo = device.get(f"{sony_prefix}_DeviceInfo", "")
    version = scalarweb_devinfo.get(f"{sony_prefix}_Version", "")
    imgdev = scalarweb_devinfo.get(f"{sony_prefix}_ImagingDevice", "")
    live_view = imgdev.get(f"{sony_prefix}_LiveView_URL", "")
    default_fn = imgdev.get(f"{sony_prefix}_DefaultFunction", "")
    scalarweb_service = scalarweb_devinfo.get(f"{sony_prefix}_ServiceList", "")
    scalarweb_service = scalarweb_service.get(f"{sony_prefix}_Service", "")

    services = []
    for srv in scalarweb_service:
        _type = srv.get(f"{sony_prefix}_ServiceType", "")
        url = srv.get(f"{sony_prefix}_ActionList_URL", "")
        services.append(ScalarWebService(_type, url))

    webapi = ScalarWebAPI(services, live_view, default_fn)

    return name, version, webapi


class SonyEndPoint:
    """Sony Imaging Device EndPoint."""

    ID_MAX = 0x7FFF_FFFF

    def __init__(self, device, name):
        """Create a new Sony Endpoint."""
        self.device = device
        self.name = name
        self.id = 1

    def __str__(self):
        """Return a name describing the endpoint."""
        return f"SonyEndPoint@{self.name}"

    def next_id(self):
        """Generate the next ID for a request."""
        ret = self.id
        self.id = self.id % self.ID_MAX + 1
        return ret

    def unimplemented_method(self, *_args, **_kwargs):
        """Called when finding an unimplemented method."""
        return {"error": [501, "Not Implemented"], "id": self.id}

    def __getattr__(self, name):
        """Call when accessing a non-existing endpoint method."""
        return self.unimplemented_method

    def __getstate__(self):
        """When pickling this class, use this state."""
        return self.__dict__.copy()

    def __setstate__(self, d):
        """When un-pickling this class, use this method to add data."""
        self.__dict__.update(d)


class SonyImagingDevice:
    """Sony Imaging Device UPnP control."""

    CNT = 0

    SPECIAL_METHODS = {
        "setExposureCompensation",
        "setWhiteBalance",
        "setStillSize",
    }

    def __init__(self,
                 location,
                 name=None,
                 timeout_seconds=10,
                 fast_setup=False):
        """Create a new Sony Imaging Device."""
        self.location = location
        self.timeout_seconds = timeout_seconds
        self.endpoints = {}
        if not name:
            self.name = f"Sony{SonyImagingDevice.CNT}"
            SonyImagingDevice.CNT += 1

        with urllib.request.urlopen(location, timeout=timeout_seconds) as req:
            contents = req.read()
            dev_name, version, api = parse_upnp_device_definition(contents)
            self.device_name = dev_name
            self.device_version = version
            self.webapi = api

        self._build_endpoints(fast_setup)

    def __str__(self):
        """Retrieve a pretty string describing the device."""
        return f"SonyImagingDevice:{self.device_name}@{self.location}"

    def _build_endpoints(self, fast_setup):
        """Initialize all endpoints."""
        eps = self.request("guide",
                           method="getServiceProtocols",
                           params=[],
                           id=1,
                           version="1.0")
        if "results" not in eps:
            self._default_endpoints()
            return

        # Make sure that all endpoints are in the services list. Otherwise,
        # create a new service and add the endpoint to the most common
        # base-URL.
        url_vote = collections.Counter(s.url for s in self.webapi.Services)
        self.endpoints = {}
        for ep in eps["results"]:
            ep_name = ep[0]
            self.endpoints[ep_name] = {}
            found = False
            for srv in self.webapi.Services:
                if srv.type == ep_name:
                    found = True
            if not found:
                common_url = url_vote.most_common(1)[0][0]
                srv = ScalarWebService(ep_name, common_url)
                self.webapi.Services.append(srv)

        # Populate all endpoints with appropriate methods.
        params = {}
        for ep, me in self.endpoints.items():
            ep = SonyEndPoint(self, ep)
            setattr(self, ep.name, ep)
            methods = self.request(ep.name,
                                   method="getMethodTypes",
                                   params=[""],
                                   id=1,
                                   version="1.0")
            if "results" not in methods:
                continue
            params[ep.name] = {}
            for arg in methods["results"]:
                name, prms, _rsp, version = arg[0:4]
                me[name] = {}
                params[ep.name][name] = prms
                func = functools.partial(self.request,
                                         ep.name,
                                         method=name,
                                         params=[],
                                         id=ep.next_id,
                                         version=version)
                setattr(ep, name, func)

        # Populate the method sets with all supported parameters.
        for ep, methods in self.endpoints.items():
            for meth, rsp in methods.items():
                p = params[ep][meth]
                opts = []
                if not fast_setup:
                    opts = self._find_options(methods, ep, meth)
                rsp["expects"] = self._response_type(p)
                if meth in self.SPECIAL_METHODS:
                    p = self._special_method_spec(p, ep, meth, opts)
                    rsp["parameters"] = p
                else:
                    rsp["parameters"] = self._parse_arg_spec(p, ep, meth, opts)

    def _response_type(self, prms):
        """Determine which response type we want."""
        if prms:
            if prms[0].startswith("{"):
                return "object"
            else:
                return "list"
        else:
            return "none"

    def _special_method_spec(self, prms, ep, meth, opts):
        """Generate the specification entry for specific methods."""
        # ExposureCompensation uses a range metric instead of the regular
        # scheme so compute all options:
        args = {}
        if meth == "setExposureCompensation":
            if opts:
                maxi, mini, step = opts[:]
                evs = set()
                for mn, mx, s in zip(mini, maxi, step):
                    evs |= set(range(mn, mx + 1, s))
                args["EV"] = {"type": "int", "options": sorted(evs)}
            else:
                args["EV"] = {"type": "int", "options": []}
        elif meth == "setWhiteBalance":
            if opts:
                wbms = []
                cts = set()
                for obj in opts[0]:
                    wbms.append(obj["whiteBalanceMode"])
                    if obj["colorTemperatureRange"]:
                        mx, mn, step = obj["colorTemperatureRange"]
                        cts |= set(range(mn, mx + 1, step))
                args["WhiteBalanceMode"] = {"type": "string", "options": wbms}
                args["ColorTempEnable"] = {"type": "bool", "options": []}
                args["ColorTemp"] = {"type": "int", "options": sorted(cts)}
            else:
                args["WhiteBalanceMode"] = {"type": "string", "options": []}
                args["ColorTempEnable"] = {"type": "bool", "options": []}
                args["ColorTemp"] = {"type": "int", "options": []}
        elif meth == "setStillSize":
            if opts:
                aspects = set()
                sizes = set()
                for obj in opts[0]:
                    if "aspect" in obj:
                        aspects.add(obj["aspect"])
                    if "size" in obj:
                        sizes.add(obj["size"])
                args["aspect"] = {"type": "string", "options": sorted(aspects)}
                args["size"] = {"type": "string", "options": sorted(sizes)}
            else:
                args["aspect"] = {"type": "string", "options": []}
                args["size"] = {"type": "string", "options": []}
        return args

    def _parse_arg_spec(self, prms, ep, meth, opts):
        """Parse the camera method argument specification."""
        args = {}
        i = 0
        VALID_TYPES = ["bool", "int", "double", "string"]
        for a in prms:
            if a in VALID_TYPES or a[0:-1] in VALID_TYPES:
                if opts:
                    args[f"arg{i}"] = {"type": a, "options": opts[0]}
                else:
                    args[f"arg{i}"] = {"type": a, "options": []}
                i += 1
            elif a.endswith("*"):
                # Multiple freely specified arguments. This is tricky to
                # support, so just present as a generic JSON.
                args[f"arg{i}"] = {"type": "JSON*", "options": []}
                i += 1
            else:
                # Possibly multiple named arguments, attempt to decode JSON:
                try:
                    spec = json.loads(a)
                    if not opts:
                        # No candidates found from getSupportedXXX(). If
                        # additional nesting is found, the argument is
                        # converted to a generic JSON input.
                        def isnested(x):
                            return isinstance(x, list) or isinstance(x, dict)
                        if any(isnested(x) for x in spec.values()):
                            args[f"arg{i}"] = {"type": "JSON", "options": []}
                            i += 1
                        else:
                            for k, v in spec.items():
                                if v in VALID_TYPES or v[0:-1] in VALID_TYPES:
                                    args[k] = {"type": v, "options": []}
                                else:
                                    is_star = v.endswith("*")
                                    v = "string" + "*" if is_star else ""
                                    args[k] = {"type": v, "options": []}
                                i += 1
                    else:
                        # Candidates exist - attempt to merge.
                        for k, v in spec.items():
                            opt = opts[0].get("candidate", [])
                            args[k] = {"type": v, "options": opt}
                except json.decoder.JSONDecodeError:
                    # Failed to decode argspec. Present as generic JSON.
                    args[f"arg{i}"] = {"type": "JSON", "options": []}
                    i += 1
        return args

    def _find_options(self, methods, ep, method):
        """Find valid options for the given method and endpoint."""
        m = re.sub("^(set)", "", method, count=1)
        sup = "getSupported" + m
        if method.startswith("set") and sup in methods:
            epo = getattr(self, ep)
            sup = getattr(epo, sup)
            rsp = sup(params=[])
            if "result" in rsp:
                return rsp["result"]
            elif "results" in rsp:
                return rsp["results"]
            else:
                return []
        else:
            return []

    def _default_endpoints(self):
        """Create the default endpoints."""
        self.guide = SonyEndPoint(self, "guide")
        self.system = SonyEndPoint(self, "system")
        self.camera = SonyEndPoint(self, "camera")
        self.avContent = SonyEndPoint(self, "avContent")

        # Build device methods.
        for ep in [self.guide, self.system, self.camera, self.avContent]:
            methods = self.request(ep.name,
                                   method="getMethodTypes",
                                   params=[""],
                                   id=1,
                                   version="1.0")
            for arg in methods["results"]:
                name, _params, _rsp, version = arg[0:4]
                func = functools.partial(self.request,
                                         ep.name,
                                         method=name,
                                         params=[],
                                         id=ep.next_id,
                                         version=version)
                setattr(ep, name, func)

    def request(self, endpoint, id=1, version="1.0", **params):
        """Send a request to the Imaging Device."""
        url = ""
        for srv in self.webapi.Services:
            if srv.type == endpoint:
                url = os.path.join(srv.url, srv.type)
        if not url:
            return {"error": [504, "No Such API endpoint"], "id": id}
        if callable(id):
            id = id()
        if callable(version):
            version = version()
        args = dict(params, id=id, version=version)
        if "params" not in args:
            args["params"] = []
        req = urllib.request.Request(url)
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        body_utf8 = json.dumps(args)
        body = body_utf8.encode("utf-8")
        logging.debug(f"MSG {body_utf8}")
        res = {}
        try:
            timeout = self.timeout_seconds
            with urllib.request.urlopen(req, body, timeout=timeout) as req:
                contents = req.read()
                # This is a hack due to a JSON bug in Sony-HDR AS50.
                if (endpoint == "accessControl" and
                        params.get("method") == "getMethodTypes"):
                    contents = contents.replace(b",,", b",")
                res = json.loads(contents)
        except socket.timeout:
            res = {"error": [2, "timeout"], "id": id}
        except urllib.error.HTTPError as err:
            res = {"error": [err.code, err.reason], "id": id}
        except json.decoder.JSONDecodeError:
            res = {"error": [504, "Invalid data in returned JSON"]}
        except urllib.error.URLError as err:
            res = {"error": [601, err.reason], "id": id}
        logging.debug(f"RES {res}")
        return res


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
        raise SonyDeviceError("Unexpected response from getEvent: %s", ev)
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


def find_devices(scan, fast_setup=False):
    """Attempt to create a Sony Imaging Device.

    Note: For more control over network or service discoverer, adjust the
    discoverer parameters.

    .. Keyword Arguments:
    :param scan: A SSDP discoverer.
    :param fast_setup: Should devices use fast_setup? (default False)

    .. Types:
    :type scan: A SSDPDiscoverer instance.
    :type fast_setup: A boolean.

    .. Returns:
    :returns: A SonyImagingDevice

    """
    devices = dict()
    for rsp in scan.query():
        if "SonyImagingDevice" not in rsp.get("server", ""):
            continue
        if "location" not in rsp:
            continue
        devices[rsp["location"]] = rsp
    return [SonyImagingDevice(d, fast_setup=fast_setup)
            for d in devices.keys()]
