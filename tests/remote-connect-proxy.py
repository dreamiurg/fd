#!/usr/bin/env python3
"""Confine WebKit acceptance traffic to FD while TLS remains browser-to-server."""
import argparse
import select
import socket
import socketserver

DESTINATION = ('fd.dreamiurg.net', 443)


class Tunnel(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        header = b''
        while b'\r\n\r\n' not in header:
            chunk = self.request.recv(4096)
            if not chunk:
                return
            header += chunk
            if len(header) > 8192:
                return
        head, _, remainder = header.partition(b'\r\n\r\n')
        first = head.split(b'\r\n', 1)[0].split()
        if (len(first) != 3 or first[0] != b'CONNECT'
                or first[1] != b'fd.dreamiurg.net:443'
                or first[2] not in (b'HTTP/1.0', b'HTTP/1.1')):
            self.request.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
            return
        # Never derive the upstream host or port from a request. TLS bytes are
        # forwarded unchanged; this process has no gate credentials or TLS keys.
        with socket.create_connection(DESTINATION, timeout=15) as upstream:
            self.request.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            self.request.settimeout(None)
            upstream.settimeout(None)
            if remainder:
                upstream.sendall(remainder)
            while True:
                readable, _, _ = select.select([self.request, upstream], [], [], 30)
                for source in readable:
                    chunk = source.recv(65536)
                    if not chunk:
                        return
                    target = upstream if source is self.request else self.request
                    target.sendall(chunk)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Do not log request headers or tunnel contents.
        print('FD acceptance tunnel connection closed after an I/O error.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18890)
    arguments = parser.parse_args()
    with Server(('127.0.0.1', arguments.port), Tunnel) as server:
        print(f'FD-only TLS tunnel listening on 127.0.0.1:{arguments.port}', flush=True)
        server.serve_forever()
