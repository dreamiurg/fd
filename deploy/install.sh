#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $EUID == 0 ]] || { echo 'Run as root.' >&2; exit 1; }
[[ ${FD_BOOTSTRAP_REF:-} =~ ^[0-9a-f]{40}$ ]] || { echo 'An immutable commit is required.' >&2; exit 1; }
[[ ${FD_BACKUP_S3_URI:-} =~ ^s3://[a-z0-9.-]+/[-A-Za-z0-9/_]*$ ]]
[[ ${FD_BACKUP_REGION:-} =~ ^[a-z]+-[a-z]+-[0-9]+$ ]]
mountpoint -q /srv/fd || { echo '/srv/fd must be a mounted data volume.' >&2; exit 1; }
exec 9>/run/lock/fd-operation.lock
flock 9
release="/opt/fd/releases/$FD_BOOTSTRAP_REF"
install -d -m 755 "$release/deploy"
base="https://raw.githubusercontent.com/dreamiurg/fd/$FD_BOOTSTRAP_REF/deploy"
for file in compose.yaml Caddyfile images.env fd.service fd-backup.service fd-backup.timer network-guard.sh backup.sh restore.sh restore-smoke.sh update.sh logrotate; do
  curl --fail --silent --show-error --location "$base/$file" -o "$release/deploy/$file.tmp"
  mv "$release/deploy/$file.tmp" "$release/deploy/$file"
done
chmod 755 "$release"/deploy/*.sh
# Only known images, pinned by content digest; never source downloaded shell env.
for name in GAME PROXY WEB; do
  grep -Eq "^FD_${name}_IMAGE=ghcr.io/dreamiurg/fd-[a-z]+@sha256:[0-9a-f]{64}$" "$release/deploy/images.env"
done
cd "$release"
compose=(docker compose --env-file deploy/images.env -f deploy/compose.yaml)
"${compose[@]}" config --quiet
"${compose[@]}" pull --quiet
game_image=$(sed -n 's/^FD_GAME_IMAGE=//p' deploy/images.env)
caddy_image=$("${compose[@]}" config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["caddy"]["image"])')
install -d -o 10001 -g 10001 -m 750 /srv/fd/game /srv/fd/caddy /srv/fd/caddy-config
if [[ -z $(find /srv/fd/game -mindepth 1 -print -quit) ]]; then
  docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --user 10001:10001 \
    --entrypoint sh -v /srv/fd/game:/seed "$game_image" -c 'cp -a /var/lib/fd/. /seed/'
fi
[[ -f /srv/fd/game/areas/area.lst ]] || { echo 'Existing game data is incomplete; refusing to overwrite it.' >&2; exit 1; }
install -d -m 700 /srv/fd/private
if [[ ! -e /srv/fd/private/access.env ]]; then
  password=$(openssl rand -hex 32)
  printf 'FD_GATE_USER=friends\nFD_GATE_PASSWORD=%s\n' "$password" > /srv/fd/private/access.env
  unset password
fi
chmod 600 /srv/fd/private/access.env
if [[ ! -e /srv/fd/private/gate.caddy ]]; then
  # Plaintext goes over stdin, never argv, Docker env, user-data, or logs.
  sed -n 's/^FD_GATE_PASSWORD=//p' /srv/fd/private/access.env |
    docker run --rm -i --network none --entrypoint caddy "$caddy_image" hash-password > /srv/fd/private/gate.hash
  { printf 'basic_auth {\n    friends '; tr -d '\r\n' < /srv/fd/private/gate.hash; printf '\n}\n'; } > /srv/fd/private/gate.caddy
  rm /srv/fd/private/gate.hash
fi
chown 10001:10001 /srv/fd/private/gate.caddy
chmod 400 /srv/fd/private/gate.caddy
"${compose[@]}" run --rm --no-deps caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1
printf 'FD_BACKUP_S3_URI=%s\nFD_BACKUP_REGION=%s\n' "$FD_BACKUP_S3_URI" "$FD_BACKUP_REGION" > /etc/fd-backup.env
install -m 644 deploy/fd.service deploy/fd-backup.service deploy/fd-backup.timer /etc/systemd/system/
install -m 644 deploy/logrotate /etc/logrotate.d/fd
# On this dedicated host, Docker itself must wait for the data mount on boot.
install -d -m 755 /etc/systemd/system/docker.service.d
printf '[Unit]\nRequiresMountsFor=/srv/fd\n' > /etc/systemd/system/docker.service.d/fd-data.conf
previous=$(readlink /opt/fd/current || true)
systemctl stop fd.service || true
ln -sfn "$release" /opt/fd/current
systemctl daemon-reload
if ! systemctl enable --now fd.service; then
  if [[ -n $previous ]]; then
    ln -sfn "$previous" /opt/fd/current
    systemctl restart fd.service
  fi
  echo 'Deployment failed; previous release restored when available.' >&2
  exit 1
fi
systemctl enable --now fd-backup.timer
echo "Forgotten Dungeon release $FD_BOOTSTRAP_REF installed."
