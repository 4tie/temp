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
                  <label class="form-label" for="bt-pairs">
                    Pairs <span class="form-hint">(hold Ctrl/Cmd for multiple)</span>
                  </label>
                  <select class="form-select form-select--multi" id="bt-pairs" name="pairs" multiple size="6" required>
                    <option value="">Loading…</option>
                  </select>
                  <div id="bt-pairs-hint" class="form-hint" style="margin-top:4px"></div>
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

          <!-- Download Data card -->
          <div class="card" style="margin-top:var(--space-4)">
            <div class="card__header" style="cursor:pointer" id="bt-dl-toggle">
              <span class="card__title">Download Data</span>
              <span id="bt-dl-badge" class="badge" style="margin-left:auto"></span>
              <svg id="bt-dl-chevron" viewBox="0 0 16 16" width="14" height="14" fill="currentColor" style="margin-left:8px;transition:transform .2s"><path d="M4 6l4 4 4-4"/></svg>
            </div>
            <div class="card__body" id="bt-dl-body" style="display:none">
              <p class="text-muted text-sm" style="margin-bottom:var(--space-3)">
                Fetch historical OHLCV data for your selected pairs so they can be used in backtests.
                Select pairs above, choose timeframe and date range, then click Download.
              </p>
              <div class="form form--compact">
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label" for="bt-dl-exchange">Exchange</label>
                    <select class="form-select" id="bt-dl-exchange">
                      <option value="binance">Binance</option>
                      <option value="kraken">Kraken</option>
                      <option value="okx">OKX</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="bt-dl-timeframe">Timeframe</label>
                    <select class="form-select" id="bt-dl-timeframe">
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
                    <label class="form-label" for="bt-dl-days">Days</label>
                    <input class="form-input" id="bt-dl-days" type="number" value="365" min="1" max="1825">
                  </div>
                </div>
                <div class="form-actions" style="margin-top:0">
                  <button type="button" class="btn btn--secondary" id="bt-dl-btn">
                    <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 2v8M4 7l4 5 4-5"/><path d="M2 13h12"/></svg>
                    Download Data
                  </button>
                </div>
                <div id="bt-dl-log-wrap" style="display:none;margin-top:var(--space-3)">
                  <div class="log-panel" id="bt-dl-logs" style="max-height:160px"></div>
                </div>
              </div>
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
            <div class="card__header">
              <span class="card__title">Results</span>
              <button class="btn btn--danger btn--sm" id="bt-delete-btn">Delete Run</button>
            </div>
            <div class="card__body" id="bt-results-body"></div>
          </div>
          <div class="card" id="bt-history-card">
            <div class="card__header"><span class="card__title">Recent Runs</span></div>
            <div class="card__body" id="bt-history-body"><div class="empty-state">No runs yet.</div></div>
          </div>
        </div>
      </div>
    `);

    const form     = DOM.$('#bt-form', _el);
    const exchange = DOM.$('#bt-exchange', _el);
    const stopBtn  = DOM.$('#bt-stop-btn', _el);
    const delBtn   = DOM.$('#bt-delete-btn', _el);

    DOM.on(exchange, 'change', () => _loadPairs(exchange.value));
    DOM.on(form,     'submit', _onSubmit);
    DOM.on(stopBtn,  'click',  _onStop);
    DOM.on(delBtn,   'click',  _onDeleteRun);

    const dlToggle = DOM.$('#bt-dl-toggle', _el);
    const dlBody   = DOM.$('#bt-dl-body', _el);
    const dlBtn    = DOM.$('#bt-dl-btn', _el);
    const dlChevron = DOM.$('#bt-dl-chevron', _el);
    DOM.on(dlToggle, 'click', () => {
      const open = dlBody.style.display !== 'none';
      dlBody.style.display = open ? 'none' : '';
      if (dlChevron) dlChevron.style.transform = open ? '' : 'rotate(180deg)';
    });
    DOM.on(dlBtn, 'click', _onDownload);

    _loadHistory();
  }

  async function _loadHistory() {
    const wrap = DOM.$('#bt-history-body', _el);
    if (!wrap) return;
    try {
      const data = await API.getRuns();
      const runs = (data.runs || []).slice(-8).reverse();
      if (!runs.length) { wrap.innerHTML = '<div class="empty-state">No runs yet.</div>'; return; }
      wrap.innerHTML = `
        <table class="data-table data-table--sm">
          <thead><tr><th>Run ID</th><th>Strategy</th><th>Status</th><th>Started</th><th></th></tr></thead>
          <tbody>
            ${runs.map(r => `
              <tr>
                <td class="font-mono text-sm">${FMT.truncate(r.run_id || '—', 18)}</td>
                <td>${r.strategy || '—'}</td>
                <td><span class="badge badge--${FMT.statusColor(r.status)}">${FMT.statusLabel(r.status)}</span></td>
                <td class="text-muted text-sm">${FMT.tsShort(r.started_at)}</td>
                <td><button class="btn btn--danger btn--sm" data-delete-run="${_esc(r.run_id || '')}">Delete</button></td>
              </tr>`).join('')}
          </tbody>
        </table>`;
      wrap.querySelectorAll('[data-delete-run]').forEach(btn => {
        DOM.on(btn, 'click', () => _deleteRun(btn.dataset.deleteRun));
      });
    } catch {}
  }

  async function _onDeleteRun() {
    if (!_currentRunId) { Toast.warning('No active run to delete.'); return; }
    await _deleteRun(_currentRunId);
  }

  async function _deleteRun(runId) {
    if (!runId) return;
    if (!confirm(`Delete run ${runId}? This cannot be undone.`)) return;
    try {
      await API.deleteRun(runId);
      Toast.success(`Run deleted.`);
      if (runId === _currentRunId) {
        _currentRunId = null;
        DOM.hide(DOM.$('#bt-status-card', _el));
        DOM.hide(DOM.$('#bt-results-card', _el));
        AppState.set('stream', 'Run deleted.');
      }
      _loadHistory();
    } catch (err) {
      Toast.error('Failed to delete run: ' + err.message);
    }
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
      const local   = data.local_pairs   || [];
      const config  = data.config_pairs  || [];
      const popular = data.popular_pairs || [];
      const all     = data.pairs         || [];

      if (!all.length) {
        sel.innerHTML = '<option value="">No pairs found</option>';
        return;
      }

      let html = '';
      if (local.length) {
        html += `<optgroup label="⬤ Downloaded Data">` +
          local.map(p => `<option value="${_esc(p)}">${_esc(p)}</option>`).join('') +
          `</optgroup>`;
      }
      if (config.length) {
        html += `<optgroup label="⬤ From Config">` +
          config.map(p => `<option value="${_esc(p)}">${_esc(p)}</option>`).join('') +
          `</optgroup>`;
      }
      if (popular.length) {
        html += `<optgroup label="Popular Pairs">` +
          popular.map(p => `<option value="${_esc(p)}">${_esc(p)}</option>`).join('') +
          `</optgroup>`;
      }
      sel.innerHTML = html;

      const hint = DOM.$('#bt-pairs-hint', _el);
      if (hint) {
        if (local.length) {
          hint.textContent = `${local.length} pair(s) with downloaded data`;
          hint.style.color = 'var(--color-green)';
        } else {
          hint.textContent = 'No local data — select pairs and use Download Data to fetch history';
          hint.style.color = 'var(--color-amber)';
        }
      }
    } catch {
      sel.innerHTML = '<option value="">Failed to load pairs</option>';
    }
  }

  /* ── Download Data ── */
  let _dlPollTimer = null;

  async function _onDownload() {
    const exchange = DOM.$('#bt-dl-exchange', _el)?.value || 'binance';
    const tf       = DOM.$('#bt-dl-timeframe', _el)?.value || '5m';
    const days     = parseInt(DOM.$('#bt-dl-days', _el)?.value) || 30;
    const pairsSel = DOM.$('#bt-pairs', _el);
    const selected = [...(pairsSel?.selectedOptions || [])].map(o => o.value).filter(Boolean);

    if (!selected.length) { Toast.warning('Select at least one pair to download.'); return; }

    const btn     = DOM.$('#bt-dl-btn', _el);
    const logEl   = DOM.$('#bt-dl-logs', _el);
    const logWrap = DOM.$('#bt-dl-log-wrap', _el);
    const badge   = DOM.$('#bt-dl-badge', _el);

    if (btn) btn.disabled = true;
    if (logWrap) DOM.show(logWrap);
    if (badge) { badge.textContent = 'Running'; badge.className = 'badge badge--amber'; }

    try {
      const res = await API.downloadData({ pairs: selected, timeframe: tf, exchange, days });
      _pollDownload(res.job_id || res.run_id, logEl, badge, btn);
      Toast.info('Download started…');
    } catch (err) {
      if (btn) btn.disabled = false;
      if (badge) { badge.textContent = 'Error'; badge.className = 'badge badge--red'; }
      Toast.error('Download failed: ' + err.message);
    }
  }

  function _pollDownload(jobId, logEl, badge, btn) {
    if (_dlPollTimer) clearInterval(_dlPollTimer);
    _dlPollTimer = setInterval(async () => {
      try {
        const data = await API.getDownload(jobId);
        if (logEl) {
          logEl.innerHTML = (data.logs || []).slice(-100).map(l => `<div class="log-line">${_esc(l)}</div>`).join('');
          logEl.scrollTop = logEl.scrollHeight;
        }
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(_dlPollTimer);
          if (btn) btn.disabled = false;
          if (badge) {
            badge.textContent = data.status === 'completed' ? 'Done' : 'Failed';
            badge.className   = data.status === 'completed' ? 'badge badge--green' : 'badge badge--red';
          }
          if (data.status === 'completed') {
            Toast.success('Data downloaded. Refreshing pairs…');
            const ex = DOM.$('#bt-exchange', _el)?.value || 'binance';
            await _loadPairs(ex);
          } else {
            Toast.error('Download failed.');
          }
        }
      } catch {}
    }, 2500);
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
