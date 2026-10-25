#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $EUID == 0 ]] || exit 1
mountpoint -q /srv/fd
set -a
source /etc/fd-backup.env
set +a
exec 9>/run/lock/fd-operation.lock
flock 9
scratch=$(mktemp -d /srv/fd/restore-check.XXXXXX)
container="fd-restore-check-$$"
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; rm -rf "$scratch"; }
trap cleanup EXIT
# The configured URI includes a prefix: split it without exposing any credentials.
bucket_prefix=${FD_BACKUP_S3_URI#s3://}
bucket=${bucket_prefix%%/*}
prefix=${bucket_prefix#*/}
key=$(aws s3api list-objects-v2 --bucket "$bucket" --prefix "$prefix/" --region "$FD_BACKUP_REGION" --query 'sort_by(Contents,&LastModified)[-1].Key' --output text)
[[ -n $key && $key != None ]]
aws s3 cp "s3://$bucket/$key" "$scratch/backup.tar.gz" --region "$FD_BACKUP_REGION" --only-show-errors
/opt/fd/current/deploy/restore.sh "$scratch/backup.tar.gz" "$scratch/game"
python3 - "$scratch/backup.tar.gz" "$scratch/game" <<'PY'
import hashlib, pathlib, sys, tarfile
def digest(stream):
    return hashlib.file_digest(stream, 'sha256').digest()
root = pathlib.Path(sys.argv[2])
count = players = 0
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    for member in archive.getmembers():
        if not member.isfile():
            continue
        relative = pathlib.PurePosixPath(member.name)
        with archive.extractfile(member) as original, (root / relative).open('rb') as restored:
            if digest(original) != digest(restored):
                raise SystemExit('Restored file does not match the backup.')
        count += 1
        if len(relative.parts) == 2 and relative.parts[0] == 'player':
            players += 1
print(f'Verified {count} restored files byte-for-byte, including {players} player saves.')
PY
image=$(sed -n 's/^FD_GAME_IMAGE=//p' /opt/fd/current/deploy/images.env)
docker run -d --name "$container" --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --memory 256m --pids-limit 64 -v "$scratch/game:/var/lib/fd" "$image" >/dev/null
for attempt in $(seq 1 45); do
  if docker exec "$container" sh -c "nc -w 2 127.0.0.1 4000 </dev/null | grep -q 'Select your codepage:'"; then
    echo 'Isolated restored game booted and served its login menu.'
    exit 0
  fi
  sleep 1
done
echo 'Restored game did not become ready.' >&2
exit 1
