import assert from 'node:assert/strict';
import test from 'node:test';
import { once } from 'node:events';
import { WebSocket } from 'ws';
import { Router } from './dist/router.js';
import { loadConfig } from './dist/config.js';
import { TelnetNegotiator } from './dist/telnet/negotiator.js';
import { Connection } from './dist/connection.js';
import { ProxyServer } from './dist/server.js';

test('only the configured game can be selected', () => {
  const router = new Router({
    ...loadConfig(), enableLegacyRouting: false,
    routes: { fd: { host: 'game', port: 4000, encoding: 'windows-1251' } },
  });
  assert.equal(router.resolve({ mud: 'fd', host: 'example.org', port: 80 }).host, 'game');
  for (const mud of ['unknown', '__proto__', 'constructor']) {
    assert.throws(() => router.resolve({ mud }), /Unknown MUD/);
  }
  assert.throws(() => router.resolve({ host: 'example.org', port: 80 }), /legacy routing is disabled/);
});

test('password negotiation reaches the browser and can be toggled repeatedly', () => {
  const messages = [];
  const connection = { passwordMode: false, remoteAddress: 'test', sendJsonToClient: m => messages.push(m) };
  const parser = new TelnetNegotiator(loadConfig());
  try {
    for (const verb of [251, 252, 251]) {
      parser.processServerData(Buffer.from([255, verb, 1]), connection);
    }
    assert.deepEqual(messages, [{ passwordMode: true }, { passwordMode: false }, { passwordMode: true }]);
    assert.equal(connection.passwordMode, true);
  } finally {
    parser.destroy();
  }
});

test('Cyrillic input is encoded and literal IAC is escaped on the Telnet wire', () => {
  const writes = [];
  const connection = {
    tcp: { writable: true, write: b => writes.push(b) },
    encoding: 'windows-1251', utf8: false, passwordMode: false,
  };
  Connection.prototype.forwardToMud.call(connection, Buffer.from('я Я\r\n'));
  assert.deepEqual([...Buffer.concat(writes)], [255, 255, 32, 223, 13, 10]);
});

for (const [kind, password] of [
  ['invalid JSON', '{throwaway-password\r\n'],
  ['control-shaped JSON', '{"connect":1,"host":"example.org","port":80,"encoding":"utf8"}\r\n'],
]) {
  test(`passwords containing ${kind} remain raw game input`, () => {
    const forwarded = [];
    let controlCalls = 0;
    const connection = {
      passwordMode: true,
      encoding: 'windows-1251',
      forwardToMud: raw => forwarded.push(Buffer.from(raw)),
      connectToMud: () => controlCalls++,
    };
    Connection.prototype.handleClientMessage.call(connection, Buffer.from(password));
    assert.deepEqual(forwarded, [Buffer.from(password)]);
    assert.equal(controlCalls, 0);
    assert.equal(connection.encoding, 'windows-1251');
  });
}

test('oversized WebSocket messages are rejected before game input parsing', { timeout: 5000 }, async () => {
  const proxy = new ProxyServer({
    ...loadConfig(), wsPort: 0, chat: { enabled: false, maxLogSize: 0 },
  });
  const listening = once(proxy.httpServer, 'listening');
  proxy.start();
  await listening;
  const client = new WebSocket(`ws://127.0.0.1:${proxy.httpServer.address().port}`);
  try {
    await once(client, 'open');
    const closed = once(client, 'close');
    client.send('x'.repeat(64 * 1024 + 1));
    const result = await Promise.race([
      closed,
      new Promise(resolve => setTimeout(() => resolve([null]), 500)),
    ]);
    assert.equal(result[0], 1009);
  } finally {
    client.terminate();
    await proxy.shutdown();
  }
});
