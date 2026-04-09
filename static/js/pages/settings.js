/* =================================================================
   SETTINGS PAGE
   Exposes: window.SettingsPage
   ================================================================= */

window.SettingsPage = (() => {
  let _el = null;
  let _presets = [];
  let _themeModes = [];
  let _themeAccents = [];
  let _selectedThemeMode = 'dark';
  let _selectedThemeAccent = 'indigo';

  /* â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
  function _esc(str) {
    const d = document.createElement('div');
    d.textContent = String(str || '');
    return d.innerHTML;
  }

  function _val(id) {
    return (DOM.$(`#${id}`, _el) || {}).value || '';
  }

  function _set(id, v) {
    const el = DOM.$(`#${id}`, _el);
    if (el && v != null) el.value = v;
  }

  function _getThemeModes() {
    return window.ThemeManager?.getModes?.() || [];
  }

  function _getThemeAccents() {
    return window.ThemeManager?.getAccents?.() || [];
  }

  function _splitApiKeys(raw) {
    return String(raw || '')
      .split(/[\n,]+/g)
      .map(s => s.trim())
      .filter(Boolean);
  }

  function _getApiRows() {
    return Array.from(DOM.$$('#s-or-list .settings-api-row', _el) || []);
  }

  function _collectApiKeysRaw() {
    const values = _getApiRows()
      .map(row => (DOM.$('.settings-api-input', row) || {}).value || '')
      .map(v => v.trim())
      .filter(Boolean);
    return values.join('\n');
  }

  function _updateApiKeyMeta() {
    const count = _getApiRows()
      .map(row => (DOM.$('.settings-api-input', row) || {}).value || '')
      .map(v => v.trim())
      .filter(Boolean).length;
    const counter = DOM.$('#s-or-count', _el);
    if (counter) counter.textContent = `${count} key${count === 1 ? '' : 's'}`;
  }

  function _addApiKeyRow(value = '') {
    const list = DOM.$('#s-or-list', _el);
    if (!list) return;
    const row = document.createElement('div');
    row.className = 'settings-api-row';
    row.innerHTML = `
      <input class="form-input settings-api-input" type="password" autocomplete="off" placeholder="sk-or-..." spellcheck="false">
      <button type="button" class="settings-api-btn" data-action="toggle" title="Show/hide key">Show</button>
      <button type="button" class="settings-api-btn settings-api-btn--test" data-action="test" title="Test API key">Test</button>
      <button type="button" class="settings-api-btn settings-api-btn--danger" data-action="remove" title="Remove key">Remove</button>
    `;

    const input = DOM.$('.settings-api-input', row);
    input.value = value || '';
    DOM.on(input, 'input', _updateApiKeyMeta);

    DOM.on(DOM.$('[data-action="toggle"]', row), 'click', (e) => {
      const hidden = input.type === 'password';
      input.type = hidden ? 'text' : 'password';
      e.currentTarget.textContent = hidden ? 'Hide' : 'Show';
    });

    DOM.on(DOM.$('[data-action="test"]', row), 'click', async (e) => {
      const btn = e.currentTarget;
      const originalText = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Testing...';
      
      try {
        const result = await API.testOpenRouterKey(input.value.trim());
        if (result.valid) {
          Toast.success('API key is valid');
          btn.textContent = 'âœ“ Valid';
          setTimeout(() => { btn.textContent = originalText; }, 2000);
        } else {
          Toast.error(`API key test failed: ${result.error}`);
          btn.textContent = 'âœ— Failed';
          setTimeout(() => { btn.textContent = originalText; }, 3000);
        }
      } catch (err) {
        Toast.error('Failed to test API key: ' + err.message);
        btn.textContent = 'âœ— Error';
        setTimeout(() => { btn.textContent = originalText; }, 3000);
      } finally {
        btn.disabled = false;
      }
    });

    DOM.on(DOM.$('[data-action="remove"]', row), 'click', () => {
      row.remove();
      if (!_getApiRows().length) _addApiKeyRow('');
      _updateApiKeyMeta();
    });

    list.appendChild(row);
    _updateApiKeyMeta();
  }

  function _setApiKeys(raw) {
    const list = DOM.$('#s-or-list', _el);
    if (!list) return;
    list.innerHTML = '';
    const keys = _splitApiKeys(raw);
    if (!keys.length) {
      _addApiKeyRow('');
      return;
    }
    keys.forEach(key => _addApiKeyRow(key));
  }

  /* â”€â”€ Render â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
  function _render() {
    DOM.setHTML(_el, `
      <div class="page-header">
        <h1 class="page-header__title">Settings</h1>
        <p class="page-header__subtitle">Configure API keys, paths, and trade defaults. Changes are written to <code class="settings-code">.env</code> and take effect immediately.</p>
      </div>

      <div class="settings-layout">

        <!-- â”€â”€ Environment / Secrets â”€â”€ -->
        <div class="card">
          <div class="card__header">
            <span class="card__title">Environment &amp; Secrets</span>
            <span class="settings-hint">Saved to <code class="settings-code">.env</code></span>
          </div>
          <div class="card__body">
            <form id="env-form" class="form">

              <div class="settings-section-label">AI Providers</div>

              <div class="form-group">
                <label class="form-label" for="s-or-list">
                  OpenRouter API Keys
                  <a class="settings-link" href="https://openrouter.ai/keys" target="_blank" rel="noopener">Get key â†—</a>
                </label>
                <div class="settings-api-box">
                  <div class="settings-api-toolbar">
                    <span class="settings-api-count" id="s-or-count">0 keys</span>
                    <div class="settings-api-actions">
                      <button type="button" class="settings-api-btn" id="s-or-add">+ Add key</button>
                      <button type="button" class="settings-api-btn settings-api-btn--danger" id="s-or-clear">Clear</button>
                    </div>
                  </div>
                  <div class="settings-api-list" id="s-or-list"></div>
                </div>
                <span class="form-hint">Add one key per row. If values are masked, updating this list replaces the saved keys.</span>
              </div>

              <div class="settings-input-panel">
                <div class="settings-input-panel__toolbar">
                  <span class="settings-api-count">Ollama</span>
                </div>
                <div class="settings-input-panel__body">
                  <div class="form-group">
                    <label class="form-label" for="s-ollama-url">Ollama Base URL</label>
                    <input class="form-input" id="s-ollama-url" type="text"
                      placeholder="http://localhost:11434" spellcheck="false">
                    <span class="form-hint">Host and port of your Ollama server. Default: <code class="settings-code">http://localhost:11434</code></span>
                  </div>
                </div>
              </div>

              <div class="settings-section-label" style="margin-top:var(--space-4)">FreqTrade</div>

              <div class="settings-input-panel">
                <div class="settings-input-panel__toolbar">
                  <span class="settings-api-count">Runtime</span>
                </div>
                <div class="settings-input-panel__body">
                  <div class="form-group">
                    <label class="form-label" for="s-ft-path">FreqTrade Executable Path</label>
                    <input class="form-input" id="s-ft-path" type="text"
                      placeholder="/home/user/.local/bin/freqtrade" spellcheck="false">
                    <span class="form-hint">Absolute path to the <code class="settings-code">freqtrade</code> binary. Leave blank to use system PATH.</span>
                  </div>
                </div>
              </div>

              <div class="settings-section-label" style="margin-top:var(--space-4)">Data Directories</div>

              <div class="settings-input-panel">
                <div class="settings-input-panel__toolbar">
                  <span class="settings-api-count">Paths</span>
                </div>
                <div class="settings-input-panel__body">
                  <div class="form-group">
                    <label class="form-label" for="s-user-data">user_data Directory</label>
                    <input class="form-input" id="s-user-data" type="text"
                      placeholder="./user_data" spellcheck="false">
                    <span class="form-hint">Root of all FreqTrade data. Contains <code class="settings-code">backtest_results/</code>, <code class="settings-code">strategies/</code>, <code class="settings-code">data/</code>.</span>
                  </div>
                </div>
              </div>

              <div class="settings-section-label" style="margin-top:var(--space-4)">Server</div>

              <div class="settings-input-panel">
                <div class="settings-input-panel__toolbar">
                  <span class="settings-api-count">Server Defaults</span>
                </div>
                <div class="settings-input-panel__body">
                  <div class="form-row">
                    <div class="form-group">
                      <label class="form-label" for="s-port">API Port</label>
                      <input class="form-input" id="s-port" type="number" min="1024" max="65535" placeholder="8000">
                      <span class="form-hint">Requires server restart.</span>
                    </div>
                    <div class="form-group">
                      <label class="form-label" for="s-exchange-env">Default Exchange</label>
                      <select class="form-select" id="s-exchange-env" data-ui-select="true" data-select-search="never">
                        <option value="binance">Binance</option>
                        <option value="binanceus">Binance US</option>
                        <option value="kraken">Kraken</option>
                        <option value="okx">OKX</option>
                        <option value="bybit">Bybit</option>
                        <option value="ftx">FTX</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              <div class="form-actions">
                <span class="settings-save-status" id="env-save-status"></span>
              </div>

            </form>
          </div>
        </div>

        <!-- â”€â”€ Trade Defaults â”€â”€ -->
        <div class="card" style="margin-top:var(--space-4)">
          <div class="card__header">
            <span class="card__title">Trade Defaults</span>
            <span class="settings-hint">Saved to browser storage</span>
          </div>
          <div class="card__body">
            <form id="settings-form" class="form">
              <div class="settings-section-label">Market Defaults</div>
              <div class="settings-input-panel">
                <div class="settings-input-panel__toolbar">
                  <span class="settings-api-count">Exchange &amp; Timeframe</span>
                </div>
                <div class="settings-input-panel__body">
                  <div class="form-row">
                    <div class="form-group">
                      <label class="form-label" for="s-exchange">Exchange</label>
                      <select class="form-select" id="s-exchange" name="exchange" data-ui-select="true" data-select-search="never">
                        <option value="binance">Binance</option>
                        <option value="binanceus">Binance US</option>
                        <option value="kraken">Kraken</option>
                        <option value="okx">OKX</option>
                        <option value="bybit">Bybit</option>
                        <option value="ftx">FTX</option>
                      </select>
                    </div>
                    <div class="form-group">
                      <label class="form-label" for="s-timeframe">Default Timeframe</label>
                      <select class="form-select" id="s-timeframe" name="timeframe" data-ui-select="true" data-select-search="never">
                        <option value="1m">1m</option>
                        <option value="5m" selected>5m</option>
                        <option value="15m">15m</option>
                        <option value="30m">30m</option>
                        <option value="1h">1h</option>
                        <option value="4h">4h</option>
                        <option value="1d">1d</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>
              <div class="settings-section-label" style="margin-top:var(--space-4)">Risk &amp; Capital</div>
              <div class="settings-input-panel">
                <div class="settings-input-panel__toolbar">
                  <span class="settings-api-count">Wallet &amp; Positioning</span>
                </div>
                <div class="settings-input-panel__body">
                  <div class="form-row">
                    <div class="form-group">
                      <label class="form-label" for="s-wallet">Starting Wallet ($)</label>
                      <input class="form-input" id="s-wallet" name="dry_run_wallet" type="number" value="1000" min="1">
                    </div>
                    <div class="form-group">
                      <label class="form-label" for="s-max-trades">Max Open Trades</label>
                      <input class="form-input" id="s-max-trades" name="max_open_trades" type="number" value="3" min="1">
                    </div>
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="s-stake">Stake Amount</label>
                    <input class="form-input" id="s-stake" name="stake_amount" type="text" value="unlimited">
                    <span class="form-hint">Use "unlimited" to distribute wallet evenly.</span>
                  </div>
                </div>
              </div>
            </form>
          </div>
        </div>

        <div class="card" style="margin-top:var(--space-4)">
          <div class="card__header">
            <span class="card__title">Appearance</span>
            <span class="settings-hint">Saved to browser storage</span>
          </div>
          <div class="card__body">
            <div class="settings-section-label">Theme Mode</div>
            <div class="settings-input-panel">
              <div class="settings-input-panel__toolbar">
                <span class="settings-api-count">Dark and light are both first-class modes</span>
              </div>
              <div class="settings-input-panel__body">
                <div id="theme-mode-grid" class="theme-mode-grid"></div>
                <span class="form-hint">Mode updates the full shell, panels, tables, and workspace surfaces immediately.</span>
              </div>
            </div>
            <div class="settings-section-label" style="margin-top:var(--space-4)">Accent</div>
            <div class="settings-input-panel">
              <div class="settings-input-panel__toolbar">
                <span class="settings-api-count">One controlled accent for actions, focus, and state</span>
              </div>
              <div class="settings-input-panel__body">
                <div id="theme-accent-grid" class="theme-preset-grid"></div>
                <span class="form-hint">Accent changes remain optional and are layered on top of the selected mode.</span>
              </div>
            </div>
          </div>
        </div>

        <!-- â”€â”€ Presets â”€â”€ -->
        <div class="card" style="margin-top:var(--space-4)">
          <div class="card__header">
            <span class="card__title">Backtest Presets</span>
            <button class="btn btn--secondary btn--sm" id="s-save-preset-btn">Save Current as Preset</button>
          </div>
          <div class="card__body" id="s-presets-body">
            <div class="empty-state">Loadingâ€¦</div>
          </div>
        </div>

        <!-- â”€â”€ Master Save Button â”€â”€ -->
        <div class="settings-master-save" style="margin-top:var(--space-4)">
          <button type="button" class="btn btn--primary btn--lg" id="master-save-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
            Save All Settings
          </button>
          <span class="settings-save-status" id="master-save-status"></span>
        </div>

      </div>
    `);

    /* â”€â”€ Bind events â”€â”€ */
    DOM.on(DOM.$('#env-form', _el), 'submit', (e) => e.preventDefault()); // Prevent default form submission
    DOM.on(DOM.$('#settings-form', _el), 'submit', (e) => e.preventDefault()); // Prevent default form submission
    DOM.on(DOM.$('#s-or-add', _el), 'click', () => _addApiKeyRow(''));
    DOM.on(DOM.$('#s-or-clear', _el), 'click', () => _setApiKeys(''));
    DOM.on(DOM.$('#s-reset-btn',   _el), 'click',  _onReset);
    DOM.on(DOM.$('#s-save-preset-btn', _el), 'click', _onSavePreset);
    DOM.on(DOM.$('#master-save-btn', _el), 'click', _onMasterSave);
  }

  /* â”€â”€ Load â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
  async function load() {
    try {
      const [envData, cfgData, presetsData] = await Promise.all([
        API.getSettings().catch(() => ({})),
        API.getLastConfig().catch(() => ({ config: null })),
        API.getPresets().catch(() => ({ presets: {} })),
      ]);

      // Populate env fields
      _setApiKeys(envData.openrouter_api_keys || envData.openrouter_api_key || '');
      _set('s-ollama-url',  envData.ollama_base_url    || '');
      _set('s-ft-path',     envData.freqtrade_path     || '');
      _set('s-user-data',   envData.user_data_dir      || '');
      _set('s-port',        envData.backtest_api_port  || '8000');
      _set('s-exchange-env', envData.freqtrade_exchange || 'binance');

      // Populate trade defaults (localStorage wins over last_config)
      const saved = _loadLocalSettings();
      const cfg   = saved || cfgData.config || {};
      _set('s-exchange',   cfg.exchange        || 'binance');
      _set('s-timeframe',  cfg.timeframe       || '5m');
      _set('s-wallet',     cfg.dry_run_wallet  || 1000);
      _set('s-max-trades', cfg.max_open_trades || 3);
      _set('s-stake',      cfg.stake_amount    || 'unlimited');
      _themeModes = _getThemeModes();
      _themeAccents = _getThemeAccents();
      _selectedThemeMode = window.ThemeManager?.getStoredMode?.() || 'dark';
      _selectedThemeAccent = window.ThemeManager?.getStoredAccent?.() || 'indigo';
      _renderThemeModes();
      _renderThemeAccents();

      _presets = presetsData.presets || {};
      _renderPresets();
    } catch (err) {
      Toast.warning('Could not load settings: ' + err.message);
    }
  }

  /* â”€â”€ Save env â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
  async function _onSaveEnv(e) {
    e.preventDefault();
    const btn    = DOM.$('#env-save-btn', _el);
    const status = DOM.$('#env-save-status', _el);
    btn.disabled = true;

    const body = {
      openrouter_api_keys: _collectApiKeysRaw(),
      ollama_base_url:    _val('s-ollama-url'),
      freqtrade_path:     _val('s-ft-path'),
      user_data_dir:      _val('s-user-data'),
      backtest_api_port:  _val('s-port'),
      freqtrade_exchange: _val('s-exchange-env'),
    };

    try {
      await API.saveSettings(body);
      if (status) {
        status.textContent = 'âœ“ Saved to .env';
        status.className = 'settings-save-status settings-save-status--ok';
        setTimeout(() => { status.textContent = ''; status.className = 'settings-save-status'; }, 3000);
      }
      Toast.success('Environment settings saved to .env');
    } catch (err) {
      Toast.error('Failed to save: ' + err.message);
    } finally {
      btn.disabled = false;
    }
  }

  /* â”€â”€ Save trade defaults â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
  function _onSaveDefaults(e) {
    e.preventDefault();
    const vals = {
      exchange:        _val('s-exchange')   || 'binance',
      timeframe:       _val('s-timeframe')  || '5m',
      dry_run_wallet:  parseFloat(_val('s-wallet'))     || 1000,
      max_open_trades: parseInt(_val('s-max-trades'))   || 3,
      stake_amount:    _val('s-stake')      || 'unlimited',
    };
    localStorage.setItem('4tie_settings', JSON.stringify(vals));
    Toast.success('Trade defaults saved.');
  }

  function _onReset() {
    _set('s-exchange',   'binance');
    _set('s-timeframe',  '5m');
    _set('s-wallet',     1000);
    _set('s-max-trades', 3);
    _set('s-stake',      'unlimited');
    Toast.info('Reset defaults applied.');
  }

  function _loadLocalSettings() {
    try { return JSON.parse(localStorage.getItem('4tie_settings') || 'null'); } catch { return null; }
  }

  /* â”€â”€ Presets â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
  function _renderPresets() {
    const el = DOM.$('#s-presets-body', _el);
    if (!el) return;
    const entries = Object.entries(_presets);
    if (!entries.length) {
      el.innerHTML = '<div class="empty-state">No presets saved yet.</div>';
      return;
    }
    el.innerHTML = `
      <div class="settings-table-wrap">
      <table class="data-table">
        <thead><tr><th>Name</th><th>Exchange</th><th>Timeframe</th><th>Saved</th><th></th></tr></thead>
        <tbody>
          ${entries.map(([name, entry]) => {
            const cfg = entry.config || entry;
            return `
            <tr>
              <td class="font-semibold">${_esc(name)}</td>
              <td>${_esc(cfg.exchange || 'â€”')}</td>
              <td>${_esc(cfg.timeframe || 'â€”')}</td>
              <td class="text-muted text-sm">${FMT.tsShort(entry.saved_at)}</td>
              <td>
                <button class="btn btn--ghost btn--sm" data-load-preset="${_esc(name)}">Load</button>
                <button class="btn btn--danger btn--sm" data-delete-preset="${_esc(name)}">Delete</button>
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
      </div>`;

    el.querySelectorAll('[data-load-preset]').forEach(btn =>
      DOM.on(btn, 'click', () => _loadPreset(btn.dataset.loadPreset))
    );
    el.querySelectorAll('[data-delete-preset]').forEach(btn =>
      DOM.on(btn, 'click', () => _deletePreset(btn.dataset.deletePreset))
    );
  }

  function _renderThemeModes() {
    const el = DOM.$('#theme-mode-grid', _el);
    if (!el) return;
    const modes = _themeModes.length ? _themeModes : _getThemeModes();
    el.innerHTML = modes.map(mode => `
      <button
        type="button"
        class="theme-preset-card theme-preset-card--mode ${mode.id === _selectedThemeMode ? 'is-active' : ''}"
        data-theme-mode="${_esc(mode.id)}"
        aria-pressed="${mode.id === _selectedThemeMode ? 'true' : 'false'}"
      >
        <div class="theme-preset-card__preview theme-preset-card__preview--${_esc(mode.id)}">
          <span class="theme-preset-card__preview-top"></span>
          <span class="theme-preset-card__preview-main"></span>
          <span class="theme-preset-card__preview-rail"></span>
        </div>
        <div class="theme-preset-card__meta">
          <div>
            <div class="theme-preset-card__title">${_esc(mode.name)}</div>
            <div class="theme-preset-card__desc">${_esc(mode.description)}</div>
          </div>
          ${mode.id === _selectedThemeMode ? '<span class="theme-preset-card__badge">Active</span>' : ''}
        </div>
      </button>
    `).join('');

    el.querySelectorAll('[data-theme-mode]').forEach(btn => {
      DOM.on(btn, 'click', () => {
        _selectedThemeMode = btn.dataset.themeMode || 'dark';
        window.ThemeManager?.applyTheme?.({
          mode: _selectedThemeMode,
          accent: _selectedThemeAccent,
        });
        _renderThemeModes();
      });
    });
  }

  function _renderThemeAccents() {
    const el = DOM.$('#theme-accent-grid', _el);
    if (!el) return;
    const accents = _themeAccents.length ? _themeAccents : _getThemeAccents();
    el.innerHTML = accents.map(accent => `
      <button
        type="button"
        class="theme-preset-card ${accent.id === _selectedThemeAccent ? 'is-active' : ''}"
        data-theme-accent="${_esc(accent.id)}"
        aria-pressed="${accent.id === _selectedThemeAccent ? 'true' : 'false'}"
      >
        <div class="theme-preset-card__swatches">
          ${accent.swatches.map(color => `<span class="theme-preset-card__swatch" style="background:${_esc(color)}"></span>`).join('')}
        </div>
        <div class="theme-preset-card__meta">
          <div>
            <div class="theme-preset-card__title">${_esc(accent.name)}</div>
            <div class="theme-preset-card__desc">${_esc(accent.description)}</div>
          </div>
          ${accent.id === _selectedThemeAccent ? '<span class="theme-preset-card__badge">Active</span>' : ''}
        </div>
      </button>
    `).join('');

    el.querySelectorAll('[data-theme-accent]').forEach(btn => {
      DOM.on(btn, 'click', () => {
        _selectedThemeAccent = btn.dataset.themeAccent || 'indigo';
        window.ThemeManager?.applyTheme?.({
          mode: _selectedThemeMode,
          accent: _selectedThemeAccent,
        });
        _renderThemeAccents();
      });
    });
  }

  async function _onSavePreset() {
    const rawName = await Modal.prompt({
      title: 'Save Preset',
      message: 'Enter a name for this settings preset.',
      label: 'Preset Name',
      placeholder: 'My preset',
      confirmLabel: 'Save Preset',
      value: '',
    });
    const name = rawName?.trim();
    if (!name) return;
    const config = {
      exchange:        _val('s-exchange'),
      timeframe:       _val('s-timeframe'),
      dry_run_wallet:  parseFloat(_val('s-wallet'))   || 1000,
      max_open_trades: parseInt(_val('s-max-trades')) || 3,
      stake_amount:    _val('s-stake'),
    };
    try {
      await API.savePreset({ name, config });
      Toast.success(`Preset "${name}" saved.`);
      _presets = (await API.getPresets()).presets || {};
      _renderPresets();
    } catch (err) {
      Toast.error('Failed to save preset: ' + err.message);
    }
  }

  function _loadPreset(name) {
    const entry = _presets[name];
    if (!entry) return;
    const cfg = entry.config || entry;
    _set('s-exchange',   cfg.exchange);
    _set('s-timeframe',  cfg.timeframe);
    _set('s-wallet',     cfg.dry_run_wallet);
    _set('s-max-trades', cfg.max_open_trades);
    _set('s-stake',      cfg.stake_amount);
    Toast.info(`Loaded preset "${name}".`);
  }

  async function _deletePreset(name) {
    const confirmed = await Modal.confirm({
      title: 'Delete Preset',
      message: `Delete preset "${name}"?`,
      confirmLabel: 'Delete Preset',
    });
    if (!confirmed) return;
    try {
      await API.deletePreset(name);
      Toast.success(`Preset "${name}" deleted.`);
      _presets = (await API.getPresets()).presets || {};
      _renderPresets();
    } catch (err) {
      Toast.error('Failed to delete: ' + err.message);
    }
  }

  /* â”€â”€ Master Save â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
  async function _onMasterSave() {
    const btn = DOM.$('#master-save-btn', _el);
    const status = DOM.$('#master-save-status', _el);
    btn.disabled = true;
    btn.textContent = 'Saving...';

    try {
      // Save environment settings to .env
      const envBody = {
        openrouter_api_keys: _collectApiKeysRaw(),
        ollama_base_url:    _val('s-ollama-url'),
        freqtrade_path:     _val('s-ft-path'),
        user_data_dir:      _val('s-user-data'),
        backtest_api_port:  _val('s-port'),
        freqtrade_exchange: _val('s-exchange-env'),
      };
      await API.saveSettings(envBody);

      // Save trade defaults and theme to localStorage
      const localVals = {
        exchange:        _val('s-exchange')   || 'binance',
        timeframe:       _val('s-timeframe')  || '5m',
        dry_run_wallet:  parseFloat(_val('s-wallet'))     || 1000,
        max_open_trades: parseInt(_val('s-max-trades'))   || 3,
        stake_amount:    _val('s-stake')      || 'unlimited',
      };
      localStorage.setItem('4tie_settings', JSON.stringify(localVals));

      window.ThemeManager?.applyTheme?.({
        mode: _selectedThemeMode || 'dark',
        accent: _selectedThemeAccent || 'indigo',
      });

      if (status) {
        status.textContent = 'âœ“ All settings saved';
        status.className = 'settings-save-status settings-save-status--ok';
        setTimeout(() => { status.textContent = ''; status.className = 'settings-save-status'; }, 3000);
      }
      Toast.success('All settings saved successfully!');

    } catch (err) {
      Toast.error('Failed to save settings: ' + err.message);
      if (status) {
        status.textContent = 'âœ— Save failed';
        status.className = 'settings-save-status settings-save-status--error';
        setTimeout(() => { status.textContent = ''; status.className = 'settings-save-status'; }, 3000);
      }
    } finally {
      btn.disabled = false;
      btn.textContent = 'Save All Settings';
    }
  }

  /* â”€â”€ Public â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
  function init() {
    _el = DOM.$('[data-view="settings"]');
    if (!_el) return;
    _render();
    window.CustomSelect?.upgradeWithin(_el);
    load();
  }

  function refresh() { load(); }

  return { init, refresh };
})();

