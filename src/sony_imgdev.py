#!/usr/bin/env python3

"""Utilities for discovering SSDP and SonyImaging services."""

# pylint: disable=invalid-name, redefined-builtin, no-name-in-module
# pylint: disable=too-many-instance-attributes, too-many-locals

import os
import collections
import urllib.request
import json
import functools

from xml.etree import cElementTree
import xml2dict


UPnPService = collections.namedtuple("UPnPService", ["SCPDURL",
                                                     "controlURL",
                                                     "eventSubURL",
                                                     "sericeId",
                                                     "serviceType"])

ScalarWebAPI = collections.namedtuple("ScalarWebAPI", ["Services",
                                                       "LiveView_URL",
                                                       "DefaultFunction"])

ScalarWebService = collections.namedtuple("ScalarWebService", ["type", "url"])


def parse_upnp_device_definition(upnp_dd):
    """Parse the XML device definition file."""
    root = cElementTree.XML(upnp_dd)
    root = xml2dict.XmlDictConfig(root)

    # _upnp_version = root.get("{urn:schemas-upnp-org:device-1-0}specVersion", "")
    device = root.get("{urn:schemas-upnp-org:device-1-0}device", "")
    name = device.get("{urn:schemas-upnp-org:device-1-0}friendlyName", "")

    # Retrieve all services
    dd_services = device.get(
        "{urn:schemas-upnp-org:device-1-0}serviceList", "")
    dd_serv = dd_services.get("{urn:schemas-upnp-org:device-1-0}service", "")

    # Are these service definitions ever actually used?
    upnp_services = []
    for srv in dd_serv:
        scpdurl = srv.get("{urn:schemas-upnp-org:device-1-0}SCPDURL",
                          "")
        control_url = srv.get("{urn:schemas-upnp-org:device-1-0}controlURL",
                              "")
        event_suburl = srv.get("{urn:schemas-upnp-org:device-1-0}eventSubURL",
                               "")
        service_id = srv.get("{urn:schemas-upnp-org:device-1-0}serviceId",
                             "")
        service_type = srv.get("{urn:schemas-upnp-org:device-1-0}serviceType",
                               "")
        upnp_services.append(UPnPService(scpdurl, control_url, event_suburl,
                                         service_id, service_type))

    # Retrieve functions relevant to the Sony AV extension "ScalarWebAPI".
    scalarweb_devinfo = device.get(
        "{urn:schemas-sony-com:av}X_ScalarWebAPI_DeviceInfo",
        "")
    version = scalarweb_devinfo.get(
        "{urn:schemas-sony-com:av}X_ScalarWebAPI_Version",
        "")
    imgdev = scalarweb_devinfo.get(
        "{urn:schemas-sony-com:av}X_ScalarWebAPI_ImagingDevice",
        "")
    live_view = imgdev.get(
        "{urn:schemas-sony-com:av}X_ScalarWebAPI_LiveView_URL",
        "")
    default_fn = imgdev.get(
        "{urn:schemas-sony-com:av}X_ScalarWebAPI_DefaultFunction",
        "")
    scalarweb_servlist = scalarweb_devinfo.get(
        "{urn:schemas-sony-com:av}X_ScalarWebAPI_ServiceList",
        "")
    scalarweb_servlist = scalarweb_servlist.get(
        "{urn:schemas-sony-com:av}X_ScalarWebAPI_Service",
        "")

    services = []
    for srv in scalarweb_servlist:
        _type = srv.get(
            "{urn:schemas-sony-com:av}X_ScalarWebAPI_ServiceType",
            "")
        url = srv.get(
            "{urn:schemas-sony-com:av}X_ScalarWebAPI_ActionList_URL",
            "")
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

    def __getattr__(self, name):
        """Call when accessing a non-existing endpoint method."""
        def unimplemented_method(*args, **kwargs):
            return {"error": [501, "Not Implemented"], "id": self.id}
        return unimplemented_method


class SonyImagingDevice:
    """Sony Imaging Device UPnP control."""

    CNT = 0

    def __init__(self, location, name=None, timeout_seconds=5):
        """Create a new Sony Imaging Device."""
        self.location = location
        self.timeout_seconds = timeout_seconds
        if not name:
            self.name = f"Sony{SonyImagingDevice.CNT}"
            SonyImagingDevice.CNT += 1

        with urllib.request.urlopen(location, timeout=timeout_seconds) as req:
            contents = req.read()
            dev_name, version, api = parse_upnp_device_definition(contents)
            self.device_name = dev_name
            self.device_version = version
            self.webapi = api

        self._build_endpoints()

    def __str__(self):
        """Retrieve a pretty string describing the device."""
        return f"SonyImagingDevice:{self.device_name}@{self.location}"

    def _build_endpoints(self):
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
        # create a new service and add the endpoint to the most common base-URL.
        url_vote = collections.Counter(s.url for s in self.webapi.Services)
        self.endpoints = []
        for ep in eps["results"]:
            ep_name = ep[0]
            self.endpoints.append(ep_name)
            found = False
            for srv in self.webapi.Services:
                if srv.type == ep_name:
                    found = True
            if not found:
                common_url = url_vote.most_common(1)[0][0]
                srv = ScalarWebService(ep_name, common_url)
                self.webapi.Services.append(srv)

        # Populate all endpoints with appropriate methods.
        for ep in self.endpoints:
            ep = SonyEndPoint(self, ep)
            setattr(self, ep.name, ep)
            methods = self.request(ep.name,
                                   method="getMethodTypes",
                                   params=[""],
                                   id=1,
                                   version="1.0")
            if "results" not in methods:
                continue
            for arg in methods["results"]:
                name, _params, _rsp, version = arg[0:4]
                func = functools.partial(self.request,
                                         ep.name,
                                         method=name,
                                         params=[],
                                         id=ep.next_id,
                                         version=version)
                setattr(ep, name, func)

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
        body = json.dumps(args).encode("utf-8")
        try:
            timeout = self.timeout_seconds
            with urllib.request.urlopen(req, body, timeout=timeout) as req:
                contents = req.read()
                # This is a hack due to a JSON bug in Sony-HDR AS50.
                if endpoint == "accessControl" and params.get("method") == "getMethodTypes":
                    contents = contents.replace(b",,", b",")
                return json.loads(contents)
        except urllib.error.HTTPError as err:
            return {"error": [err.code, err.reason], "id": id}
        except json.decoder.JSONDecodeError:
            return {"error": [504, "Invalid data in returned JSON"]}
        except urllib.error.URLError as err:
            return {"error": [err.code, err.reason], "id": id}


def create_sony_imaging_device(ssdp):
    """Attempt to create a Sony Imaging Device.

    Note: Creates an imaging device from the first matching SSDP device, for
    more control over network or services, adjust the discoverer parameters.

    .. Keyword Arguments:
    :param ssdp: A SSDP discoverer.

    .. Types:
    :type ssdp: A SSDPDiscoverer instance.

    .. Returns:
    :returns: A SonyImagingDevice

    """
    query = ssdp.query()
    for rsp in query:
        if ("SonyImagingDevice" in rsp.get("server", "") and "location" in rsp):
            return SonyImagingDevice(rsp["location"])
    raise KeyError("Unable to find any SonyImagingDevice")
