#!/usr/bin/env python3
"""A real unsaved player update must survive SIGTERM on an isolated game."""
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import time
import uuid

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fd_smoke', root / 'tests/smoke.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
name = 'fd-stop-test-' + uuid.uuid4().hex[:10]
volume = name + '-data'


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def ready(port):
    for attempt in range(40):
        try:
            session = smoke.Session(port=port)
            session.expect('Select your codepage:', timeout=2)
            session.socket.close()
            return
        except (OSError, AssertionError):
            time.sleep(0.25)
    raise AssertionError('Isolated game failed to start')


try:
    run('docker', 'run', '-d', '--name', name, '--platform', 'linux/amd64', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '-p', '127.0.0.1::4000', '-v', volume + ':/var/lib/fd', 'fd-production-game:validation')
    port = int(json.loads(run('docker', 'inspect', name))[0]['NetworkSettings']['Ports']['4000/tcp'][0]['HostPort'])
    ready(port)
    character, password = smoke.fresh_name(), secrets.token_hex(12)
    session = smoke.Session(port=port)
    session.create(character, password)
    marker = 'UnsavedStop' + secrets.token_hex(5)
    session.command('title ' + marker)
    run('docker', 'stop', '--time', '45', name)
    state = json.loads(run('docker', 'inspect', name))[0]['State']
    assert state['ExitCode'] == 0, state['ExitCode']
    session.socket.close()
    run('docker', 'start', name)
    port = int(json.loads(run('docker', 'inspect', name))[0]['NetworkSettings']['Ports']['4000/tcp'][0]['HostPort'])
    ready(port)
    session = smoke.Session(port=port)
    session.login(character, password)
    assert marker in session.command('score'), 'Unsaved title was lost on SIGTERM'
    session.quit()
    print('PASS: real unsaved title survived SIGTERM save, container stop/start, and password login')
finally:
    subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    subprocess.run(['docker', 'volume', 'rm', volume], capture_output=True)
