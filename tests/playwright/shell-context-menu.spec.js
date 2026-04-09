const { test, expect } = require('@playwright/test');

function fulfillJson(route, payload) {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function fulfillText(route, payload) {
  return route.fulfill({
    status: 200,
    contentType: 'text/plain; charset=utf-8',
    body: payload,
  });
}

const STRATEGY_SOURCE = `class TestStrategy:\n    stoploss = -0.1\n    timeframe = '5m'\n`;

async function installShellMenuMocks(page, appOrigin) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== appOrigin) return route.continue();

    const { pathname } = url;
    const method = request.method();

    if (method === 'GET' && pathname === '/runs') {
      return fulfillJson(route, { runs: [] });
    }
    if (method === 'GET' && pathname === '/result-metrics') {
      return fulfillJson(route, { metrics: [], groups: { results_table: [] } });
    }
    if (method === 'GET' && pathname === '/strategies') {
      return fulfillJson(route, { strategies: ['TestStrategy'] });
    }
    if (method === 'GET' && pathname === '/strategies/TestStrategy/params') {
      return fulfillJson(route, {
        parameters: [
          { name: 'stoploss', type: 'float', default: -0.1, description: 'Stop loss.' },
        ],
      });
    }
    if (method === 'GET' && pathname === '/strategies/TestStrategy/source') {
      return fulfillText(route, STRATEGY_SOURCE);
    }
    if (method === 'GET' && pathname === '/hyperopt/runs') {
      return fulfillJson(route, { runs: [] });
    }
    if (method === 'GET' && pathname === '/pairs') {
      return fulfillJson(route, {
        local_pairs: ['BTC/USDT'],
        config_pairs: ['BTC/USDT'],
        popular_pairs: ['BTC/USDT'],
      });
    }
    if (method === 'GET' && pathname === '/healthz') {
      return fulfillJson(route, { status: 'ok' });
    }
    if (method === 'GET' && pathname === '/ai/providers') {
      return fulfillJson(route, {
        providers: {
          ollama: {
            available: true,
            models: [{ id: 'ollama-mini', name: 'Ollama Mini' }],
          },
          openrouter: {
            available: true,
            models: [{ id: 'openrouter-mini', name: 'OpenRouter Mini' }],
          },
        },
      });
    }
    if (method === 'GET' && pathname === '/ai/threads') {
      return fulfillJson(route, []);
    }
    if (method === 'GET' && /^\/ai\/threads\/[^/]+$/.test(pathname)) {
      return fulfillJson(route, {
        messages: [],
        goal_id: 'balanced',
        provider: 'openrouter',
        model: 'openrouter-mini',
        context_run_id: null,
      });
    }
    if (method === 'GET' && (pathname === '/ai/conversations' || pathname === '/ai/pipeline-logs')) {
      return fulfillJson(route, []);
    }

    return route.continue();
  });
}

async function gotoView(page, viewName, waitSelector) {
  await page.goto(`/#${viewName}`);
  await page.waitForSelector(`.page-view.active[data-view="${viewName}"]`);
  if (waitSelector) {
    await page.waitForSelector(waitSelector);
  }
}

async function readMenuState(page) {
  return page.locator('.shell-menu__item').evaluateAll((nodes) => nodes.map((node) => ({
    label: (node.textContent || '').trim(),
    disabled: node.hasAttribute('disabled'),
    active: node.classList.contains('is-active'),
  })));
}

async function injectShellMenuFixtures(page) {
  await page.evaluate(() => {
    const active = document.querySelector('.page-view.active');
    if (!active) return;
    let host = document.querySelector('#shell-menu-test-fixtures');
    if (!host) {
      host = document.createElement('div');
      host.id = 'shell-menu-test-fixtures';
      host.innerHTML = `
        <input id="shell-menu-test-input" class="form-input" type="text" value="alpha beta gamma">
        <textarea id="shell-menu-test-textarea" class="form-input" rows="3">delta epsilon zeta</textarea>
        <div id="shell-menu-selection-source">Visible shell selection source</div>
      `;
      active.appendChild(host);
    }
  });
}

async function selectNodeText(page, selector) {
  await page.evaluate((targetSelector) => {
    const el = document.querySelector(targetSelector);
    const selection = window.getSelection();
    if (!el || !selection) return;
    const range = document.createRange();
    range.selectNodeContents(el);
    selection.removeAllRanges();
    selection.addRange(range);
  }, selector);
}

