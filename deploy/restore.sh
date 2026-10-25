#!/usr/bin/env bash
set -euo pipefail
[[ $# == 2 ]] || { echo 'Usage: restore.sh ARCHIVE EMPTY_TARGET_DIRECTORY' >&2; exit 1; }
# Never overwrites live data. Caller chooses an empty, isolated destination.
python3 - "$1" "$2" <<'PY'
import os, pathlib, sys, tarfile
archive, target = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
target.mkdir(parents=True, exist_ok=True)
if any(target.iterdir()):
    raise SystemExit('Restore target must be empty.')
with tarfile.open(archive, 'r:gz') as data:
    members = data.getmembers()
    if not any(m.name.lstrip('./') == 'areas/area.lst' for m in members):
        raise SystemExit('Not an FD game backup.')
    data.extractall(target, members=members, filter='data')
if os.geteuid() == 0:
    for base, directories, files in os.walk(target):
        os.chown(base, 10001, 10001)
        for name in files:
            os.chown(os.path.join(base, name), 10001, 10001, follow_symlinks=False)
print('Restored game state into empty target.')
PY
