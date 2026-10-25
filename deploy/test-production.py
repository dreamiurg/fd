#!/usr/bin/env python3
"""Check deployment isolation and the real Caddy auth boundary, without live data."""
import base64
import http.client
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout.strip()


with tempfile.TemporaryDirectory(prefix='fd-production-test-') as temporary:
    temp = Path(temporary)
    manifest = temp / 'images.env'
    manifest.write_text(''.join(f'FD_{name}_IMAGE=ghcr.io/dreamiurg/fd-{name.lower()}@sha256:{"a" * 64}\n' for name in ('GAME', 'PROXY', 'WEB')))
    config = json.loads(run('docker', 'compose', '--env-file', str(manifest), '-f', str(ROOT / 'deploy/compose.yaml'), 'config', '--format', 'json'))
    services = config['services']
    assert {key for key, service in services.items() if service.get('ports')} == {'caddy'}
    assert {int(port['published']) for port in services['caddy']['ports']} == {80, 443}
    assert sum(int(service['mem_limit']) for service in services.values()) <= 576 * 1024**2
    assert all(service['read_only'] and service['cap_drop'] == ['ALL'] for service in services.values())
    assert services['web-proxy']['environment']['ALLOWED_ORIGINS'] == 'https://fd.dreamiurg.net'
    assert services['web']['tmpfs'] == ['/tmp:size=16m,mode=1777']
    assert config['networks']['game']['internal'] and config['networks']['web']['internal']
    assert services['caddy']['cap_add'] == ['NET_BIND_SERVICE']
    assert all(not s.get('cap_add') for key, s in services.items() if key != 'caddy')
    print('PASS: only 80/443 published; private internal networks; bounded memory and privileges')

    image = services['caddy']['image']
    password = secrets.token_hex(16)
    hashed = run('docker', 'run', '--platform', 'linux/amd64', '--rm', '-i', '--network', 'none', '--entrypoint', 'caddy', image, 'hash-password', input=password + '\n')
    gate = temp / 'gate.caddy'
    gate.write_text(f'basic_auth {{\n friends {hashed}\n}}\n')
    gate.chmod(0o644)
    caddyfile = temp / 'Caddyfile'
    caddyfile.write_text((ROOT / 'deploy/Caddyfile').read_text().replace('fd.dreamiurg.net {', 'http://:8080 {'))
    caddyfile.chmod(0o644)
    network = 'fd-gate-test-' + uuid.uuid4().hex[:10]
    names = [network + suffix for suffix in ('-backend', '-caddy', '-client1', '-client2')]
    run('docker', 'network', 'create', network)
    try:
        server = "const h=require('node:http');for(const port of [8080,6200]){const s=h.createServer((q,r)=>{if(q.headers.authorization){r.writeHead(500);r.end('credential leaked')}else r.end('ok')});s.on('upgrade',(q,s)=>{if(q.headers.authorization)return s.end('HTTP/1.1 500 Credential Leak\\r\\n\\r\\n');s.end('HTTP/1.1 101 Switching Protocols\\r\\nUpgrade: websocket\\r\\nConnection: Upgrade\\r\\nX-Test-Peer: '+q.headers['x-forwarded-for']+'\\r\\n\\r\\n')});s.listen(port,'0.0.0.0');}"
        run('docker', 'run', '--platform', 'linux/amd64', '-d', '--name', names[0], '--network', network, '--network-alias', 'web', '--network-alias', 'web-proxy', '--entrypoint', 'node', 'fd-production-proxy:validation', '-e', server)
        run('docker', 'run', '--platform', 'linux/amd64', '-d', '--name', names[1], '--network', network, '--user', '10001:10001', '--read-only', '--tmpfs', '/data:uid=10001,gid=10001,mode=700', '--tmpfs', '/config:uid=10001,gid=10001,mode=700', '--cap-drop', 'ALL', '--cap-add', 'NET_BIND_SERVICE', '--security-opt', 'no-new-privileges', '-p', '127.0.0.1::8080', '-v', f'{caddyfile}:/etc/caddy/Caddyfile:ro', '-v', f'{gate}:/etc/caddy/gate.caddy:ro', image)
        status = json.loads(run('docker', 'inspect', names[1]))[0]
        if not status['State']['Running']:
            raise AssertionError(subprocess.run(['docker', 'logs', names[1]], capture_output=True, text=True).stderr)
        port = int(status['NetworkSettings']['Ports']['8080/tcp'][0]['HostPort'])

        def request(path, auth=None):
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
            headers = {'Connection': 'Upgrade', 'Upgrade': 'websocket'} if path == '/ws' else {}
            if auth:
                headers['Authorization'] = 'Basic ' + base64.b64encode(('friends:' + auth).encode()).decode()
            connection.request('GET', path, headers=headers)
            response = connection.getresponse()
            status = response.status
            connection.close()
            return status

        for attempt in range(30):
            try:
                if request('/') == 401:
                    break
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(0.2)
        for path in ('/', '/health', '/ws'):
            assert request(path) == 401, path
            assert request(path, 'incorrect') == 401, path
        assert request('/', password) == 200
        assert request('/ws', password) == 101
        print('PASS: real Caddy rejects missing/wrong auth on site, health and WebSocket; accepts authorized HTTP/WebSocket; strips upstream credentials')
        peers = []
        for name in names[2:]:
            run('docker', 'run', '--platform', 'linux/amd64', '-d', '--name', name, '--network', network, '--entrypoint', 'node', 'fd-production-proxy:validation', '-e', 'setInterval(()=>{},1000)')
            client = "const h=require('node:http');const password=require('node:fs').readFileSync(0,'utf8').trim();const q=h.request({host:" + json.dumps(names[1]) + ",port:8080,path:'/ws',headers:{Authorization:'Basic '+Buffer.from('friends:'+password).toString('base64'),Connection:'Upgrade',Upgrade:'websocket','X-Forwarded-For':'203.0.113.88'} });q.on('upgrade',(r,s)=>{console.log(r.headers['x-test-peer']);s.destroy()});q.on('response',r=>{console.error(r.statusCode);process.exit(1)});q.on('error',()=>process.exit(1));q.end();"
            peer = run('docker', 'exec', '-i', name, 'node', '-e', client, input=password + '\n')
            assert peer and '203.0.113.88' not in peer, 'External forwarded IP spoof was accepted'
            peers.append(peer)
        assert peers[0] != peers[1], 'Distinct clients collapsed to one rate-limit identity'
        print('PASS: authenticated WebSockets preserve distinct client IPs and reject spoofed forwarding headers')
    finally:
        for name in names:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        subprocess.run(['docker', 'network', 'rm', network], check=True, capture_output=True)