async function dispatchContextMenu(page, selector) {
  await page.evaluate((targetSelector) => {
    const el = document.querySelector(targetSelector);
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.dispatchEvent(new MouseEvent('contextmenu', {
      bubbles: true,
      cancelable: true,
      clientX: rect.left + Math.min(12, Math.max(4, rect.width / 2)),
      clientY: rect.top + Math.min(12, Math.max(4, rect.height / 2)),
    }));
  }, selector);
}

async function installClipboardDenied(page) {
  await page.addInitScript(() => {
    const originalQuery = navigator.permissions?.query?.bind(navigator.permissions);
    Object.defineProperty(navigator, 'permissions', {
      configurable: true,
      value: {
        query: async (descriptor) => {
          if (descriptor && descriptor.name === 'clipboard-read') {
            return {
              state: 'denied',
              onchange: null,
              addEventListener() {},
              removeEventListener() {},
              dispatchEvent() { return true; },
            };
          }
          if (originalQuery) return originalQuery(descriptor);
          return {
            state: 'prompt',
            onchange: null,
            addEventListener() {},
            removeEventListener() {},
            dispatchEvent() { return true; },
          };
        },
      },
    });
  });
}

async function installCodeMirrorDisabled(page) {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'CodeMirror', {
      configurable: true,
      get() {
        return undefined;
      },
      set() {},
    });
  });
}

async function installFakeCodeMirror(page) {
  await page.addInitScript(() => {
    function indexToPos(value, index) {
      const lines = String(value).split('\n');
      let remaining = index;
      for (let line = 0; line < lines.length; line += 1) {
        const lineLength = lines[line].length;
        if (remaining <= lineLength) return { line, ch: remaining };
        remaining -= lineLength + 1;
      }
      return { line: lines.length - 1, ch: lines[lines.length - 1].length };
    }

    function posToIndex(value, pos) {
      const lines = String(value).split('\n');
      let index = 0;
      for (let line = 0; line < pos.line; line += 1) {
        index += lines[line].length + 1;
      }
      return index + pos.ch;
    }

    class FakeCodeMirrorEditor {
      constructor(host, options = {}) {
        this._value = String(options.value || '');
        this._options = { ...options };
        this._undo = [];
        this._redo = [];
        this._listeners = { change: [] };
        this._selections = [{ anchor: { line: 0, ch: 0 }, head: { line: 0, ch: 0 } }];
        this._wrapper = document.createElement('div');
        this._wrapper.className = 'CodeMirror';
        this._textarea = document.createElement('textarea');
        this._textarea.className = 'CodeMirror__input';
        this._textarea.value = this._value;
        this._wrapper.appendChild(this._textarea);
        this._wrapper.CodeMirror = this;
        host.appendChild(this._wrapper);
        this._applySelection();
      }

      _emitChange() {
        this._listeners.change.forEach((handler) => handler(this));
      }

      _snapshotSelection() {
        return this._selections.map((item) => ({
          anchor: { ...item.anchor },
          head: { ...item.head },
        }));
      }

      _pushUndo() {
        this._undo.push({ value: this._value, selections: this._snapshotSelection() });
        this._redo = [];
      }

      _applySelection() {
        const current = this._selections[0];
        const start = posToIndex(this._value, current.anchor);
        const end = posToIndex(this._value, current.head);
        this._textarea.selectionStart = Math.min(start, end);
        this._textarea.selectionEnd = Math.max(start, end);
      }

      on(name, handler) {
        this._listeners[name] = this._listeners[name] || [];
        this._listeners[name].push(handler);
      }

      historySize() {
        return { undo: this._undo.length, redo: this._redo.length };
      }

      getOption(name) {
        return this._options[name];
      }

      getValue() {
        return this._value;
      }

      setValue(nextValue) {
        this._pushUndo();
        this._value = String(nextValue || '');
        this._textarea.value = this._value;
        const end = indexToPos(this._value, this._value.length);
        this._selections = [{ anchor: end, head: end }];
        this._applySelection();
        this._emitChange();
      }

      lineCount() {
        return this._value.split('\n').length;
      }

      getLine(line) {
        return this._value.split('\n')[line] || '';
      }

      markText() {
        return { clear() {} };
      }

      listSelections() {
        return this._snapshotSelection();
      }

      setSelections(selections) {
        this._selections = selections.map((item) => ({
          anchor: { ...item.anchor },
          head: { ...item.head },
        }));
        this._applySelection();
      }

      setSelection(anchor, head) {
        this.setSelections([{ anchor, head }]);
      }

      getCursor(which) {
        const current = this._selections[0];
        return which === 'to' ? current.head : current.anchor;
      }

      somethingSelected() {
        const current = this._selections[0];
        return current.anchor.line !== current.head.line || current.anchor.ch !== current.head.ch;
      }

      getSelection() {
        const current = this._selections[0];
        const start = posToIndex(this._value, current.anchor);
        const end = posToIndex(this._value, current.head);
        return this._value.slice(Math.min(start, end), Math.max(start, end));
      }

      replaceSelection(text) {
        const current = this._selections[0];
        const start = posToIndex(this._value, current.anchor);
        const end = posToIndex(this._value, current.head);
        this._pushUndo();
        this._value = `${this._value.slice(0, Math.min(start, end))}${text}${this._value.slice(Math.max(start, end))}`;
        this._textarea.value = this._value;
        const next = indexToPos(this._value, Math.min(start, end) + String(text).length);
        this._selections = [{ anchor: next, head: next }];
        this._applySelection();
        this._emitChange();
      }

      execCommand(command) {
        if (command === 'selectAll') {
          const end = indexToPos(this._value, this._value.length);
          this._selections = [{ anchor: { line: 0, ch: 0 }, head: end }];
          this._applySelection();
        }
      }

      focus() {
        this._textarea.focus();
      }

      refresh() {}

      undo() {
        const previous = this._undo.pop();
        if (!previous) return;
        this._redo.push({ value: this._value, selections: this._snapshotSelection() });
        this._value = previous.value;
        this._textarea.value = this._value;
        this._selections = previous.selections;
        this._applySelection();
        this._emitChange();
      }

      redo() {
        const next = this._redo.pop();
        if (!next) return;
        this._undo.push({ value: this._value, selections: this._snapshotSelection() });
        this._value = next.value;
        this._textarea.value = this._value;
        this._selections = next.selections;
        this._applySelection();
        this._emitChange();
      }
    }

    const fakeCodeMirror = function fakeCodeMirror(host, options) {
      return new FakeCodeMirrorEditor(host, options);
    };

    fakeCodeMirror.MergeView = function mergeView(host, options) {
      const editor = new FakeCodeMirrorEditor(host, options);
      return {
        editor: () => editor,
        leftOriginal: () => editor,
      };
    };

    Object.defineProperty(window, 'CodeMirror', {
      configurable: true,
      get() {
        return fakeCodeMirror;
      },
      set() {},
    });
  });
}

