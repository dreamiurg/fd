# Forgotten Dungeon, locally

This branch runs the original Forgotten Dungeon engine and world from Git commit
`49136aeadc582c535682fdd781d89a476ea3b046`, the first upstream import. Its in-game
version is **4.83.46 (Saboteur)**. The import contains source from 1998–2006;
the 2004 Makefile date does not make it an exact 2004 release.

## Start and connect

From this checkout, with Docker running:

```sh
docker compose up --build -d
docker compose ps
```

Open **http://localhost:8080** in your browser. Choose **2 (Windows-1251)** at the
initial prompt. The browser bridge converts between Unicode and the game's
original CP1251 encoding. Game assets remain in their original encoding.

For a Telnet/MUD client, connect to **127.0.0.1:4000**, select CP1251 encoding in
your client, and choose **2** in the game. For example:

```sh
telnet 127.0.0.1 4000
```

A UTF-8-only terminal will not display the direct Telnet connection correctly;
use the browser client or a MUD client with CP1251 support.

Create a new character with a unique name of 3–12 letters. A straightforward
first character is `human`, sex `m` or `f`, class `warrior`, alignment `n`, manual
skills `n`, and weapon `sword`. Press Enter after the message of the day.
Useful commands: `look`, `north`, `south`, `who`, `say Привет`, `inventory`,
`score`, `help`, `save`, and `quit`. `colour` toggles ANSI colors.

**Use a throwaway password.** This historical engine stores character passwords
in plaintext. The services are bound to localhost, and this setup is for local
use. It is not approved for public deployment. Historical player accounts,
private logs, and operator shell scripts are not copied into the runtime image.

## Stop, restart, and preserve characters

Use `save` or `quit` before restarting:

```sh
docker compose stop
docker compose start
docker compose restart game
docker compose down
```

The named Docker volume retains the game runtime, including players and their
backups, notes, clan state, and editable area/configuration files. `down` retains
it; **`docker compose down -v` deletes it**. Do not use `-v` to update the game.

The entire writable runtime shares one filesystem because the original save
code atomically renames `areas/romtmp` into `player/<name>`. Separate volumes
for those directories would break saving.

New image assets initialize an empty volume only. Rebuilding the image does not
overwrite an existing world's saved state or modified assets.

Inspect status and logs with `docker compose ps` and `docker compose logs
--tail=100 game web-proxy web`. Game log timestamps use America/Los_Angeles.

To back up a stopped world without exposing its plaintext passwords in logs:

```sh
docker compose stop
umask 077
docker compose run --rm -T --no-deps --entrypoint tar game -C /var/lib/fd -czf - . > fd-backup.tar.gz
docker compose start
```

Keep the archive private. To restore, stop the services, keep a backup of the
current state, then extract the selected archive. This replaces matching saved
files, so use it only when you intend to restore that snapshot:

```sh
docker compose stop
docker compose run --rm -T --no-deps --entrypoint tar game -C /var/lib/fd -xzf - < fd-backup.tar.gz
docker compose start
```

## Verify

Python 3 is sufficient for the TCP integration test:

```sh
python3 tests/smoke.py
python3 tests/smoke.py --restart
```

The test creates two synthetic `Smoke...` characters through the real TCP login
flow, walks around, exchanges Cyrillic messages, checks ANSI output, walks to
KPI, confirms both historical areas in the live area list, and checks that a
saved title survives logout/login. `--restart` also restarts the game container
and checks persistence across that restart. It disconnects other players.
The test never deletes character data and leaves its synthetic characters in
the volume. Passwords are generated in memory and not printed.

Verified locally on October 24, 2026:

- The TCP test passed with `--restart`, including the walk to KPI and saved
  character state after the game container restarted.
- Isolated Chromium 155 and WebKit 26.6 browsers created fresh characters,
  moved north/south, exchanged Cyrillic chat in both directions (including
  lowercase `я`), rendered ANSI colors, and used arrow-key command history.
- Both browsers hid passwords, kept them out of terminal output/history, and
  accepted a password beginning with `{`. After the final proxy update, both
  used the Reconnect link, logged in again, and displayed their saved titles.
- A synthetic local character temporarily granted trust 102 entered room 26201
  and displayed the original Shadows hall. Its exact ordinary-player save was
  restored, and a new login confirmed the administrator command was unavailable.

WebKit verification exercises Safari's browser engine, not the installed Safari
application. Mobile layouts and public deployment were not tested.

## Historical places

- `areas/kpi.are` is in the boot list and covers vnums 25000–25199. From the
  starting school entrance: `down`, `south` eight times, `east`, `south`, `up`,
  `east`, `north` twice reaches **Первый корпус КПИ** (room 25001).
- `areas/shadows.are` is in the boot list and covers vnums 26200–26249.
  **Зал Теней** is room 26201. The preserved world has no inbound walking route
  from the starting area to this clan hall, and its `clans.dat` no longer has a
  Shadows clan entry. A fresh ordinary character therefore cannot simply walk
  into the hall. A local administrator can inspect it with `goto 26201`.
  The world and clan descriptions are preserved; no new doors, historical
  accounts, or invented clan memberships are added.

## Scope

The upstream master remains available separately. This branch starts directly
from the initial import, so compatibility changes are reviewable with:

```sh
git diff 49136aeadc582c535682fdd781d89a476ea3b046 -- mud
```

Compatibility changes cover modern Linux declarations/build rules, allocation
bookkeeping, byte-safe legacy text loading, the final song's inline terminator,
and Telnet negotiation/escaping/password echo. The unused FreeBSD module loader
is disabled. Connections use numeric peer addresses so reverse DNS cannot block
the single-threaded game loop. Runtime configuration disables the historical
`test`, `file`, and `srcwrite` commands; no player accounts are promoted by default.

The browser uses the existing Maldorne client and proxy. Exact upstream commits,
licenses, integration patches, and proxy security tests are documented in
[web/README.md](web/README.md).

The local implementation does not provision cloud resources or change DNS.
The original Diku, Merc, ROM, and Forgotten Dungeon credits must be retained.
