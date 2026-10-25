# Deployment acceptance

The deployment is running at https://fd.dreamiurg.net. The original protected
deployment passed remote HTTPS boundaries,
Chromium and WebKit gameplay, mobile WebKit, restart, redeployment, VM reboot,
backup, and isolated restore on 2026-10-24/25 (America/Los_Angeles).
Physical iPhone hardware remains untested. Local Telnet and both desktop engines
also passed the earlier local milestone.

The remote checks use fresh synthetic characters and isolated browser profiles.
They never read historical player files or modify the local game volume. Use a
unique, disposable game password: the historical server saves game passwords as
plaintext. The website is public; character passwords remain required.

## Repeat the boundary checks

```sh
python3 tests/remote-boundary.py --expected-ip <deployed-elastic-ip>
```

Supply the address from AWS metadata or an authoritative Route53 A response;
record which source was used. The check verifies all recursive DNS addresses
against that address, the HTTP redirect, trusted TLS, public site and `/health`,
a WebSocket upgrade without credentials, rejection of foreign browser origins
before application data, and inaccessible public port 4000. The pinned proxy
checks Origin after HTTP upgrade and immediately closes rejected connections;
an HTTP 101 alone does not establish game access. Certificate timestamps in its
output are converted to America/Los_Angeles.

## Repeat browser acceptance

Use Playwright CLI with fresh isolated Chromium and WebKit contexts, without
HTTP credentials or a proxy. Keep certificate verification enabled. For mobile
WebKit, use a 390 × 844 viewport, `isMobile: true`, and `hasTouch: true`. Open
https://fd.dreamiurg.net directly; no shared website password is required.

After opening the website, run
`tests/remote-browser.js` using Playwright CLI `run-code --filename`.
The first phase creates a new character. Later phases
are selected through `eval 'window.__fdPhase = "play"'` before running the file
again. Synthetic game credentials remain in that isolated browser's memory;
the script returns only nonsecret evidence.

| Phase | Evidence |
| --- | --- |
| `create` | Complete character creation; password input masked and absent from terminal |
| `play` | Command history excludes password; ANSI colors; north/south movement; Cyrillic `я` |
| `peer` | Set `window.__fdPeerMessage` to the other session's returned message; verify receipt |
| `areas` | Runtime lists KPI and Shadows; separate disposable character walks into KPI room 25003 |
| `save` | Set title, explicitly save, and quit |
| `checkpoint` | Set a new title while online without explicitly saving |
| `relogin` | Use the visible Reconnect link, log in, and verify the retained title |
| `mobile` | Touch Send button, no horizontal overflow, input visible after viewport reduction |
| `quit` | Leave the test character safely |

Set `window.__fdUseSendButton = true` before mobile creation. Run creation,
play, mobile layout, save, and reconnect in that context. Viewport reduction
simulates the space occupied by a keyboard; it does not prove physical iPhone
keyboard behavior. An installed Safari application and physical iPhone remain
unverified unless separately recorded below.

Run the area tour in a separate desktop session. The original KPI park contains
aggressive mobs that can kill a level-one character; the test stops at the first
KPI room, `Перекресток в парке` (25003). The world is preserved unchanged.
Shadows remains disconnected from ordinary walking. Its hall was verified with
a temporary synthetic administrator locally; remote acceptance checks its
runtime area listing without creating new world connections or admin accounts.

## Restart, deployment, reboot, and restore

Coordinate maintenance before disconnecting any active players. The fixed
operations workflow is `fd-operations.yml` in `dreamiurg/terraform-aws-personal`.
Use `checkpoint` immediately before each restart, deployment, or reboot, then
`relogin` afterward. Record the release and kernel boot ID from `status`; an
actual reboot must change the boot ID. Verify both browser sessions afterward.

Run `backup`, then `restore-smoke`. The restore operation downloads the newest
backup into an empty temporary directory, starts an isolated game container
without network access, checks the login greeting, and removes only that
temporary container and directory. It must never restore over live game state.

## Public website acceptance

Release `3578a67690f84ba2425423ac1d8dd152d83e9d09` passed on 2026-10-25
at 09:17–09:22 PDT (timestamps converted to America/Los_Angeles). Redeploy
`40210780484` took a backup before updating; status `40210887761` confirmed the
same data mount, enabled game service, active backup timer, four running
containers, and healthy game.

- Anonymous HTTPS returned 200 for the site and health endpoint, with trusted
  TLS and DNS matching AWS-confirmed EIP `184.33.125.10`. The native WebSocket
  connected without credentials. A foreign Origin received an immediate close
  before application data; public game port 4000 remained unreachable.
- Fresh Chromium 155 and desktop WebKit 26.6 profiles used no HTTP credentials,
  Authorization headers, or proxy. Both created characters, masked game
  passwords, excluded passwords from 24 history entries, rendered seven ANSI
  colors, moved north/south, and displayed Cyrillic including `я`.
- Both desktop engines and mobile WebKit saved, quit, then used Reconnect to
  log in with their character passwords and recover their saved titles. Mobile
  creation and commands used touch Send; the 390 × 844 layout had no horizontal
  overflow and kept input reachable at a reduced 430-pixel height.
