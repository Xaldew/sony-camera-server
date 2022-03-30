#!/usr/bin/env python3

"""Utilities for capturing Sony Image Device media streams."""

import struct
import threading
import urllib.request

# pylint: disable=redefined-builtin

# Common Header
# 0--------1--------2--------+--------4----+----+----+----8
# |0xFF    |payload | sequence number | Time stamp        |
# |        |type    |                 |                   |
# +-------------------------------------------------------+
#
# Payload Header
# 0--------------------------4-------------------7--------8
# | Start code               |  JPEG data size   | Padding|
# +--------------------------4------5---------------------+
# | Reserved                 | 0x00 | ..                  |
# +-------------------------------------------------------+
# | .. 115[B] Reserved                                    |
# +-------------------------------------------------------+
# | ...                                                   |
# ------------------------------------------------------128
#
# Payload Data
# in case payload type = 0x01
# +-------------------------------------------------------+
# | JPEG data size ...                                    |
# +-------------------------------------------------------+
# | ...                                                   |
# +-------------------------------------------------------+
# | Padding data size ...                                 |
# ------------------------------JPEG data size + Padding data size


JPEG_DATA = 0x01
FRAME_DATA = 0x02


def common_header(data):
    """Extract the Common Header from a Sony LiveView stream."""
    (start_byte, payload_type,
     sequence_number, time_stamp) = struct.unpack('!BBHI', data)
    if start_byte != 255:  # 0xff fixed
        raise RuntimeError('[error] wrong QX livestream start byte')

    return {'start_byte': start_byte,
            'payload_type': payload_type,
            'sequence_number': sequence_number,
            'time_stamp': time_stamp,     # Milliseconds
            }


def payload_header(data, type=1):
    """Extract the Payload from a Sony LiveView stream."""
    # payload_type = 1, assume JPEG
    (start_code, jpeg_data_size_2, jpeg_data_size_1,
     jpeg_data_size_0, padding_size) = struct.unpack_from('!IBBBB', data)
    if start_code != 607479929:
        raise RuntimeError('[error] wrong QX payload header start')

    # This seems silly, but it's a 3-byte-integer !
    jpeg_data_size = (jpeg_data_size_0 * 2**0 +
                      jpeg_data_size_1 * 2**8 +
                      jpeg_data_size_2 * 2**16)

    if jpeg_data_size > 100000:
        raise RuntimeError(f"Possibly wrong image size ({jpeg_data_size})?")

    payload_hdr = {
        'start_code': start_code,
        'jpeg_data_size': jpeg_data_size,
        'padding_size': padding_size,
    }

    if type == 1:
        payload_hdr.update(payload_header_jpeg(data))
    elif type == 2:
        payload_hdr.update(payload_header_frameinfo(data))
    else:
        raise RuntimeError(f"Unknown payload type: {type}")

    return payload_hdr


def payload_header_jpeg(data):
    """Extract the payload header from a Sony LiveView stream."""
    reserved_1, flag = struct.unpack_from('!IB', data, offset=8)
    if flag != 0:
        raise RuntimeError(f"Wrong QX payload header flag: {flag}")

    return {
        'reserved_1': reserved_1,
        'flag': flag
    }


def payload_header_frameinfo(data):
    """Extract the payload frameinfo header from a Sony LiveView stream."""
    (version,
     frame_count,
     frame_size) = struct.unpack_from('!HHH', data, offset=8)
    return {
        'version': version,
        'frame_count': frame_count,
        'frame_size': frame_size
    }


def payload_frameinfo(data):
    """Extract the frameinfo from a payload for a Sony LiveView stream."""
    left, top, right, bottom = struct.unpack_from(">HHHH", data)
    category, status, additional = struct.unpack_from("BBB", data, offset=8)
    return {
        'left': left,
        'top': top,
        'right': right,
        'bottom': bottom,
        'category': category,
        'status': status,
        'additional': additional
    }


class LiveviewStreamThread(threading.Thread):
    """Thread capable of parsing the Sony binary LiveView format."""

    def __init__(self, url, jpeg_callback, frameinfo_callback=lambda x: x):
        super().__init__()
        self.lv_url = url
        self.jpeg_cb = jpeg_callback
        self.fi_cb = frameinfo_callback
        self.daemon = True

    def run(self):
        with urllib.request.urlopen(self.lv_url) as session:
            while True:
                hdr = session.read(8)
                comhdr = common_header(hdr)

                data = session.read(128)
                payload = payload_header(data, type=comhdr['payload_type'])

                if comhdr['payload_type'] == JPEG_DATA:
                    size = payload['jpeg_data_size']
                    img = session.read(size)
                    if len(img) != size:
                        msg = f"Payload length mismatch: {len(img)} vs. {size}"
                        raise ValueError(msg)
                    self.jpeg_cb(img)

                elif comhdr['payload_type'] == FRAME_DATA:
                    for _ in range(payload['frame_count']):
                        data = session.read(payload['frame_size'])
                        frameinfo = payload_frameinfo(data)
                        self.fi_cb(frameinfo)

                # Skip the padding.
                session.read(payload['padding_size'])
