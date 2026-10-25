#!/usr/bin/env python3
"""Verify public HTTPS/WebSocket access, origin restrictions, TLS, DNS, and private TCP."""

import argparse
import base64
import hashlib
import http.client
import json
import os
import socket
import ssl
from datetime import datetime
from zoneinfo import ZoneInfo


HOST = "fd.dreamiurg.net"


def request(path, websocket=False, origin="https://" + HOST, expect_rejection=False):
    connection = http.client.HTTPSConnection(HOST, timeout=15, context=ssl.create_default_context())
    connection.connect()
    certificate = connection.sock.getpeercert()
    headers = {}
    key = base64.b64encode(os.urandom(16)).decode()
    if websocket:
        headers.update({"Connection": "Upgrade", "Upgrade": "websocket", "Sec-WebSocket-Version": "13",
                        "Sec-WebSocket-Key": key, "Origin": origin})
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        body = b"" if response.status == 101 else response.read(65536)
        if response.status == 101:
            expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            assert response.getheader("Sec-WebSocket-Accept") == expected, "Invalid WebSocket handshake"
            if expect_rejection:
                # The pinned proxy checks Origin after upgrading, before creating
                # a game connection. Attempt game access, then require its first
                # frame to close the socket without any application data.
                command = b'{"connect":1,"mud":"fd"}'
                mask = os.urandom(4)
                frame = bytes([0x81, 0x80 | len(command)]) + mask
                frame += bytes(value ^ mask[index % 4] for index, value in enumerate(command))
                connection.sock.settimeout(3)
                connection.sock.sendall(frame)
                header = response.fp.read(2)
                assert len(header) == 2 and header[0] == 0x88, "Foreign origin received application data or remained open"
                assert header[1] <= 125 and header[1] != 1, "Invalid server close frame"
                assert len(response.fp.read(header[1])) == header[1], "Incomplete server close frame"
        elif expect_rejection:
            assert response.status == 403, "Foreign origin was not rejected"
        return response.status, body, certificate
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-ip", required=True, help="Address independently confirmed from AWS metadata or authoritative Route53 DNS")
    args = parser.parse_args()
    addresses = sorted({item[4][0] for item in socket.getaddrinfo(HOST, 443, socket.AF_UNSPEC)})
    assert addresses == [args.expected_ip], "Recursive DNS does not match the independently confirmed address"
    redirect = http.client.HTTPConnection(HOST, timeout=15)
    try:
        redirect.request("GET", "/")
        response = redirect.getresponse()
        assert response.status in (301, 308) and response.getheader("Location") == "https://" + HOST + "/", "HTTP did not redirect to standard HTTPS"
    finally:
        redirect.close()
    status, body, certificate = request("/")
    assert status == 200 and b"Forgotten Dungeon" in body, "Public site is unavailable"
    assert request("/health")[0] == 200, "Public health endpoint is unavailable"
    assert request("/ws", websocket=True)[0] == 101, "Public WebSocket upgrade failed"
    rejected_status = request("/ws", websocket=True, origin="https://example.invalid", expect_rejection=True)[0]
    with socket.socket() as probe:
        probe.settimeout(5)
        assert probe.connect_ex((args.expected_ip, 4000)) != 0, "Game TCP port 4000 is publicly reachable"
    expiry = datetime.fromtimestamp(ssl.cert_time_to_seconds(certificate["notAfter"]), ZoneInfo("America/Los_Angeles"))
    print(json.dumps({"host": HOST, "addresses": addresses, "tls_verified": True,
                      "certificate_expires_local": expiry.isoformat(), "timezone": "America/Los_Angeles",
                      "http_redirect": "https://" + HOST + "/",
                      "public_site": 200, "public_health": 200, "public_websocket": 101,
                      "foreign_websocket_origin": {"handshake_status": rejected_status, "rejected_before_application_data": True},
                      "external_game_port_4000": "unreachable"}, indent=2))


if __name__ == "__main__":
    main()
