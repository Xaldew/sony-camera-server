#!/usr/bin/env python3

"""Utilities for the Simple Service Discovery Protocol"""

import socket
import platform

SSDP_ADDR = '239.255.255.250'
SSDP_PORT = 1900
SSDP_MX = 1

DISCOVERY_MSG_FMT = ('M-SEARCH * HTTP/1.1\r\n'
                     'HOST: %s:%d\r\n'
                     'MAN: "ssdp:discover"\r\n'
                     'MX: %d\r\n'
                     'ST: %s\r\n'
                     '\r\n')

SONY_SERVICE_TYPE = "urn:schemas-sony-com:service:ScalarWebAPI:1"


def parse_ssdp_response(data):
    """Parse the header of a SSDP response message.

    """
    lines = data.split(b'\r\n')
    if not lines and lines[0] == b'HTTP/1.1 200 OK':
        raise KeyError("Invalid SSDP Response")
    headers = {}
    for line in lines[1:]:
        if not line:
            continue
        key, val = line.split(b': ', 1)
        headers[str(key.lower(), "utf8")] = str(val, "utf8")
    return headers


class SSDPDiscoverer:
    """SDDP Device Discoverer."""

    def __init__(self,
                 service_type,
                 interfaces=socket.if_nameindex(),
                 timeout=2):
        self.service_type = service_type
        self.timeout = timeout
        self.sockets = []
        for (idx, inf) in interfaces:
            sock = socket.socket(socket.AF_INET,
                                 socket.SOCK_DGRAM,
                                 socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET,
                            socket.SO_REUSEADDR,
                            1)
            sock.setsockopt(socket.IPPROTO_IP,
                            socket.IP_MULTICAST_TTL,
                            2)
            sock.settimeout(timeout)
            try:
                pltfm = platform.system()
                if pltfm == "Linux":
                    sock.setsockopt(socket.SOL_SOCKET,
                                    socket.SO_BINDTODEVICE,
                                    inf.encode())
                elif pltfm == "Darwin":
                    IP_BOUND_IF = 25
                    sock.setsockopt(socket.IPPROTO_IP,
                                    IP_BOUND_IF,
                                    idx)
            except AttributeError:
                pass
            self.sockets.append(sock)

    def __str__(self):
        return "SSDPDiscoverer"

    def query(self):
        """Attempt to discover SSDP devices."""
        ssdp_st = self.service_type
        msg = DISCOVERY_MSG_FMT % (SSDP_ADDR, SSDP_PORT, SSDP_MX, ssdp_st)
        services = {}
        for sock in self.sockets:
            try:
                sock.sendto(bytes(msg, "ASCII"), (SSDP_ADDR, SSDP_PORT))
                data = sock.recv(1024)
                srv = parse_ssdp_response(data)
                key = tuple(sorted(srv.items()))
                services[key] = srv
            except socket.timeout:
                pass
            except OSError:
                pass
            except KeyError:
                pass
        return services.values()
