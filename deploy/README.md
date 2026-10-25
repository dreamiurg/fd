# AWS deployment

Routine releases are automatic on `codex/aws-hosting`: push reviewed source,
then the workflow builds cached native amd64 images, commits their immutable
digests to `deploy/images.env`, backs up the running world, and deploys that
release child commit. The image revision labels identify the source commit;
the manifest commit identifies the exact deployed source/configuration/digests.
A stale source head refuses deployment. Bot manifest commits do not trigger
another build. No Terraform pin PR is needed for application releases.

The AWS role can invoke only the fixed deployment document on the FD instance.
The nonsecret GitHub repository variables `FD_DEPLOY_ROLE_ARN` and
`FD_INSTANCE_ID` are configured once from Terraform. Infrastructure and bootstrap
remain in `terraform-aws-personal`; the app role cannot change them.

Routine updates require the existing `/srv/fd` mount, area list and player
directory. They never format or reseed the data volume. Player saves and persisted
world files stay under `/srv/fd/game`; a failed backup aborts deployment. Current
releases keep the save format unchanged. Future save-format changes need an
explicit migration and recovery plan before shipping.

The original local Compose stack remains separate. Production uses only public
ports 80 and 443 and Caddy automatic HTTPS. The website and `/ws` are public;
players authenticate with their in-game character passwords. WebSockets go
directly from Caddy to the proxy, preserving separate client rate-limit identities
and rejecting spoofed forwarding headers. The proxy accepts only the production origin and the
fixed `game:4000` destination. Game and proxy networks are internal. Caddy runs
nonroot with only NET_BIND_SERVICE (required by its official binary); the game,
proxy, and web containers drop every capability. Containers
cannot access instance metadata; only host backup commands use the instance role.

Images are built for amd64 in GitHub Actions, outside the 1 GiB host. Official
base image digests, upstream source commits, action commits and the deployed
image digests are pinned. The three application references in `images.env`
are published by the release process. Never build images on the VM.

Bootstrap requires an already mounted `/srv/fd` data volume and root:

```sh
FD_BOOTSTRAP_REF=<40-character-commit> \
FD_BACKUP_S3_URI=s3://<bucket>/backups FD_BACKUP_REGION=us-west-2 \
bash /opt/fd/releases/<commit>/deploy/install.sh
```

The installer fetches only deployment files at that commit, pulls and validates
images before stopping the existing service, seeds only an empty game directory,
and preserves existing saves. It refuses incomplete, nonempty game data. Releases live under `/opt/fd/releases`; `/opt/fd/current`
selects the active release. The systemd service is `fd.service`. Docker waits
for the data mount on boot. The installer rolls back the release symlink if the
new service fails its startup check. Obsolete shared-gate credential files are
removed only after successful startup; failed upgrades retain them for rollback.

The server handles SIGTERM by saving complete connected and linkdead player
characters from the game loop. Incomplete character creation is excluded.
The game remains historical software: use unique game passwords because player
files contain plaintext passwords. Do not grant administrator accounts to friends.

Operations:

```sh
sudo systemctl restart fd.service
sudo systemctl start fd-backup.service
sudo /opt/fd/current/deploy/update.sh <40-character-commit>
sudo /opt/fd/current/deploy/restore-smoke.sh
```

The daily backup timer runs around 04:00 America/Los_Angeles. It briefly stops
the game, saves players, archives `/srv/fd/game`, restarts the game, and uploads
to the private S3 prefix with server-side encryption. Connections disconnect
and players use Reconnect afterward. TLS state is not included in game archives.
Updates take a backup first.

`restore.sh ARCHIVE EMPTY_TARGET_DIRECTORY` refuses nonempty targets and uses
Python's safe tar extraction. `restore-smoke.sh` downloads the newest archive,
restores a temporary directory, verifies every regular file byte-for-byte
against the archive (reporting only counts), and boots it without any network
access to check the login menu. It never overwrites live state. Actual recovery is an explicit
administrator operation: stop the service, preserve the existing game directory,
restore into an empty replacement directory, then restart and verify login.

Runtime memory limits total 576 MiB, leaving space for Ubuntu, Docker, and SSM.
Docker logs rotate at 3 × 5 MiB per service; historical text logs rotate separately.
Source publication removes old player/god/log snapshots at branch HEAD; original
upstream commits remain identifiable. Game assets are copied by an allowlist.

Local production boundary check (after building `fd-production-proxy:validation`):

```sh
python3 deploy/test-production.py
```

The check uses separate temporary containers and a network, verifies public
HTTP/WebSocket access, strips stale browser Authorization headers upstream,
preserves distinct client IPs, and confirms only the gateway publishes ports.
Remote browser and persistence acceptance are documented separately in `docs/deployment-validation.md`.
