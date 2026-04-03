/* =================================================================
   BACKTESTING PAGE
   Exposes: window.BacktestPage
   ================================================================= */

window.BacktestPage = (() => {
  let _el = null;
  let _pollTimer = null;
  let _currentRunId = null;

  function init() {
    _el = DOM.$('[data-view="backtesting"]');
    if (!_el) return;
    _render();
    _loadFormData();
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="page-header">
        <h1 class="page-header__title">Backtesting</h1>
        <p class="page-header__subtitle">Configure and run a backtest against historical market data.</p>
      </div>
      <div class="split-layout">
        <!-- Form panel -->
        <div class="split-layout__form">
          <div class="card">
            <div class="card__header"><span class="card__title">Configuration</span></div>
            <div class="card__body">
              <form id="bt-form" class="form">
                <div class="form-group">
                  <label class="form-label" for="bt-strategy">Strategy</label>
                  <select class="form-select" id="bt-strategy" name="strategy" required>
                    <option value="">Loading strategies…</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label" for="bt-exchange">Exchange</label>
                  <select class="form-select" id="bt-exchange" name="exchange">
                    <option value="binance">Binance</option>
                    <option value="kraken">Kraken</option>
                    <option value="ftx">FTX</option>
                    <option value="okx">OKX</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label" for="bt-pairs">Pairs <span class="form-hint">(hold Ctrl/Cmd for multiple)</span></label>
                  <select class="form-select form-select--multi" id="bt-pairs" name="pairs" multiple size="6" required>
                    <option value="">Select exchange first</option>
                  </select>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label" for="bt-timeframe">Timeframe</label>
                    <select class="form-select" id="bt-timeframe" name="timeframe">
                      <option value="1m">1m</option>
                      <option value="5m" selected>5m</option>
                      <option value="15m">15m</option>
                      <option value="30m">30m</option>
                      <option value="1h">1h</option>
                      <option value="4h">4h</option>
                      <option value="1d">1d</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="bt-timerange">Timerange</label>
                    <input class="form-input" id="bt-timerange" name="timerange" type="text" placeholder="20230101-20240101">
                  </div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label" for="bt-wallet">Starting Wallet</label>
                    <input class="form-input" id="bt-wallet" name="dry_run_wallet" type="number" value="1000" min="1">
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="bt-max-trades">Max Open Trades</label>
                    <input class="form-input" id="bt-max-trades" name="max_open_trades" type="number" value="3" min="1">
                  </div>
                </div>
                <div class="form-group">
                  <label class="form-label" for="bt-stake">Stake Amount</label>
                  <input class="form-input" id="bt-stake" name="stake_amount" type="text" value="unlimited">
                </div>
                <div class="form-actions">
                  <button type="submit" class="btn btn--primary" id="bt-run-btn">
                    <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor"><path d="M3 2l10 6-10 6V2z"/></svg>
                    Run Backtest
                  </button>
                  <button type="button" class="btn btn--danger" id="bt-stop-btn" style="display:none">Stop</button>
                </div>
              </form>
            </div>
          </div>
        </div>
        <!-- Output panel -->
        <div class="split-layout__output">
          <div class="card" id="bt-status-card" style="display:none">
            <div class="card__header">
              <span class="card__title">Status</span>
              <span class="badge" id="bt-status-badge">—</span>
            </div>
            <div class="card__body">
              <div class="log-panel" id="bt-logs"></div>
            </div>
          </div>
          <div class="card" id="bt-results-card" style="display:none">
            <div class="card__header"><span class="card__title">Results</span></div>
            <div class="card__body" id="bt-results-body"></div>
          </div>
        </div>
      </div>
    `);

    const form     = DOM.$('#bt-form', _el);
    const exchange = DOM.$('#bt-exchange', _el);
    const stopBtn  = DOM.$('#bt-stop-btn', _el);

    DOM.on(exchange, 'change', () => _loadPairs(exchange.value));
    DOM.on(form,     'submit', _onSubmit);
    DOM.on(stopBtn,  'click',  _onStop);
  }

  async function _loadFormData() {
    try {
      const [strats, lastCfg] = await Promise.all([
        API.getStrategies().catch(() => ({ strategies: [] })),
        API.getLastConfig().catch(() => ({ config: null })),
      ]);

      const select = DOM.$('#bt-strategy', _el);
      const strategies = strats.strategies || [];
      if (strategies.length) {
        select.innerHTML = strategies.map(s =>
          `<option value="${_esc(s.name || s)}">${_esc(s.name || s)}</option>`
        ).join('');
      } else {
        select.innerHTML = '<option value="">No strategies found</option>';
      }

      if (lastCfg.config) _applyLastConfig(lastCfg.config);

      const exVal = DOM.$('#bt-exchange', _el).value || 'binance';
      await _loadPairs(exVal);
    } catch (err) {
      Toast.warning('Could not load form data: ' + err.message);
    }
  }

  async function _loadPairs(exchange) {
    const sel = DOM.$('#bt-pairs', _el);
    if (!sel) return;
    sel.innerHTML = '<option value="">Loading…</option>';
    try {
      const data = await API.getPairs(exchange);
      const pairs = data.pairs || [];
      if (pairs.length) {
        sel.innerHTML = pairs.map(p => `<option value="${_esc(p)}">${_esc(p)}</option>`).join('');
      } else {
        sel.innerHTML = '<option value="">No pair data found</option>';
      }
    } catch {
      sel.innerHTML = '<option value="">Failed to load pairs</option>';
    }
  }

  function _applyLastConfig(cfg) {
    const set = (id, v) => { const el = DOM.$(id, _el); if (el && v != null) el.value = v; };
    set('#bt-strategy',   cfg.strategy);
    set('#bt-exchange',   cfg.exchange);
    set('#bt-timeframe',  cfg.timeframe);
    set('#bt-timerange',  cfg.timerange);
    set('#bt-wallet',     cfg.dry_run_wallet);
    set('#bt-max-trades', cfg.max_open_trades);
    set('#bt-stake',      cfg.stake_amount);
  }

  async function _onSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const fd   = new FormData(form);
    const pairsEl  = DOM.$('#bt-pairs', _el);
    const selectedPairs = [...(pairsEl?.selectedOptions || [])].map(o => o.value).filter(Boolean);

    if (!selectedPairs.length) { Toast.warning('Select at least one pair.'); return; }

    const body = {
      strategy:       fd.get('strategy'),
      pairs:          selectedPairs,
      timeframe:      fd.get('timeframe') || '5m',
      timerange:      fd.get('timerange') || null,
      dry_run_wallet: parseFloat(fd.get('dry_run_wallet')) || 1000,
      max_open_trades: parseInt(fd.get('max_open_trades')) || 3,
      stake_amount:   fd.get('stake_amount') || 'unlimited',
      exchange:       fd.get('exchange') || 'binance',
    };

    _setRunning(true);
    try {
      const res = await API.startBacktest(body);
      _currentRunId = res.run_id;
      AppState.set('stream', `Backtest started: ${_currentRunId}`);
      Auth.setRunning(true);
      _startPoll(_currentRunId);
      Toast.success('Backtest started.');
    } catch (err) {
      _setRunning(false);
      Toast.error('Failed to start backtest: ' + err.message);
    }
  }

  function _startPoll(runId) {
    _stopPoll();
    const card = DOM.$('#bt-status-card', _el);
    DOM.show(card);
    _pollTimer = setInterval(async () => {
      try {
        const data = await API.getRun(runId);
        _updateStatus(data);
        if (data.status === 'completed' || data.status === 'failed') {
          _stopPoll();
          _setRunning(false);
          Auth.setRunning(false);
          AppState.set('stream', `Backtest ${data.status}: ${runId}`);
          if (data.status === 'completed') Toast.success('Backtest completed.');
          else Toast.error('Backtest failed.');
        }
      } catch {}
    }, 2000);
  }

  function _updateStatus(data) {
    const badge = DOM.$('#bt-status-badge', _el);
    const logs  = DOM.$('#bt-logs', _el);
    const resCard = DOM.$('#bt-results-card', _el);
    const resBody = DOM.$('#bt-results-body', _el);

    if (badge) {
      badge.className = `badge badge--${FMT.statusColor(data.status)}`;
      badge.textContent = FMT.statusLabel(data.status);
    }
    if (logs) {
      logs.innerHTML = (data.logs || []).slice(-200).map(l => `<div class="log-line">${_esc(l)}</div>`).join('');
      logs.scrollTop = logs.scrollHeight;
    }
    if (data.status === 'completed' && data.results) {
      DOM.show(resCard);
      _renderResults(resBody, data.results);
    }
  }

  function _renderResults(el, results) {
    if (!el || !results) return;
    const ov = results.overview || {};
    el.innerHTML = `
      <div class="results-overview">
        ${_metric('Total Profit %',   FMT.pct((ov.profit_percent||0)*100), (ov.profit_percent||0)>0?'green':'red')}
        ${_metric('Profit (abs)',      FMT.currency(ov.profit_total_abs||0))}
        ${_metric('Total Trades',     ov.total_trades ?? '—')}
        ${_metric('Win Rate',         ov.win_rate != null ? FMT.pct((ov.win_rate||0)*100,1,false) : '—', 'muted')}
        ${_metric('Max Drawdown',     ov.max_drawdown != null ? FMT.pct(Math.abs((ov.max_drawdown||0)*100),1,false) : '—', 'red')}
        ${_metric('Sharpe Ratio',     FMT.number(ov.sharpe_ratio))}
        ${_metric('Final Balance',    FMT.currency(ov.final_balance))}
      </div>`;
  }

  function _metric(label, value, color = '') {
    return `<div class="metric-item"><span class="metric-label">${label}</span><span class="metric-value ${color ? 'text-' + color : ''}">${value}</span></div>`;
  }

  function _onStop() {
    if (!_currentRunId) return;
    _stopPoll();
    _setRunning(false);
    Auth.setRunning(false);
    Toast.info('Stopped polling. Job may still be running on server.');
  }

  function _setRunning(running) {
    const runBtn  = DOM.$('#bt-run-btn', _el);
    const stopBtn = DOM.$('#bt-stop-btn', _el);
    if (runBtn)  runBtn.disabled = running;
    if (running) DOM.show(stopBtn); else DOM.hide(stopBtn);
  }

  function _stopPoll() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
  }

  function _esc(str) {
    const d = document.createElement('div');
    d.textContent = String(str || '');
    return d.innerHTML;
  }

  function refresh() { _loadFormData(); }

  return { init, refresh };
})();