test.describe('Shell context menu', () => {
  test('opens from mouse and keyboard, clamps to the viewport, and closes on dismiss triggers', async ({ page, baseURL }) => {
    const appOrigin = new URL(baseURL || 'http://127.0.0.1:8000').origin;
    await installShellMenuMocks(page, appOrigin);

    await page.setViewportSize({ width: 900, height: 700 });
    await gotoView(page, 'dashboard', '#dash-stats');

    const contentBox = await page.locator('[data-page-content]').boundingBox();
    await page.mouse.click(contentBox.x + contentBox.width - 3, contentBox.y + contentBox.height - 3, { button: 'right' });

    const panel = page.locator('.shell-menu__panel');
    await expect(panel).toBeVisible();
    const panelBox = await panel.boundingBox();
    expect(panelBox.x + panelBox.width).toBeLessThanOrEqual(900);
    expect(panelBox.y + panelBox.height).toBeLessThanOrEqual(700);

    await page.locator('[data-topbar]').click({ button: 'right', modifiers: ['Shift'] });
    await expect(panel).toBeHidden();

    const refreshButton = page.locator('#topbar-refresh-btn');
    await refreshButton.focus();
    await page.keyboard.press('Shift+F10');
    await expect(panel).toBeVisible();
    await expect.poll(() => readMenuState(page).then((items) => items.find((item) => item.active)?.label || '')).toBe('Refresh View');

    await page.keyboard.press('ArrowDown');
    await expect.poll(() => readMenuState(page).then((items) => items.find((item) => item.active)?.label || '')).toBe('Reload App');
    await page.keyboard.press('Escape');
    await expect(panel).toBeHidden();

    await page.keyboard.press('ContextMenu');
    await expect(panel).toBeVisible();
    await page.mouse.click(24, 24);
    await expect(panel).toBeHidden();

    await page.keyboard.press('ContextMenu');
    await expect(panel).toBeVisible();
    await page.evaluate(() => window.dispatchEvent(new Event('blur')));
    await expect(panel).toBeHidden();

    await page.keyboard.press('ContextMenu');
    await expect(panel).toBeVisible();
    await page.evaluate(() => {
      document.querySelector('[data-page-content]')?.dispatchEvent(new Event('scroll', { bubbles: true }));
    });
    await expect(panel).toBeHidden();
  });

  test('shows editable actions for native inputs, textareas, AI textarea, and Strategy Lab fallback textarea', async ({ page, baseURL }) => {
    const appOrigin = new URL(baseURL || 'http://127.0.0.1:8000').origin;
    await installClipboardDenied(page);
    await installCodeMirrorDisabled(page);
    await installShellMenuMocks(page, appOrigin);

    await gotoView(page, 'dashboard', '#dash-stats');
    await injectShellMenuFixtures(page);

    await page.evaluate(() => {
      const input = document.querySelector('#shell-menu-test-input');
      input.focus();
      input.setSelectionRange(0, 5);
    });
    await page.locator('#shell-menu-test-input').click({ button: 'right' });
    let items = await readMenuState(page);
    expect(items.map((item) => item.label)).toEqual([
      'Undo', 'Redo', 'Cut', 'Copy', 'Paste', 'Select All',
      'Refresh View', 'Reload App', 'Hard Reload', 'Empty Cache + Hard Reload',
    ]);
    expect(items.find((item) => item.label === 'Paste')?.disabled).toBe(true);
    await page.keyboard.press('Escape');

    await page.evaluate(() => {
      const textarea = document.querySelector('#shell-menu-test-textarea');
      textarea.focus();
      textarea.setSelectionRange(0, 5);
    });
    await page.locator('#shell-menu-test-textarea').click({ button: 'right' });
    items = await readMenuState(page);
    expect(items.slice(0, 6).map((item) => item.label)).toEqual(['Undo', 'Redo', 'Cut', 'Copy', 'Paste', 'Select All']);
    expect(items.find((item) => item.label === 'Paste')?.disabled).toBe(true);
    await page.keyboard.press('Escape');

    await gotoView(page, 'ai-diagnosis', '#ai-textarea');
    await page.fill('#ai-textarea', 'AI editable text');
    await page.evaluate(() => {
      const textarea = document.querySelector('#ai-textarea');
      textarea.focus();
      textarea.setSelectionRange(0, 2);
    });
    await page.locator('#ai-textarea').click({ button: 'right' });
    items = await readMenuState(page);
    expect(items.slice(0, 6).map((item) => item.label)).toEqual(['Undo', 'Redo', 'Cut', 'Copy', 'Paste', 'Select All']);
    expect(items.find((item) => item.label === 'Paste')?.disabled).toBe(true);
    await page.keyboard.press('Escape');

    await gotoView(page, 'strategy-lab', '#sl-list');
    await page.locator('[data-strategy="TestStrategy"]').click();
    await page.locator('#sl-toggle-editor-btn').click();
    await page.waitForSelector('#sl-source-textarea');
    await page.evaluate(() => {
      const textarea = document.querySelector('#sl-source-textarea');
      textarea.focus();
      textarea.setSelectionRange(0, 5);
    });
    await page.locator('#sl-source-textarea').click({ button: 'right' });
    items = await readMenuState(page);
    expect(items.slice(0, 6).map((item) => item.label)).toEqual(['Undo', 'Redo', 'Cut', 'Copy', 'Paste', 'Select All']);
    expect(items.find((item) => item.label === 'Paste')?.disabled).toBe(true);
  });

  test('shows editable actions for Strategy Lab CodeMirror and keeps unsupported items disabled', async ({ page, baseURL }) => {
    const appOrigin = new URL(baseURL || 'http://127.0.0.1:8000').origin;
    await installFakeCodeMirror(page);
    await installShellMenuMocks(page, appOrigin);
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin: appOrigin });

    await gotoView(page, 'strategy-lab', '#sl-list');
    await page.locator('[data-strategy="TestStrategy"]').click();
    await page.locator('#sl-toggle-editor-btn').click();
    await page.waitForSelector('.CodeMirror');

    await page.evaluate(async () => {
      await navigator.clipboard.writeText('pasted-from-clipboard');
      const editor = document.querySelector('.CodeMirror').CodeMirror;
      editor.setSelection({ line: 0, ch: 0 }, { line: 0, ch: 5 });
    });

    await dispatchContextMenu(page, '.CodeMirror');
    const items = await readMenuState(page);
    expect(items.map((item) => item.label)).toEqual([
      'Undo', 'Redo', 'Cut', 'Copy', 'Paste', 'Select All',
      'Refresh View', 'Reload App', 'Hard Reload', 'Empty Cache + Hard Reload',
    ]);
    expect(items.find((item) => item.label === 'Undo')?.disabled).toBe(true);
    expect(items.find((item) => item.label === 'Redo')?.disabled).toBe(true);
    expect(items.find((item) => item.label === 'Paste')?.disabled).toBe(false);
  });

  test('shows selection actions only for visible non-editable text and routes refresh through the active page module', async ({ page, baseURL }) => {
    const appOrigin = new URL(baseURL || 'http://127.0.0.1:8000').origin;
    await installShellMenuMocks(page, appOrigin);

    await gotoView(page, 'dashboard', '#dash-stats');
    await injectShellMenuFixtures(page);

    await page.evaluate(() => {
      window.__shellMenuRefreshCalls = 0;
      const originalRefresh = window.DashboardPage.refresh;
      window.DashboardPage.refresh = function wrappedRefresh(...args) {
        window.__shellMenuRefreshCalls += 1;
        return originalRefresh.apply(this, args);
      };
    });

    await selectNodeText(page, '#shell-menu-selection-source');
    await page.evaluate(() => {
      const el = document.querySelector('#shell-menu-selection-source');
      const rect = el.getBoundingClientRect();
      el.dispatchEvent(new MouseEvent('contextmenu', {
        bubbles: true,
        cancelable: true,
        clientX: rect.left + 8,
        clientY: rect.top + 8,
      }));
    });
    let items = await readMenuState(page);
    expect(items.map((item) => item.label)).toEqual([
      'Copy', 'Select All',
      'Refresh View', 'Reload App', 'Hard Reload', 'Empty Cache + Hard Reload',
    ]);
    await page.keyboard.press('Escape');

    const beforeTopbarRefresh = await page.evaluate(() => performance.timeOrigin);
    await page.locator('[data-topbar]').click({ button: 'right' });
    await page.getByRole('menuitem', { name: 'Refresh View', exact: true }).click();
    await expect.poll(() => page.evaluate(() => window.__shellMenuRefreshCalls)).toBe(1);
    expect(await page.evaluate(() => performance.timeOrigin)).toBe(beforeTopbarRefresh);

    await page.locator('#topbar-refresh-btn').click();
    await expect.poll(() => page.evaluate(() => window.__shellMenuRefreshCalls)).toBe(2);
    expect(await page.evaluate(() => performance.timeOrigin)).toBe(beforeTopbarRefresh);

    await page.evaluate(() => {
      const hiddenHost = document.createElement('div');
      hiddenHost.id = 'shell-menu-hidden-selection';
      hiddenHost.textContent = 'Hidden selection should not count';
      document.querySelector('#page-settings').appendChild(hiddenHost);
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(hiddenHost);
      selection.removeAllRanges();
      selection.addRange(range);
    });
    await dispatchContextMenu(page, '[data-topbar]');
    items = await readMenuState(page);
    expect(items.map((item) => item.label)).toEqual([
      'Refresh View', 'Reload App', 'Hard Reload', 'Empty Cache + Hard Reload',
    ]);
  });

  test('reload, hard reload, and empty-cache hard reload follow the shell contract', async ({ page, baseURL }) => {
    const appOrigin = new URL(baseURL || 'http://127.0.0.1:8000').origin;
    await installShellMenuMocks(page, appOrigin);

    await gotoView(page, 'dashboard', '#dash-stats');

    const reloadOrigin = await page.evaluate(() => performance.timeOrigin);
    await page.locator('[data-topbar]').click({ button: 'right' });
    await page.getByRole('menuitem', { name: 'Reload App', exact: true }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForFunction((stamp) => performance.timeOrigin !== stamp, reloadOrigin);
    expect(await page.evaluate(() => location.hash)).toBe('#dashboard');
    expect(await page.evaluate(() => location.search)).toBe('');

    const hardReloadOrigin = await page.evaluate(() => performance.timeOrigin);
    await page.locator('[data-topbar]').click({ button: 'right' });
    await page.getByRole('menuitem', { name: 'Hard Reload', exact: true }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForFunction((stamp) => performance.timeOrigin !== stamp, hardReloadOrigin);
    await page.waitForFunction(() => !location.search.includes('__4tie_hr'));
    expect(await page.evaluate(() => location.hash)).toBe('#dashboard');

    await page.evaluate(async () => {
      localStorage.setItem('4tie_theme_mode', 'light');
      localStorage.setItem('4tie_theme_accent', 'amber');
      localStorage.setItem('4tie_theme_preset', 'sunset');
      localStorage.setItem('4tie_sidebar_collapsed', 'true');
      localStorage.setItem('4tie_settings', JSON.stringify({ stake_amount: 10 }));
      localStorage.setItem('4tie_fav_pairs', JSON.stringify(['BTC/USDT']));
      localStorage.setItem('4tie_bt_form', JSON.stringify({ pair: 'BTC/USDT' }));
      localStorage.setItem('4tie_ho_form', JSON.stringify({ epochs: 4 }));
      localStorage.setItem('strategy_lab_editor_visible', '1');
      localStorage.setItem('4tie_ui_logs', JSON.stringify([{ message: 'persisted log' }]));
      sessionStorage.setItem('4tie_pending_strategy_intelligence_rerun', JSON.stringify({ id: 'rerun-1' }));

      const cache = await caches.open('shell-menu-test-cache');
      await cache.put('/healthz', new Response('cached-health'));

      await new Promise((resolve, reject) => {
        const request = indexedDB.open('shell-menu-test-db', 1);
        request.onupgradeneeded = () => {
          request.result.createObjectStore('items');
        };
        request.onsuccess = () => {
          request.result.close();
          resolve();
        };
        request.onerror = () => reject(request.error);
      });

      if ('serviceWorker' in navigator) {
        await navigator.serviceWorker.register('/sw.js');
        await new Promise((resolve) => setTimeout(resolve, 150));
      }
    });

    const emptyCacheOrigin = await page.evaluate(() => performance.timeOrigin);
    await page.locator('[data-topbar]').click({ button: 'right' });
    await page.getByRole('menuitem', { name: 'Empty Cache + Hard Reload', exact: true }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForFunction((stamp) => performance.timeOrigin !== stamp, emptyCacheOrigin);
    await page.waitForFunction(() => !location.search.includes('__4tie_hr'));

    const state = await page.evaluate(async () => {
      const local = {};
      for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        local[key] = localStorage.getItem(key);
      }
      const sessionKeys = [];
      for (let index = 0; index < sessionStorage.length; index += 1) {
        sessionKeys.push(sessionStorage.key(index));
      }
      const cacheKeys = await (window.caches?.keys ? window.caches.keys() : Promise.resolve([]));
      const dbs = await (window.indexedDB?.databases ? window.indexedDB.databases() : Promise.resolve([]));
      const registrations = await (navigator.serviceWorker?.getRegistrations ? navigator.serviceWorker.getRegistrations() : Promise.resolve([]));
      return {
        hash: location.hash,
        search: location.search,
        local,
        sessionKeys,
        cacheKeys,
        dbNames: dbs.map((db) => db?.name).filter(Boolean),
        registrationCount: registrations.length,
      };
    });

    expect(state.hash).toBe('#dashboard');
    expect(state.search).toBe('');
    expect(state.local).toEqual({
      '4tie_sidebar_collapsed': 'true',
      '4tie_theme_accent': 'amber',
      '4tie_theme_mode': 'light',
      '4tie_theme_preset': 'sunset',
    });
    expect(state.sessionKeys).toEqual([]);
    expect(state.cacheKeys).toEqual([]);
    expect(state.dbNames).not.toContain('shell-menu-test-db');
    expect(state.registrationCount).toBe(0);
  });
});




