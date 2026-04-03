/* =================================================================
   HYPEROPT PAGE
   Exposes: window.HyperoptPage
   ================================================================= */

window.HyperoptPage = (() => {
  let _el = null;
  let _pollTimer = null;
  let _currentRunId = null;

  function init() {
    _el = DOM.$('[data-view="hyperopt"]');
    if (!_el) return;
    _render();
    _loadFormData();
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="page-header">
        <h1 class="page-header__title">Hyperopt</h1>
        <p class="page-header__subtitle">Optimize strategy parameters using hyperparameter search.</p>
      </div>
      <div class="split-layout">
        <div class="split-layout__form">
          <div class="card">
            <div class="card__header"><span class="card__title">Configuration</span></div>
            <div class="card__body">
              <form id="ho-form" class="form">
                <div class="form-group">
                  <label class="form-label" for="ho-strategy">Strategy</label>
                  <select class="form-select" id="ho-strategy" name="strategy" required>
                    <option value="">Loading…</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label" for="ho-exchange">Exchange</label>
                  <select class="form-select" id="ho-exchange" name="exchange">
                    <option value="binance">Binance</option>
                    <option value="kraken">Kraken</option>
                    <option value="okx">OKX</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label" for="ho-pairs">Pairs <span class="form-hint">(hold Ctrl/Cmd for multiple)</span></label>
                  <select class="form-select form-select--multi" id="ho-pairs" name="pairs" multiple size="5" required>
                    <option value="">Loading…</option>
                  </select>
                  <div id="ho-pairs-hint" class="form-hint" style="margin-top:4px"></div>
                </div>
                <div class="form-group">
                  <label class="form-label" for="ho-loss">Loss Function</label>
                  <select class="form-select" id="ho-loss" name="loss_function">
                    <option value="">Loading…</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Spaces</label>
                  <div class="checkbox-group" id="ho-spaces"></div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label" for="ho-epochs">Epochs</label>
                    <input class="form-input" id="ho-epochs" name="epochs" type="number" value="100" min="10">
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="ho-jobs">Jobs</label>
                    <input class="form-input" id="ho-jobs" name="jobs" type="number" value="1" min="1">
                  </div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label" for="ho-timeframe">Timeframe</label>
                    <select class="form-select" id="ho-timeframe" name="timeframe">
                      <option value="5m" selected>5m</option>
                      <option value="15m">15m</option>
                      <option value="1h">1h</option>
                      <option value="4h">4h</option>
                      <option value="1d">1d</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="ho-timerange">Timerange</label>
                    <input class="form-input" id="ho-timerange" name="timerange" type="text" placeholder="20230101-20240101">
                  </div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label" for="ho-wallet">Wallet</label>
                    <input class="form-input" id="ho-wallet" name="dry_run_wallet" type="number" value="1000">
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="ho-min-trades">Min Trades</label>
                    <input class="form-input" id="ho-min-trades" name="min_trades" type="number" value="1">
                  </div>
                </div>
                <div class="form-actions">
                  <button type="submit" class="btn btn--primary" id="ho-run-btn">
                    <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor"><path d="M3 2l10 6-10 6V2z"/></svg>
                    Start Hyperopt
                  </button>
                  <button type="button" class="btn btn--danger" id="ho-stop-btn" style="display:none">Stop</button>
                </div>
              </form>
            </div>
          </div>

          <!-- Download Data card -->
          <div class="card" style="margin-top:var(--space-4)">
            <div class="card__header" style="cursor:pointer" id="ho-dl-toggle">
              <span class="card__title">Download Data</span>
              <span id="ho-dl-badge" class="badge" style="margin-left:auto"></span>
              <svg id="ho-dl-chevron" viewBox="0 0 16 16" width="14" height="14" fill="currentColor" style="margin-left:8px;transition:transform .2s"><path d="M4 6l4 4 4-4"/></svg>
            </div>
            <div class="card__body" id="ho-dl-body" style="display:none">
              <p class="text-muted text-sm" style="margin-bottom:var(--space-3)">
                Select pairs above, set timeframe &amp; days, then download historical OHLCV data for hyperopt.
              </p>
              <div class="form form--compact">
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label" for="ho-dl-exchange">Exchange</label>
                    <select class="form-select" id="ho-dl-exchange">
                      <option value="binance">Binance</option>
                      <option value="kraken">Kraken</option>
                      <option value="okx">OKX</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="ho-dl-timeframe">Timeframe</label>
                    <select class="form-select" id="ho-dl-timeframe">
                      <option value="1m">1m</option>
                      <option value="5m" selected>5m</option>
                      <option value="15m">15m</option>
                      <option value="1h">1h</option>
                      <option value="4h">4h</option>
                      <option value="1d">1d</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="ho-dl-days">Days</label>
                    <input class="form-input" id="ho-dl-days" type="number" value="365" min="1" max="1825">
                  </div>
                </div>
                <div class="form-actions" style="margin-top:0">
                  <button type="button" class="btn btn--secondary" id="ho-dl-btn">
                    <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 2v8M4 7l4 5 4-5"/><path d="M2 13h12"/></svg>
                    Download Data
                  </button>
                </div>
                <div id="ho-dl-log-wrap" style="display:none;margin-top:var(--space-3)">
                  <div class="log-panel" id="ho-dl-logs" style="max-height:160px"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="split-layout__output">
          <div class="card" id="ho-status-card" style="display:none">
            <div class="card__header">
              <span class="card__title">Progress</span>
              <span class="badge" id="ho-status-badge">—</span>
            </div>
            <div class="card__body">
              <div class="progress-panel" id="ho-progress"></div>
              <div class="log-panel" id="ho-logs"></div>
            </div>
          </div>
          <div class="card" id="ho-results-card" style="display:none">
            <div class="card__header">
              <span class="card__title">Best Results</span>
              <button class="btn btn--secondary btn--sm" id="ho-apply-btn" style="display:none">Apply Params</button>
            </div>
            <div class="card__body" id="ho-results-body"></div>
          </div>
          <div class="card">
            <div class="card__header"><span class="card__title">Previous Runs</span></div>
            <div class="card__body" id="ho-history"></div>
          </div>
        </div>
      </div>
    `);

    DOM.on(DOM.$('#ho-exchange', _el), 'change', e => _loadPairs(e.target.value));
    DOM.on(DOM.$('#ho-form',     _el), 'submit', _onSubmit);
    DOM.on(DOM.$('#ho-stop-btn', _el), 'click',  _onStop);
    DOM.on(DOM.$('#ho-apply-btn',_el), 'click',  _onApply);

    const dlToggle  = DOM.$('#ho-dl-toggle', _el);
    const dlBody    = DOM.$('#ho-dl-body', _el);
    const dlBtn     = DOM.$('#ho-dl-btn', _el);
    const dlChevron = DOM.$('#ho-dl-chevron', _el);
    DOM.on(dlToggle, 'click', () => {
      const open = dlBody.style.display !== 'none';
      dlBody.style.display = open ? 'none' : '';
      if (dlChevron) dlChevron.style.transform = open ? '' : 'rotate(180deg)';
    });
    DOM.on(dlBtn, 'click', _onDownload);
  }

  async function _loadFormData() {
    try {
      const [strats, lossFns, spaces] = await Promise.all([
        API.getStrategies().catch(() => ({ strategies: [] })),
        API.getLossFunctions().catch(() => ({ loss_functions: [] })),
        API.getHyperoptSpaces().catch(() => ({ spaces: [] })),
      ]);

      const stratSel = DOM.$('#ho-strategy', _el);
      stratSel.innerHTML = (strats.strategies || []).map(s =>
        `<option value="${_esc(s.name || s)}">${_esc(s.name || s)}</option>`
      ).join('') || '<option value="">No strategies</option>';

      const lossSel = DOM.$('#ho-loss', _el);
      lossSel.innerHTML = (lossFns.loss_functions || []).map(f =>
        `<option value="${_esc(f.name)}"${f.name === 'SharpeHyperOptLossDaily' ? ' selected' : ''}>${_esc(f.label)}</option>`
      ).join('');

      const spacesEl = DOM.$('#ho-spaces', _el);
      spacesEl.innerHTML = (spaces.spaces || []).map(s => `
        <label class="checkbox-label">
          <input type="checkbox" name="spaces" value="${_esc(s.value)}"${s.value === 'default' ? ' checked' : ''}>
          ${_esc(s.label)}
        </label>`).join('');

      const exVal = DOM.$('#ho-exchange', _el).value || 'binance';
      await _loadPairs(exVal);
      await _loadHistory();
    } catch (err) {
      Toast.warning('Could not fully load hyperopt form: ' + err.message);
    }
  }

  async function _loadPairs(exchange) {
    const sel = DOM.$('#ho-pairs', _el);
    if (!sel) return;
    sel.innerHTML = '<option value="">Loading…</option>';
    try {
      const data    = await API.getPairs(exchange);
      const local   = data.local_pairs   || [];
      const config  = data.config_pairs  || [];
      const popular = data.popular_pairs || [];
      const all     = data.pairs         || [];

      if (!all.length) { sel.innerHTML = '<option value="">No pairs found</option>'; return; }

      let html = '';
      if (local.length)   html += `<optgroup label="⬤ Downloaded Data">`  + local.map(p   => `<option value="${_esc(p)}">${_esc(p)}</option>`).join('') + '</optgroup>';
      if (config.length)  html += `<optgroup label="⬤ From Config">`       + config.map(p  => `<option value="${_esc(p)}">${_esc(p)}</option>`).join('') + '</optgroup>';
      if (popular.length) html += `<optgroup label="Popular Pairs">`        + popular.map(p => `<option value="${_esc(p)}">${_esc(p)}</option>`).join('') + '</optgroup>';
      sel.innerHTML = html;

      const hint = DOM.$('#ho-pairs-hint', _el);
      if (hint) {
        if (local.length) { hint.textContent = `${local.length} pair(s) with downloaded data`; hint.style.color = 'var(--color-green)'; }
        else              { hint.textContent = 'No local data — use Download Data to fetch history'; hint.style.color = 'var(--color-amber)'; }
      }
    } catch {
      sel.innerHTML = '<option value="">Failed to load pairs</option>';
    }
  }

  /* ── Download Data ── */
  let _dlPollTimer = null;

  async function _onDownload() {
    const exchange = DOM.$('#ho-dl-exchange', _el)?.value || 'binance';
    const tf       = DOM.$('#ho-dl-timeframe', _el)?.value || '5m';
    const days     = parseInt(DOM.$('#ho-dl-days', _el)?.value) || 30;
    const pairsSel = DOM.$('#ho-pairs', _el);
    const selected = [...(pairsSel?.selectedOptions || [])].map(o => o.value).filter(Boolean);

    if (!selected.length) { Toast.warning('Select at least one pair to download.'); return; }

    const btn     = DOM.$('#ho-dl-btn', _el);
    const logEl   = DOM.$('#ho-dl-logs', _el);
    const logWrap = DOM.$('#ho-dl-log-wrap', _el);
    const badge   = DOM.$('#ho-dl-badge', _el);

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
          if (badge) { badge.textContent = data.status === 'completed' ? 'Done' : 'Failed'; badge.className = data.status === 'completed' ? 'badge badge--green' : 'badge badge--red'; }
          if (data.status === 'completed') {
            Toast.success('Data downloaded. Refreshing pairs…');
            await _loadPairs(DOM.$('#ho-exchange', _el)?.value || 'binance');
          } else {
            Toast.error('Download failed.');
          }
        }
      } catch {}
    }, 2500);
  }

  async function _loadHistory() {
    const histEl = DOM.$('#ho-history', _el);
    if (!histEl) return;
    try {
      const data  = await API.getHyperoptRuns();
      const runs  = (data.runs || []).slice(-5).reverse();
      if (!runs.length) { histEl.innerHTML = '<div class="empty-state">No previous runs.</div>'; return; }
      histEl.innerHTML = `
        <table class="data-table data-table--sm">
          <thead><tr><th>Run ID</th><th>Strategy</th><th>Status</th><th>Epochs</th></tr></thead>
          <tbody>${runs.map(r => `
            <tr>
              <td class="font-mono text-sm">${FMT.truncate(r.run_id || '—', 18)}</td>
              <td>${r.strategy || '—'}</td>
              <td><span class="badge badge--${FMT.statusColor(r.status)}">${FMT.statusLabel(r.status)}</span></td>
              <td>${r.epochs ?? '—'}</td>
            </tr>`).join('')}
          </tbody>
        </table>`;
    } catch {}
  }

  async function _onSubmit(e) {
    e.preventDefault();
    const fd      = new FormData(e.target);
    const pairs   = [...(DOM.$('#ho-pairs', _el)?.selectedOptions || [])].map(o => o.value).filter(Boolean);
    const spaces  = fd.getAll('spaces').filter(Boolean);
    if (!pairs.length)  { Toast.warning('Select at least one pair.'); return; }
    if (!spaces.length) { Toast.warning('Select at least one space.'); return; }

    const body = {
      strategy:       fd.get('strategy'),
      pairs,
      timeframe:      fd.get('timeframe') || '5m',
      timerange:      fd.get('timerange') || null,
      epochs:         parseInt(fd.get('epochs')) || 100,
      spaces,
      loss_function:  fd.get('loss_function') || 'SharpeHyperOptLossDaily',
      jobs:           parseInt(fd.get('jobs')) || 1,
      min_trades:     parseInt(fd.get('min_trades')) || 1,
      dry_run_wallet: parseFloat(fd.get('dry_run_wallet')) || 1000,
      exchange:       fd.get('exchange') || 'binance',
    };

    _setRunning(true);
    try {
      const res = await API.startHyperopt(body);
      _currentRunId = res.run_id;
      DOM.show(DOM.$('#ho-status-card', _el));
      Auth.setRunning(true);
      _startPoll(_currentRunId);
      Toast.success('Hyperopt started.');
    } catch (err) {
      _setRunning(false);
      Toast.error('Failed to start hyperopt: ' + err.message);
    }
  }

  function _startPoll(runId) {
    _stopPoll();
    _pollTimer = setInterval(async () => {
      try {
        const data = await API.getHyperoptRun(runId);
        _updateStatus(data);
        if (data.status === 'completed' || data.status === 'failed') {
          _stopPoll();
          _setRunning(false);
          Auth.setRunning(false);
          if (data.status === 'completed') Toast.success('Hyperopt completed.');
          else Toast.error('Hyperopt failed.');
          _loadHistory();
        }
      } catch {}
    }, 3000);
  }

  function _updateStatus(data) {
    const badge    = DOM.$('#ho-status-badge', _el);
    const logsEl   = DOM.$('#ho-logs', _el);
    const progressEl = DOM.$('#ho-progress', _el);
    const resCard  = DOM.$('#ho-results-card', _el);
    const resBody  = DOM.$('#ho-results-body', _el);
    const applyBtn = DOM.$('#ho-apply-btn', _el);

    if (badge) { badge.className = `badge badge--${FMT.statusColor(data.status)}`; badge.textContent = FMT.statusLabel(data.status); }

    if (data.progress && progressEl) {
      const p = data.progress;
      const pct = p.total_epochs > 0 ? Math.round((p.current_epoch / p.total_epochs) * 100) : 0;
      progressEl.innerHTML = `
        <div class="progress-bar-wrap">
          <div class="progress-bar" style="width:${pct}%"></div>
        </div>
        <div class="progress-meta">
          <span>Epoch ${p.current_epoch} / ${p.total_epochs}</span>
          ${p.best_profit_pct != null ? `<span>Best profit: <strong class="text-green">${FMT.pct(p.best_profit_pct)}</strong></span>` : ''}
          ${p.best_trades ? `<span>Best trades: ${p.best_trades}</span>` : ''}
        </div>`;
    }

    if (logsEl) {
      logsEl.innerHTML = (data.logs || []).slice(-100).map(l => `<div class="log-line">${_esc(l)}</div>`).join('');
      logsEl.scrollTop = logsEl.scrollHeight;
    }

    if (data.status === 'completed' && data.results) {
      DOM.show(resCard);
      DOM.show(applyBtn);
      _renderHoResults(resBody, data.results, data.meta);
    }
  }

  function _renderHoResults(el, results, meta) {
    if (!el) return;
    const best = Array.isArray(results) ? results[0] : results;
    if (!best) { el.innerHTML = '<div class="empty-state">No results.</div>'; return; }
    const params = best.params || best.parameters || {};
    el.innerHTML = `
      <div class="results-overview" style="margin-bottom:var(--space-4)">
        ${_metric('Profit %',   FMT.pct(best.profit_percent ?? best.profit ?? 0), (best.profit_percent||0)>0?'green':'red')}
        ${_metric('Trades',     best.trade_count ?? best.total_trades ?? '—')}
        ${_metric('Win Rate',   best.win_rate != null ? FMT.pct((best.win_rate||0)*100,1,false) : '—')}
        ${_metric('Drawdown',   best.max_drawdown != null ? FMT.pct(Math.abs((best.max_drawdown||0)*100),1,false) : '—', 'red')}
      </div>
      ${Object.keys(params).length ? `
        <div class="section-heading">Best Parameters</div>
        <table class="data-table data-table--sm">
          <thead><tr><th>Parameter</th><th>Value</th></tr></thead>
          <tbody>${Object.entries(params).map(([k, v]) => `<tr><td class="font-mono">${_esc(k)}</td><td>${_esc(String(v))}</td></tr>`).join('')}</tbody>
        </table>` : ''}`;
  }

  function _metric(label, value, color = '') {
    return `<div class="metric-item"><span class="metric-label">${label}</span><span class="metric-value ${color ? 'text-' + color : ''}">${value}</span></div>`;
  }

  async function _onApply() {
    if (!_currentRunId) return;
    const strategy = DOM.$('#ho-strategy', _el)?.value;
    if (!strategy) { Toast.warning('No strategy selected.'); return; }
    try {
      const data = await API.getHyperoptRun(_currentRunId);
      const results = data.results;
      const best = Array.isArray(results) ? results[0] : results;
      if (!best?.params) { Toast.warning('No params to apply.'); return; }
      await API.applyHyperoptParams({ strategy, params: best.params });
      Toast.success('Parameters applied to strategy file.');
    } catch (err) {
      Toast.error('Failed to apply params: ' + err.message);
    }
  }

  function _onStop() {
    _stopPoll();
    _setRunning(false);
    Auth.setRunning(false);
    Toast.info('Stopped polling.');
  }

  function _setRunning(running) {
    const runBtn  = DOM.$('#ho-run-btn', _el);
    const stopBtn = DOM.$('#ho-stop-btn', _el);
    if (runBtn) runBtn.disabled = running;
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

  function refresh() { _loadHistory(); }

  return { init, refresh };
})();
