#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 && $# == 1 && $1 =~ ^[0-9a-f]{40}$ ]] || { echo 'Usage: sudo update.sh COMMIT_SHA' >&2; exit 1; }
# Routine releases must reuse an installed world, never seed a missing save tree.
mountpoint -q /srv/fd
[[ -f /srv/fd/game/areas/area.lst && -d /srv/fd/game/player ]] || { echo 'Existing game data is missing; deployment refused.' >&2; exit 1; }
set -a
source /etc/fd-backup.env
set +a
/opt/fd/current/deploy/backup.sh
release="/opt/fd/releases/$1"
install -d -m 755 "$release/deploy"
curl --fail --silent --show-error --location "https://raw.githubusercontent.com/dreamiurg/fd/$1/deploy/install.sh" -o "$release/deploy/install.sh.tmp"
mv "$release/deploy/install.sh.tmp" "$release/deploy/install.sh"
FD_BOOTSTRAP_REF="$1" bash "$release/deploy/install.sh"
