/* =================================================================
   SETTINGS PAGE
   Exposes: window.SettingsPage
   ================================================================= */

window.SettingsPage = (() => {
  let _el = null;
  let _presets = [];

  function init() {
    _el = DOM.$('[data-view="settings"]');
    if (!_el) return;
    _render();
    load();
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="page-header">
        <h1 class="page-header__title">Settings</h1>
        <p class="page-header__subtitle">Configure default exchange, data paths, and trade parameters.</p>
      </div>
      <div class="settings-layout">
        <div class="card">
          <div class="card__header"><span class="card__title">Default Configuration</span></div>
          <div class="card__body">
            <form id="settings-form" class="form">
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label" for="s-exchange">Default Exchange</label>
                  <select class="form-select" id="s-exchange" name="exchange">
                    <option value="binance">Binance</option>
                    <option value="kraken">Kraken</option>
                    <option value="okx">OKX</option>
                    <option value="ftx">FTX</option>
                    <option value="bybit">Bybit</option>
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
              <div class="form-group">
                <label class="form-label" for="s-data-dir">Data Directory</label>
                <input class="form-input" id="s-data-dir" name="data_directory" type="text" placeholder="/path/to/freqtrade/user_data/data">
                <span class="form-hint">Path where FreqTrade OHLCV data is stored.</span>
              </div>
              <div class="form-actions">
                <button type="submit" class="btn btn--primary">Save Settings</button>
                <button type="button" class="btn btn--secondary" id="s-reset-btn">Reset to Defaults</button>
              </div>
            </form>
          </div>
        </div>

        <div class="card" style="margin-top:var(--space-4)">
          <div class="card__header">
            <span class="card__title">Presets</span>
            <button class="btn btn--secondary btn--sm" id="s-save-preset-btn">Save Current as Preset</button>
          </div>
          <div class="card__body" id="s-presets-body">
            <div class="empty-state">Loading…</div>
          </div>
        </div>
      </div>
    `);

    DOM.on(DOM.$('#settings-form', _el), 'submit', _onSave);
    DOM.on(DOM.$('#s-reset-btn',   _el), 'click',  _onReset);
    DOM.on(DOM.$('#s-save-preset-btn', _el), 'click', _onSavePreset);
  }

  async function load() {
    try {
      const [cfgData, presetsData] = await Promise.all([
        API.getLastConfig().catch(() => ({ config: null })),
        API.getPresets().catch(() => ({ presets: {} })),
      ]);

      if (cfgData.config) {
        const cfg = cfgData.config;
        const s = (id, v) => { const el = DOM.$(id, _el); if (el && v != null) el.value = v; };
        s('#s-exchange',   cfg.exchange);
        s('#s-timeframe',  cfg.timeframe);
        s('#s-wallet',     cfg.dry_run_wallet);
        s('#s-max-trades', cfg.max_open_trades);
        s('#s-stake',      cfg.stake_amount);
        s('#s-data-dir',   cfg.data_directory);
      }

      const saved = localStorage.getItem('4tie_settings');
      if (saved) {
        try {
          const cfg = JSON.parse(saved);
          const s = (id, v) => { const el = DOM.$(id, _el); if (el && v != null) el.value = v; };
          s('#s-exchange',   cfg.exchange);
          s('#s-timeframe',  cfg.timeframe);
          s('#s-wallet',     cfg.dry_run_wallet);
          s('#s-max-trades', cfg.max_open_trades);
          s('#s-stake',      cfg.stake_amount);
          s('#s-data-dir',   cfg.data_directory);
        } catch {}
      }

      _presets = presetsData.presets || {};
      _renderPresets();
    } catch (err) {
      Toast.warning('Could not load settings: ' + err.message);
    }
  }

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

    el.querySelectorAll('[data-load-preset]').forEach(btn => {
      DOM.on(btn, 'click', () => _loadPreset(btn.dataset.loadPreset));
    });
    el.querySelectorAll('[data-delete-preset]').forEach(btn => {
      DOM.on(btn, 'click', () => _deletePreset(btn.dataset.deletePreset));
    });
  }

  function _getFormValues() {
    return {
      exchange:        DOM.$('#s-exchange',  _el)?.value || 'binance',
      timeframe:       DOM.$('#s-timeframe', _el)?.value || '5m',
      dry_run_wallet:  parseFloat(DOM.$('#s-wallet',     _el)?.value) || 1000,
      max_open_trades: parseInt(DOM.$('#s-max-trades',  _el)?.value) || 3,
      stake_amount:    DOM.$('#s-stake',     _el)?.value || 'unlimited',
      data_directory:  DOM.$('#s-data-dir',  _el)?.value || '',
    };
  }

  function _onSave(e) {
    e.preventDefault();
    const vals = _getFormValues();
    localStorage.setItem('4tie_settings', JSON.stringify(vals));
    Toast.success('Settings saved.');
    AppState.set('stream', 'Settings saved.');
  }

  function _onReset() {
    const defaults = { exchange: 'binance', timeframe: '5m', dry_run_wallet: 1000, max_open_trades: 3, stake_amount: 'unlimited', data_directory: '' };
    const s = (id, v) => { const el = DOM.$(id, _el); if (el) el.value = v; };
    s('#s-exchange',   defaults.exchange);
    s('#s-timeframe',  defaults.timeframe);
    s('#s-wallet',     defaults.dry_run_wallet);
    s('#s-max-trades', defaults.max_open_trades);
    s('#s-stake',      defaults.stake_amount);
    s('#s-data-dir',   defaults.data_directory);
    Toast.info('Reset to defaults (not saved).');
  }

  async function _onSavePreset() {
    const name = prompt('Preset name:');
    if (!name) return;
    const config = _getFormValues();
    try {
      await API.savePreset({ name, config });
      Toast.success(`Preset "${name}" saved.`);
      const presetsData = await API.getPresets();
      _presets = presetsData.presets || {};
      _renderPresets();
    } catch (err) {
      Toast.error('Failed to save preset: ' + err.message);
    }
  }

  function _loadPreset(name) {
    const entry = _presets[name];
    if (!entry) return;
    const cfg = entry.config || entry;
    const s = (id, v) => { const el = DOM.$(id, _el); if (el && v != null) el.value = v; };
    s('#s-exchange',   cfg.exchange);
    s('#s-timeframe',  cfg.timeframe);
    s('#s-wallet',     cfg.dry_run_wallet);
    s('#s-max-trades', cfg.max_open_trades);
    s('#s-stake',      cfg.stake_amount);
    s('#s-data-dir',   cfg.data_directory);
    Toast.info(`Loaded preset "${name}".`);
  }

  async function _deletePreset(name) {
    if (!confirm(`Delete preset "${name}"?`)) return;
    try {
      await API.deletePreset(name);
      Toast.success(`Preset "${name}" deleted.`);
      const presetsData = await API.getPresets();
      _presets = presetsData.presets || {};
      _renderPresets();
    } catch (err) {
      Toast.error('Failed to delete: ' + err.message);
    }
  }

  function _esc(str) {
    const d = document.createElement('div');
    d.textContent = String(str || '');
    return d.innerHTML;
  }

  function refresh() { load(); }

  return { init, refresh };
})();
