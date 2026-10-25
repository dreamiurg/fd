#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 1; }
mountpoint -q /srv/fd
: "${FD_BACKUP_S3_URI:?backup destination required}"
: "${FD_BACKUP_REGION:?backup region required}"
exec 9>/run/lock/fd-operation.lock
flock 9
cd /opt/fd/current
compose=(docker compose --env-file deploy/images.env -f deploy/compose.yaml)
archive=$(mktemp /srv/fd/backup.XXXXXX.tar.gz)
restart_game() { "${compose[@]}" up -d --wait --wait-timeout 120 game; }
cleanup() { rm -f "$archive"; }
trap cleanup EXIT
# SIGTERM saves players before exit. Archive only after the process has stopped.
"${compose[@]}" stop game
trap 'restart_game; cleanup' EXIT
tar -czf "$archive" -C /srv/fd/game .
restart_game
trap cleanup EXIT
key="${FD_BACKUP_S3_URI%/}/fd-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
aws s3 cp "$archive" "$key" --region "$FD_BACKUP_REGION" --sse AES256 --only-show-errors
echo "Backup uploaded to $key"