- Pre-update synthetic character `Remoteydrspm` was recognized and required a
  masked password. Authenticated login for that older test character was not
  repeated because its deliberately temporary password was no longer retained;
  no password was recovered or reset.

Screenshots are ignored local artifacts:
`output/playwright/public-chromium-final.png`,
`output/playwright/public-webkit-final.png`, and
`output/playwright/public-mobile-final.png`. All isolated test browsers were
closed after safe logout. Physical iPhone hardware remains untested; mobile
results are WebKit emulation. The earlier reboot/restore suite was not repeated
for this website authentication change.

## Original protected deployment results

The results below describe the earlier release with its shared HTTP gate.
They are historical evidence; current public-access checks are described above.

Local mobile preflight passed on 2026-10-24 in isolated WebKit 26.6 at
390 × 844: fresh creation using native touch taps on Send, masked password and
password-free command history, Cyrillic, seven rendered colors, movement,
no horizontal overflow, reachable input at a reduced 430-pixel height, and
save/quit/reconnect with the saved title preserved. Screenshot:
`output/playwright/mobile-reconnected.png` (ignored local artifact).

Terminal scrollback responded to a DOM wheel event. Playwright's mobile WebKit
does not provide native wheel or touch-swipe automation; native iPhone touch
scrolling and its real keyboard remain unverified. This preflight used a separate
temporary local stack and did not change the user's original local game.

Remote checks on 2026-10-24/25 (America/Los_Angeles):

- Release `0c348dce83dd84ec7ab1182393a245a9594ab045` on instance
  `i-0611e74c112d8f662`, EIP `184.33.125.10`, Oregon `t3a.micro`.
- Trusted TLS and DNS matched the AWS metadata. Missing/wrong gate credentials
  returned 401; authenticated site returned 200 and WebSocket upgraded with 101.
  HTTP redirected to standard HTTPS; public TCP port 4000 was unreachable.
- Chromium created a synthetic character, hid its password, excluded it from
  24 history entries, rendered seven colors, moved north/south, and sent Cyrillic
  including `я`. A separate character verified both runtime area names and walked
  to KPI room 25003. Screenshot: `output/playwright/remote-kpi.png`.
- Restart run `40170947495` and same-release redeploy `40171038434` passed.
  Chromium logged back in with each title set before maintenance retained; these
  titles were not explicitly saved before the operations.
- Actual VM reboot `40171159704` changed boot ID from
  `c3016a8a-e9a6-431f-8ced-7400029fd58a` to
  `ebce9d38-e17a-440a-9a29-3edd14b3ebbd`. Status `40171237759` confirmed automatic
  startup, enabled service, all four running containers, healthy game, and the
  same release and data UUID `2206692a-5dce-4e4e-8ef5-71c7215d0125`. Chromium
  reconnected with the pre-reboot title retained.
- Backup `40171332397` and isolated restore `40171389997` passed. The restored
  copy matched 140 files byte-for-byte, including two synthetic player saves,
  and served the game login menu without network access. No live restore occurred.
- Runtime evidence: `output/playwright/remote-post-reboot-status.txt` and
  `output/playwright/remote-restore-result.txt`; timestamps converted to PDT.
- AWS catalog pricing was verified as $12.91 per 730-hour month for compute,
  30 GiB gp3 storage, and one public IPv4 address, plus small backup/DNS charges.

Two isolated Chromium sessions also passed bidirectional room chat and private
`tell`/reply with Cyrillic, followed by save/quit/reconnect. Screenshots:
`output/playwright/remote-chromium-chat.png` and
`output/playwright/remote-peer-chat.png`.

The final fixed-tunnel runs passed on desktop WebKit and mobile WebKit at
390 × 844: fresh creation, masked password, 24 password-free history entries,
seven rendered colors, movement, Cyrillic, and cross-browser chat. Mobile creation
and commands used touch taps on Send; input stayed reachable at 430-pixel height,
with no horizontal overflow. Earlier remote save/quit/reconnect also passed.

Shared reboot `40172435164` then preserved the titles of all three online test
characters without explicit saves. Chromium, desktop WebKit, and mobile WebKit
all reconnected through the visible UI and verified their respective titles.
Final status `40172554987` passed with boot ID
`bb68fda5-cf8a-46e3-bb6b-3b6e8def84d8`, enabled service, healthy game, four running
containers, and the unchanged release/data mount. Cloud-init reported `done`
after this normal reboot; no historical error record was manually cleared.
The final HTTPS/DNS/gate/WebSocket/public-port boundary check passed again.

Final evidence:

- `output/playwright/remote-webkit-final.png`
- `output/playwright/remote-mobile-final.png`
- `output/playwright/remote-final-status.txt` (timestamps converted to PDT)

These are ignored local artifacts. The mobile result is browser emulation;
physical iPhone Safari, its real keyboard, and native swipe scrolling remain
unverified. The earlier WebKit Basic Auth automation workaround is no longer
needed with public website access.
