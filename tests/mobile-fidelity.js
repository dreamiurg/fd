// Run with playwright-cli run-code --filename tests/mobile-fidelity.js.
// Run before character creation to check the real startup banner.
async (page) => {
  await page.waitForFunction(() => document.body.innerText.includes('Select your codepage:'));
  const actual = (await page.locator('.xterm-rows > div').allTextContents()).map(row => row.trimEnd());
  // The original server emits this 79-column row (including trailing spaces).
  const banner = '   +--------------------------------------------------+        |_=_=_=_=_=_|   ';
  if (!actual.includes(banner.trimEnd()))
    throw new Error('The original 79-column ASCII banner wrapped or was clipped');
  if (!actual.includes(' 2 Windows-1251         |=_ |+|+|   |= -  -_,--,_     -|_= |+|+|   |  -_  |'))
    throw new Error('The codepage row lost its original ASCII alignment');
  return { bannerColumns: banner.length, originalRowsIntact: true };
}
