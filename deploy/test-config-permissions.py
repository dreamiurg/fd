#!/usr/bin/env python3
"""Reproduce bootstrap file permissions on Linux, not macOS bind-mount semantics."""
from pathlib import Path
import re
import subprocess
import uuid

compose = Path(__file__).with_name('compose.yaml').read_text()
image = re.search(r'image: (docker.io/library/caddy:[^\s]+)', compose).group(1)
volume = 'fd-config-permissions-' + uuid.uuid4().hex[:10]
base = ['docker', 'run', '--rm', '--platform', 'linux/amd64']


def run(arguments, **kwargs):
    return subprocess.run(arguments, capture_output=True, text=True, **kwargs)


try:
    # Match root + umask 077 in install.sh. A Docker volume enforces real Linux
    # UID permissions; Docker Desktop host-file sharing can mask this defect.
    run(base + ['-i', '--network', 'none', '-v', volume + ':/fixture', '--entrypoint', 'sh', image,
                '-c', 'umask 077; cat > /fixture/Caddyfile'],
        input='{\n admin off\n}\nhttp://:8080 {\n respond ok\n}\n', check=True)
    ownership = run(base + ['-v', volume + ':/fixture', '--entrypoint', 'stat', image,
                            '-c', '%u:%g %a', '/fixture/Caddyfile'], check=True).stdout.strip()
    assert ownership == '0:0 600', ownership
    validate = base + ['--network', 'none', '--user', '10001:10001', '--read-only',
                       '--cap-drop', 'ALL', '--cap-add', 'NET_BIND_SERVICE',
                       '--security-opt', 'no-new-privileges', '-v', volume + ':/fixture:ro',
                       '--entrypoint', 'caddy', image, 'validate', '--config', '/fixture/Caddyfile']
    before = run(validate)
    assert before.returncode != 0 and 'permission denied' in before.stderr
    run(base + ['-v', volume + ':/fixture', '--entrypoint', 'chmod', image,
                '644', '/fixture/Caddyfile'], check=True)
    after = run(validate)
    assert after.returncode == 0, 'Caddy must read the public root-owned 0644 config'
    print('PASS: Linux root-owned 0600 config is rejected; 0644 config validates as UID 10001')
finally:
    run(['docker', 'volume', 'rm', volume], check=True)
