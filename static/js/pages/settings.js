/* =================================================================
   SETTINGS PAGE
   Exposes: window.SettingsPage
   ================================================================= */

window.SettingsPage = (() => {
  let _el = null;
  let _presets = [];

  /* ── Helpers ─────────────────────────────────────────────── */
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

  /* ── Render ──────────────────────────────────────────────── */
  function _render() {
    DOM.setHTML(_el, `
      <div class="page-header">
        <h1 class="page-header__title">Settings</h1>
        <p class="page-header__subtitle">Configure API keys, paths, and trade defaults. Changes are written to <code class="settings-code">.env</code> and take effect immediately.</p>
      </div>

      <div class="settings-layout">

        <!-- ── Environment / Secrets ── -->
        <div class="card">
          <div class="card__header">
            <span class="card__title">Environment &amp; Secrets</span>
            <span class="settings-hint">Saved to <code class="settings-code">.env</code></span>
          </div>
          <div class="card__body">
            <form id="env-form" class="form">

              <div class="settings-section-label">AI Providers</div>

              <div class="form-group">
                <label class="form-label" for="s-or-key">
                  OpenRouter API Key
                  <a class="settings-link" href="https://openrouter.ai/keys" target="_blank" rel="noopener">Get key ↗</a>
                </label>
                <div class="settings-secret-wrap">
                  <input class="form-input settings-secret-input" id="s-or-key"
                    type="password" autocomplete="off" placeholder="sk-or-…" spellcheck="false">
                  <button type="button" class="settings-reveal-btn" id="s-or-key-reveal" title="Show/hide">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  </button>
                </div>
                <span class="form-hint">Required for OpenRouter AI pipeline. Leave blank to use Ollama only.</span>
              </div>

              <div class="form-group">
                <label class="form-label" for="s-ollama-url">Ollama Base URL</label>
                <input class="form-input" id="s-ollama-url" type="text"
                  placeholder="http://localhost:11434" spellcheck="false">
                <span class="form-hint">Host and port of your Ollama server. Default: <code class="settings-code">http://localhost:11434</code></span>
              </div>

              <div class="settings-section-label" style="margin-top:var(--space-4)">FreqTrade</div>

              <div class="form-group">
                <label class="form-label" for="s-ft-path">FreqTrade Executable Path</label>
                <input class="form-input" id="s-ft-path" type="text"
                  placeholder="/home/user/.local/bin/freqtrade" spellcheck="false">
                <span class="form-hint">Absolute path to the <code class="settings-code">freqtrade</code> binary. Leave blank to use system PATH.</span>
              </div>

              <div class="settings-section-label" style="margin-top:var(--space-4)">Data Directories</div>

              <div class="form-group">
                <label class="form-label" for="s-user-data">user_data Directory</label>
                <input class="form-input" id="s-user-data" type="text"
                  placeholder="./user_data" spellcheck="false">
                <span class="form-hint">Root of all FreqTrade data. Contains <code class="settings-code">backtest_results/</code>, <code class="settings-code">strategies/</code>, <code class="settings-code">data/</code>.</span>
              </div>

              <div class="settings-section-label" style="margin-top:var(--space-4)">Server</div>

              <div class="form-row">
                <div class="form-group">
                  <label class="form-label" for="s-port">API Port</label>
                  <input class="form-input" id="s-port" type="number" min="1024" max="65535" placeholder="5000">
                  <span class="form-hint">Requires server restart.</span>
                </div>
                <div class="form-group">
                  <label class="form-label" for="s-exchange-env">Default Exchange</label>
                  <select class="form-select" id="s-exchange-env">
                    <option value="binance">Binance</option>
                    <option value="binanceus">Binance US</option>
                    <option value="kraken">Kraken</option>
                    <option value="okx">OKX</option>
                    <option value="bybit">Bybit</option>
                    <option value="ftx">FTX</option>
                  </select>
                </div>
              </div>

              <div class="form-actions">
                <button type="submit" class="btn btn--primary" id="env-save-btn">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                  Save to .env
                </button>
                <span class="settings-save-status" id="env-save-status"></span>
              </div>

            </form>
          </div>
        </div>

        <!-- ── Trade Defaults ── -->
        <div class="card" style="margin-top:var(--space-4)">
          <div class="card__header">
            <span class="card__title">Trade Defaults</span>
            <span class="settings-hint">Saved to browser storage</span>
          </div>
          <div class="card__body">
            <form id="settings-form" class="form">
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label" for="s-exchange">Exchange</label>
                  <select class="form-select" id="s-exchange" name="exchange">
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
                  <select class="form-select" id="s-timeframe" name="timeframe">
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
              <div class="form-actions">
                <button type="submit" class="btn btn--primary">Save Defaults</button>
                <button type="button" class="btn btn--secondary" id="s-reset-btn">Reset</button>
              </div>
            </form>
          </div>
        </div>

        <!-- ── Presets ── -->
        <div class="card" style="margin-top:var(--space-4)">
          <div class="card__header">
            <span class="card__title">Backtest Presets</span>
            <button class="btn btn--secondary btn--sm" id="s-save-preset-btn">Save Current as Preset</button>
          </div>
          <div class="card__body" id="s-presets-body">
            <div class="empty-state">Loading…</div>
          </div>
        </div>

      </div>
    `);

    /* ── Bind env form ── */
    DOM.on(DOM.$('#env-form', _el), 'submit', _onSaveEnv);

    const revealBtn = DOM.$('#s-or-key-reveal', _el);
    const keyInput  = DOM.$('#s-or-key', _el);
    DOM.on(revealBtn, 'click', () => {
      const isHidden = keyInput.type === 'password';
      keyInput.type = isHidden ? 'text' : 'password';
      revealBtn.style.color = isHidden ? 'var(--violet)' : '';
    });

    /* ── Bind trade defaults form ── */
    DOM.on(DOM.$('#settings-form', _el), 'submit', _onSaveDefaults);
    DOM.on(DOM.$('#s-reset-btn',   _el), 'click',  _onReset);
    DOM.on(DOM.$('#s-save-preset-btn', _el), 'click', _onSavePreset);
  }

  /* ── Load ────────────────────────────────────────────────── */
  async function load() {
    try {
      const [envData, cfgData, presetsData] = await Promise.all([
        API.getSettings().catch(() => ({})),
        API.getLastConfig().catch(() => ({ config: null })),
        API.getPresets().catch(() => ({ presets: {} })),
      ]);

      // Populate env fields
      _set('s-or-key',      envData.openrouter_api_key || '');
      _set('s-ollama-url',  envData.ollama_base_url    || '');
      _set('s-ft-path',     envData.freqtrade_path     || '');
      _set('s-user-data',   envData.user_data_dir      || '');
      _set('s-port',        envData.backtest_api_port  || '5000');
      _set('s-exchange-env', envData.freqtrade_exchange || 'binance');

      // Populate trade defaults (localStorage wins over last_config)
      const saved = _loadLocalSettings();
      const cfg   = saved || cfgData.config || {};
      _set('s-exchange',   cfg.exchange        || 'binance');
      _set('s-timeframe',  cfg.timeframe       || '5m');
      _set('s-wallet',     cfg.dry_run_wallet  || 1000);
      _set('s-max-trades', cfg.max_open_trades || 3);
      _set('s-stake',      cfg.stake_amount    || 'unlimited');

      _presets = presetsData.presets || {};
      _renderPresets();
    } catch (err) {
      Toast.warning('Could not load settings: ' + err.message);
    }
  }

  /* ── Save env ────────────────────────────────────────────── */
  async function _onSaveEnv(e) {
    e.preventDefault();
    const btn    = DOM.$('#env-save-btn', _el);
    const status = DOM.$('#env-save-status', _el);
    btn.disabled = true;

    const body = {
      openrouter_api_key: _val('s-or-key'),
      ollama_base_url:    _val('s-ollama-url'),
      freqtrade_path:     _val('s-ft-path'),
      user_data_dir:      _val('s-user-data'),
      backtest_api_port:  _val('s-port'),
      freqtrade_exchange: _val('s-exchange-env'),
    };

    try {
      await API.saveSettings(body);
      if (status) {
        status.textContent = '✓ Saved to .env';
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

  /* ── Save trade defaults ─────────────────────────────────── */
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
    Toast.info('Reset to defaults (not saved).');
  }

  function _loadLocalSettings() {
    try { return JSON.parse(localStorage.getItem('4tie_settings') || 'null'); } catch { return null; }
  }

  /* ── Presets ─────────────────────────────────────────────── */
  function _renderPresets() {
    const el = DOM.$('#s-presets-body', _el);
    if (!el) return;
    const entries = Object.entries(_presets);
    if (!entries.length) {
      el.innerHTML = '<div class="empty-state">No presets saved yet.</div>';
      return;
    }
    el.innerHTML = `
      <table class="data-table">
        <thead><tr><th>Name</th><th>Exchange</th><th>Timeframe</th><th>Saved</th><th></th></tr></thead>
        <tbody>
          ${entries.map(([name, entry]) => {
            const cfg = entry.config || entry;
            return `
            <tr>
              <td class="font-semibold">${_esc(name)}</td>
              <td>${_esc(cfg.exchange || '—')}</td>
              <td>${_esc(cfg.timeframe || '—')}</td>
              <td class="text-muted text-sm">${FMT.tsShort(entry.saved_at)}</td>
              <td>
                <button class="btn btn--ghost btn--sm" data-load-preset="${_esc(name)}">Load</button>
                <button class="btn btn--danger btn--sm" data-delete-preset="${_esc(name)}">Delete</button>
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>`;

    el.querySelectorAll('[data-load-preset]').forEach(btn =>
      DOM.on(btn, 'click', () => _loadPreset(btn.dataset.loadPreset))
    );
    el.querySelectorAll('[data-delete-preset]').forEach(btn =>
      DOM.on(btn, 'click', () => _deletePreset(btn.dataset.deletePreset))
    );
  }

  async function _onSavePreset() {
    const name = prompt('Preset name:');
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
    if (!confirm(`Delete preset "${name}"?`)) return;
    try {
      await API.deletePreset(name);
      Toast.success(`Preset "${name}" deleted.`);
      _presets = (await API.getPresets()).presets || {};
      _renderPresets();
    } catch (err) {
      Toast.error('Failed to delete: ' + err.message);
    }
  }

  /* ── Public ──────────────────────────────────────────────── */
  function init() {
    _el = DOM.$('[data-view="settings"]');
    if (!_el) return;
    _render();
    load();
  }

  function refresh() { load(); }

  return { init, refresh };
})();
