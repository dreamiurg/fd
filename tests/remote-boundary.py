#!/usr/bin/env python3
"""Verify the production HTTPS gate, WebSocket gate, TLS, DNS, and private TCP port."""

import argparse
import base64
import hashlib
import http.client
import json
import os
import socket
import ssl
import stat
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


HOST = "fd.dreamiurg.net"


def credentials(path):
    path = Path(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600, "Access file must have mode 0600"
    fields = dict(line.split("=", 1) for line in path.read_text().splitlines() if line and not line.startswith("#"))
    user, password = fields["FD_GATE_USER"], fields["FD_GATE_PASSWORD"]
    assert user and password and ":" not in user and "\r" not in user + password
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def request(path, authorization=None, websocket=False):
    connection = http.client.HTTPSConnection(HOST, timeout=15, context=ssl.create_default_context())
    connection.connect()
    certificate = connection.sock.getpeercert()
    headers = {}
    if authorization:
        headers["Authorization"] = authorization
    key = base64.b64encode(os.urandom(16)).decode()
    if websocket:
        headers.update({"Connection": "Upgrade", "Upgrade": "websocket", "Sec-WebSocket-Version": "13",
                        "Sec-WebSocket-Key": key, "Origin": "https://" + HOST})
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        body = b"" if response.status == 101 else response.read(65536)
        if response.status == 101:
            expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            assert response.getheader("Sec-WebSocket-Accept") == expected, "Invalid WebSocket handshake"
        return response.status, body, certificate
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", required=True, help="Path to the private mode-0600 access.env; never prints its contents")
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
    for route in ("/", "/health", "/ws"):
        status, _, _ = request(route, websocket=route == "/ws")
        assert status == 401, f"Unauthenticated {route} returned {status}, expected 401"
    wrong = "Basic " + base64.b64encode(b"friends:incorrect-acceptance-password").decode()
    assert request("/", wrong)[0] == 401, "Incorrect gate password was accepted"
    authorization = credentials(args.credentials)
    status, body, certificate = request("/", authorization)
    assert status == 200 and b"Forgotten Dungeon" in body, "Authenticated site is unavailable"
    assert request("/ws", authorization, websocket=True)[0] == 101, "Authenticated WebSocket upgrade failed"
    with socket.socket() as probe:
        probe.settimeout(5)
        assert probe.connect_ex((args.expected_ip, 4000)) != 0, "Game TCP port 4000 is publicly reachable"
    expiry = datetime.fromtimestamp(ssl.cert_time_to_seconds(certificate["notAfter"]), ZoneInfo("America/Los_Angeles"))
    print(json.dumps({"host": HOST, "addresses": addresses, "tls_verified": True,
                      "certificate_expires_local": expiry.isoformat(), "timezone": "America/Los_Angeles",
                      "unauthenticated_site_health_ws": 401, "wrong_password": 401,
                      "http_redirect": "https://" + HOST + "/",
                      "authenticated_site": 200, "authenticated_websocket": 101,
                      "external_game_port_4000": "unreachable"}, indent=2))


if __name__ == "__main__":
    main()
