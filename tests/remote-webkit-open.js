// Start remote-connect-proxy.py, configure that proxy, and open about:blank
// with an isolated, serviceWorkers: 'block' WebKit context first.
// This engine's HTTP-auth origin filter fails on default HTTPS port 443.
// Native challenge handling remains enabled. The proxy confines redirects too;
// Playwright routes alone cannot enforce destination restrictions on redirects.
async (page) => {
  if (page.url() !== 'about:blank') throw new Error('Start in a fresh about:blank context');
  const context = page.context();
  await context.route('**/*', route =>
    new URL(route.request().url()).origin === 'https://fd.dreamiurg.net'
      ? route.continue() : route.abort());
  // Only foreign sockets are intercepted. The game's allowed socket stays native.
  await context.routeWebSocket(url => url.origin !== 'wss://fd.dreamiurg.net',
    socket => socket.close());
  const response = await page.goto('https://fd.dreamiurg.net/');
  if (response.status() !== 200) throw new Error('Authenticated WebKit navigation failed');
  await page.waitForFunction(() => document.body.innerText.includes('Select your codepage:'));
  return { status: response.status(), nativeWebSocketGreeting: true, destinationRestricted: true };
}
