# Local browser client

This integrates existing GPL-3.0-or-later projects, without replacing their clients:

- [maldorne/mud-web-client](https://github.com/maldorne/mud-web-client/tree/ca4b94caf03c265c72c181f4949e6ef2c7c15c18), version 4.1.0, commit `ca4b94caf03c265c72c181f4949e6ef2c7c15c18`.
- [maldorne/mud-web-proxy](https://github.com/maldorne/mud-web-proxy/tree/6459d115f0cabda3b7a25580cf8dd022a7582bde), version 4.0.0, commit `6459d115f0cabda3b7a25580cf8dd022a7582bde`.

Docker downloads the exact commits, applies the reviewable patches in this directory, and uses their npm lockfiles. The original license notices remain in each image; the client notice is available at `/LICENSE-client.txt`. The linked commit trees plus these patches provide the corresponding source. The build stages remain available for rebuilding or inspecting it.

The browser uses one same-origin WebSocket endpoint (`/ws`). The proxy allows only the named `fd` route to `game:4000`; client-provided host/port values cannot select a destination. The proxy converts Windows-1251 to UTF-8 in both directions. Select `2` at the game's initial codepage prompt. Do not select another codepage in this client.

The patches set Forgotten Dungeon defaults and a small reconnect header, propagate Telnet password-mode changes, exclude passwords from history, preserve literal Cyrillic `я` on the Telnet wire, and reject inherited JavaScript property names as routes. They retain the upstream terminal, ANSI renderer, scrollback, command history, and clipboard handling.

`proxy.test.mjs` runs during the proxy image build and verifies fixed routing, repeated password-mode changes, CP1251/Telnet byte encoding, literal passwords that resemble JSON controls, and rejection of WebSocket messages over 64 KiB. Browser acceptance tests exercise the actual game separately. Reconnect starts a new login session; no password is stored or automatically resent.

The proxy patch pins Zod to `4.6.6`, including its npm lockfile integrity, fixing [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5). No other dependency versions were changed. Upstream's unused `@eslint/js` package is classified as a development dependency so ESLint and its tools are excluded from the runtime image. The October 24, 2026 runtime audit (`npm audit --omit=dev`) reports **zero vulnerabilities**.

The full build-stage dependency audit still reports six tooling findings: `@humanfs/node` (moderate), `brace-expansion` (high), `diff` (low), `js-yaml` (high), `mocha` (moderate), and `serialize-javascript` (high). These packages are excluded from the runtime image; broader upstream tooling upgrades are deferred. This is a local-only deployment, not a public-service security audit.
