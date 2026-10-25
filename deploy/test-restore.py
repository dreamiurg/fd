#!/usr/bin/env python3
"""Verify safe restore boundaries with synthetic files only."""
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile

restore = Path(__file__).with_name('restore.sh')
with tempfile.TemporaryDirectory(prefix='fd-restore-test-') as directory:
    root = Path(directory)

    def archive(path, members):
        with tarfile.open(path, 'w:gz') as output:
            for name, contents in members.items():
                entry = tarfile.TarInfo(name)
                entry.size = len(contents)
                output.addfile(entry, io.BytesIO(contents))

    good = root / 'good.tar.gz'
    archive(good, {'areas/area.lst': b'test.are\n$\n', 'player/Smokeexample': b'synthetic fixture\n'})
    target = root / 'restored'
    subprocess.run([str(restore), str(good), str(target)], check=True, capture_output=True)
    assert (target / 'player/Smokeexample').read_bytes() == b'synthetic fixture\n'
    assert subprocess.run([str(restore), str(good), str(target)], capture_output=True).returncode != 0
    assert (target / 'player/Smokeexample').read_bytes() == b'synthetic fixture\n'
    bad = root / 'bad.tar.gz'
    archive(bad, {'areas/area.lst': b'$\n', '../escaped': b'must not escape'})
    assert subprocess.run([str(restore), str(bad), str(root / 'rejected')], capture_output=True).returncode != 0
    assert not (root / 'escaped').exists()
    print('PASS: restore preserves player bytes, refuses nonempty targets, and rejects archive path traversal')
