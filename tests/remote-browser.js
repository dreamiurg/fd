// Run with playwright-cli run-code --filename tests/remote-browser.js.
// Select a phase with: playwright-cli eval 'window.__fdPhase = "play"'.
async (page) => {
  const phase = await page.evaluate(() => window.__fdPhase || 'create');
  const input = page.locator('input[aria-label="Game command"]');
  const useSendButton = await page.evaluate(() => Boolean(window.__fdUseSendButton));
  const waitText = (text) => page.waitForFunction(t => document.body.innerText.replace(/\s+/g, '')
    .includes(t.replace(/\s+/g, '')), text);
  const send = async (text) => {
    await input.fill(text);
    if (useSendButton) await page.getByRole('button', { name: 'Send', exact: true }).tap();
    else await input.press('Enter');
  };
  const step = async (text, expected) => { await send(text); await waitText(expected); };
  const screen = () => page.locator('.xterm-rows').innerText();
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  let character = await page.evaluate(() => window.__fdCharacter);
  let sequence = 0;
  const prefix = 'CHECK' + Math.random().toString(36).slice(2, 8);
  const command = async (text) => {
    const start = prefix + (++sequence) + 'S>';
    const end = prefix + sequence + 'E>';
    const waitPrompt = (prompt) => page.waitForFunction(p => Array.from(document.querySelectorAll('.xterm-rows > div'))
      .some(row => row.textContent.trim() === p), prompt);
    await send('prompt ' + start);
    await waitPrompt(start);
    await send(text);
    await send('prompt ' + end);
    await waitPrompt(end);
    const rendered = await screen();
    // The marker occurs in its command echo, before the response, and after it.
    // If only the final marker remains, all older rows have scrolled out already.
    const markers = rendered.split(start).length - 1;
    return markers >= 2 ? rendered.slice(rendered.indexOf(start) + start.length) : rendered;
  };
  const hiddenPassword = async () => {
    await page.waitForFunction(() => document.querySelector('[aria-label="Game command"]').type === 'password');
    await send(character.password);
  };

  if (phase === 'create') {
    character = await page.evaluate(() => {
      const bytes = crypto.getRandomValues(new Uint8Array(24));
      const name = 'Remote' + Array.from(bytes.slice(0, 6), b => String.fromCharCode(97 + b % 26)).join('');
      return { name, password: '{' + Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('') };
    });
    await page.evaluate(c => { window.__fdCharacter = c; }, character);
    await waitText('Select your codepage:');
    await step('2', 'странник:');
    await step(character.name, '(Y/N)?');
    await step('y', 'Введи пароль');
    await hiddenPassword();
    await waitText('еще раз:');
    await hiddenPassword();
    await waitText('Какой ты расы');
    await page.waitForFunction(() => document.querySelector('[aria-label="Game command"]').type === 'text');
    for (const [answer, expected] of [
      ['human', 'Какого ты пола'], ['m', 'Выбери класс'], ['warrior', '(G/N/E)?'],
      ['n', 'Вручную (Y/N)?'], ['n', 'Твой выбор?'], ['sword', 'Нажми ENTER для продолжения'],
      ['', 'Вход в Школу'],
    ]) await step(answer, expected);
    await command('scroll 0');
    assert(!(await page.locator('body').innerText()).includes(character.password), 'Password appeared in terminal');
    return { phase, name: character.name, created: true, passwordMasked: true };
  }

  assert(character, 'Run create in this browser session first');

  if (phase === 'play') {
    const history = [];
    for (let i = 0; i < 24; i++) {
      await input.press('ArrowUp');
      const value = await input.inputValue();
      assert(value !== character.password, 'Password appeared in history');
      history.push(value);
    }
    assert(history.includes('scroll 0'), 'Command history did not retain commands');
    await input.press('ArrowDown');
    if ((await command('colour')).replace(/\s+/g, '').includes('Цветавыключены.'))
      await command('colour');
    const colors = await page.locator('.xterm-rows span').evaluateAll(spans =>
      [...new Set(spans.map(span => getComputedStyle(span).color))]);
    assert(colors.length >= 4, 'ANSI colors were not rendered');
    assert((await command('north')).includes('Комната в Школе'), 'North did not reach the school room');
    assert((await command('south')).includes('Вход в Школу'), 'South did not return to the school entrance');
    assert(!(await command('acceptanceboundarycheck')).includes('Вход в Школу'), 'Fresh response contains stale room text');
    const message = character.name + ' Привет, друзья! я здесь';
    await command('say ' + message);
    return { phase, name: character.name, historyEntriesChecked: 24, colors: colors.length, moved: true, message };
  }

  if (phase === 'peer') {
    const message = await page.evaluate(() => window.__fdPeerMessage);
    assert(message, 'Set window.__fdPeerMessage to the other browser message');
    await waitText(message);
    return { phase, name: character.name, received: message };
  }

  if (phase === 'areas') {
    const areas = await command('areas');
    assert(areas.includes('KPI') && areas.includes('Shadows'), 'Required historical areas are not loaded');
    // Use a separate disposable character: the unchanged KPI park has lethal mobs.
    for (const direction of ['down', ...Array(8).fill('south'), 'east', 'south', 'up'])
      await command(direction);
    const arrival = await command('east');
    assert(arrival.includes('Перекресток в парке'), 'Walking route did not enter KPI room 25003');
    return { phase, name: character.name, loaded: ['KPI', 'Shadows'], walkedToKpiRoom: 25003 };
  }

  if (phase === 'mobile') {
    assert(useSendButton, 'Enable window.__fdUseSendButton for touch acceptance');
    const viewport = page.viewportSize();
    const checkLayout = async () => page.evaluate(() => {
      const input = document.querySelector('[aria-label="Game command"]').getBoundingClientRect();
      const height = window.visualViewport?.height || innerHeight;
      return { width: innerWidth, height, inputTop: input.top, inputBottom: input.bottom,
        horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1 };
    });
    await command('look');
    let layout = await checkLayout();
    assert(!layout.horizontalOverflow, 'Mobile page overflows horizontally');
    assert(layout.inputTop >= 0 && layout.inputBottom <= layout.height + 1, 'Mobile input is unreachable');
    assert(await input.evaluate(element => parseFloat(getComputedStyle(element).fontSize) >= 16), 'Mobile input text risks focus zoom');
    const sendBox = await page.getByRole('button', { name: 'Send', exact: true }).boundingBox();
    assert(sendBox.height >= 44 && sendBox.width >= 44, 'Send touch target is too small');
    await page.setViewportSize({ width: viewport.width, height: 430 });
    await input.tap();
    await command('say Мобильная проверка я');
    layout = await checkLayout();
    assert(!layout.horizontalOverflow && layout.inputTop >= 0 && layout.inputBottom <= layout.height + 1,
      'Input became unreachable in the simulated keyboard viewport');
    await page.setViewportSize(viewport);
    return { phase, name: character.name, touchSend: true, noHorizontalOverflow: true,
      reducedViewportInputVisible: true, physicalIphoneTested: false };
  }

  if (phase === 'save') {
    character.title = 'RemoteSaved' + Math.random().toString(36).slice(2, 9);
    await page.evaluate(c => { window.__fdCharacter = c; }, character);
    await command('title ' + character.title);
    assert((await command('save')).includes('Хранители Знаний'), 'Game did not acknowledge save');
    await step('quit', 'Все хорошее рано или поздно заканчивается');
    return { phase, name: character.name, savedTitle: character.title, quit: true };
  }

  if (phase === 'checkpoint') {
    character.title = 'RemoteUnsaved' + Math.random().toString(36).slice(2, 9);
    await page.evaluate(c => { window.__fdCharacter = c; }, character);
    await command('title ' + character.title);
    assert((await command('who')).replace(/\s+/g, '').includes(character.title), 'Unsaved title was not applied');
    return { phase, name: character.name, title: character.title, online: true, explicitlySaved: false };
  }

  if (phase === 'relogin') {
    assert(character.title, 'Run save before relogin');
    await page.getByRole('link', { name: 'Reconnect', exact: true }).click();
    await page.evaluate(c => { window.__fdCharacter = c; }, character);
    await page.evaluate(value => { window.__fdUseSendButton = value; }, useSendButton);
    await waitText('Select your codepage:');
    await step('2', 'странник:');
    await step(character.name, 'Пароль:');
    await hiddenPassword();
    await waitText('Нажми ENTER для продолжения');
    await page.waitForFunction(() => document.querySelector('[aria-label="Game command"]').type === 'text');
    await step('', 'Добро пожаловать в Forgotten Dungeon');
    await command('scroll 0');
    assert((await command('who')).replace(/\s+/g, '').includes(character.title), 'Saved title did not survive');
    assert(!(await page.locator('body').innerText()).includes(character.password), 'Password appeared after login');
    return { phase, name: character.name, savedTitle: character.title, reconnected: true };
  }

  if (phase === 'quit') {
    await step('quit', 'Все хорошее рано или поздно заканчивается');
    return { phase, name: character.name, quit: true };
  }

  throw new Error('Unknown acceptance phase');
}
