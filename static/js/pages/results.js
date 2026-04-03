/* =================================================================
   RESULTS PAGE
   Exposes: window.ResultsPage
   ================================================================= */

window.ResultsPage = (() => {
  let _el = null;
  let _runs = [];
  let _sortKey = 'started_at';
  let _sortDir = -1;

  function init() {
    _el = DOM.$('[data-view="results"]');
    if (!_el) return;
    _render();
    load();
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="page-header">
        <h1 class="page-header__title">Results</h1>
        <p class="page-header__subtitle">Completed backtest runs with key performance metrics.</p>
      </div>
      <div id="results-table-wrap"><div class="empty-state">Loading…</div></div>
      <div id="result-detail-modal" class="modal">
        <div class="modal__backdrop"></div>
        <div class="modal__dialog" role="dialog" aria-modal="true" aria-labelledby="result-detail-title">
          <div class="modal__header">
            <h2 class="modal__title" id="result-detail-title">Run Detail</h2>
            <button class="modal__close" aria-label="Close">
              <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>
            </button>
          </div>
          <div class="modal__body" id="result-detail-body"></div>
        </div>
      </div>
    `);
    DOM.on(DOM.$('.modal__close', _el), 'click', () => Modal.close());
    DOM.on(DOM.$('.modal__backdrop', _el), 'click', () => Modal.close());
  }

  async function load() {
    try {
      const data = await API.getRuns();
      _runs = (data.runs || []).filter(r => r.status === 'completed');
      _renderTable();
    } catch (err) {
      Toast.error('Failed to load results: ' + err.message);
    }
  }

  function _sort(key) {
    if (_sortKey === key) _sortDir *= -1;
    else { _sortKey = key; _sortDir = -1; }
    _renderTable();
  }

  function _renderTable() {
    const wrap = DOM.$('#results-table-wrap', _el);
    if (!wrap) return;
    if (!_runs.length) {
      DOM.setHTML(wrap, '<div class="empty-state">No completed backtest runs yet.</div>');
      return;
    }
    const sorted = [..._runs].sort((a, b) => {
      const va = a[_sortKey] ?? '';
      const vb = b[_sortKey] ?? '';
      return typeof va === 'number'
        ? (va - vb) * _sortDir
        : String(va).localeCompare(String(vb)) * _sortDir;
    });

    const th = (key, label) => `<th class="sortable ${_sortKey === key ? 'sorted' : ''}" data-sort="${key}">${label}${_sortKey === key ? (_sortDir === 1 ? ' ▲' : ' ▼') : ''}</th>`;

    DOM.setHTML(wrap, `
      <table class="data-table data-table--hoverable">
        <thead><tr>
          ${th('run_id',      'Run ID')}
          ${th('strategy',   'Strategy')}
          ${th('started_at', 'Date')}
          <th>Profit %</th>
          <th>Trades</th>
          <th>Win Rate</th>
          <th>Drawdown</th>
          <th></th>
        </tr></thead>
        <tbody>
          ${sorted.map(r => {
            const ov = r.results?.overview || r.overview || {};
            const profit = ov.profit_total_abs ?? ov.profit_percent ?? null;
            const profitPct = ov.profit_percent ?? ov.profit_total ?? null;
            const trades = ov.total_trades ?? '—';
            const winRate = ov.win_rate != null ? FMT.pct(ov.win_rate * 100, 1, false) : '—';
            const dd = ov.max_drawdown != null ? FMT.pct(Math.abs(ov.max_drawdown * 100), 1, false) : '—';
            const color = profitPct > 0 ? 'green' : profitPct < 0 ? 'red' : 'muted';
            return `
              <tr class="cursor-pointer" data-run-id="${r.run_id || ''}">
                <td class="font-mono text-sm">${FMT.truncate(r.run_id || '—', 18)}</td>
                <td>${r.strategy || '—'}</td>
                <td class="text-muted text-sm">${FMT.tsShort(r.started_at)}</td>
                <td class="text-${color} font-semibold">${profitPct != null ? FMT.pct(profitPct * 100) : '—'}</td>
                <td>${trades}</td>
                <td>${winRate}</td>
                <td class="text-red">${dd}</td>
                <td><button class="btn btn--ghost btn--sm" data-detail-btn data-run-id="${r.run_id || ''}">View</button></td>
              </tr>`;
          }).join('')}
        </tbody>
      </table>`);

    wrap.querySelectorAll('[data-sort]').forEach(th => {
      DOM.on(th, 'click', () => _sort(th.dataset.sort));
    });
    wrap.querySelectorAll('[data-detail-btn]').forEach(btn => {
      DOM.on(btn, 'click', e => {
        e.stopPropagation();
        _showDetail(btn.dataset.runId);
      });
    });
    wrap.querySelectorAll('tr[data-run-id]').forEach(row => {
      DOM.on(row, 'click', () => _showDetail(row.dataset.runId));
    });
  }

  async function _showDetail(runId) {
    if (!runId) return;
    try {
      const data  = await API.getRun(runId);
      const ov    = data.results?.overview || {};
      const pairs = data.results?.per_pair || [];
      DOM.setHTML(DOM.$('#result-detail-title', _el), `Run: ${FMT.truncate(runId, 30)}`);
      DOM.setHTML(DOM.$('#result-detail-body', _el), `
        <div class="detail-grid">
          <div class="detail-item"><span class="detail-label">Strategy</span><span>${data.meta?.strategy || '—'}</span></div>
          <div class="detail-item"><span class="detail-label">Profit %</span><span class="text-${ov.profit_percent > 0 ? 'green' : 'red'} font-semibold">${FMT.pct((ov.profit_percent||0)*100)}</span></div>
          <div class="detail-item"><span class="detail-label">Profit (abs)</span><span>${FMT.currency(ov.profit_total_abs||0)}</span></div>
          <div class="detail-item"><span class="detail-label">Total Trades</span><span>${ov.total_trades ?? '—'}</span></div>
          <div class="detail-item"><span class="detail-label">Win Rate</span><span>${ov.win_rate != null ? FMT.pct((ov.win_rate||0)*100, 1, false) : '—'}</span></div>
          <div class="detail-item"><span class="detail-label">Max Drawdown</span><span class="text-red">${ov.max_drawdown != null ? FMT.pct(Math.abs((ov.max_drawdown||0)*100), 1, false) : '—'}</span></div>
          <div class="detail-item"><span class="detail-label">Sharpe Ratio</span><span>${FMT.number(ov.sharpe_ratio)}</span></div>
          <div class="detail-item"><span class="detail-label">Final Balance</span><span>${FMT.currency(ov.final_balance)}</span></div>
        </div>
        ${pairs.length ? `
          <div class="section-heading" style="margin-top:var(--space-4)">Per-Pair Performance</div>
          <table class="data-table data-table--sm">
            <thead><tr><th>Pair</th><th>Trades</th><th>Profit %</th></tr></thead>
            <tbody>${pairs.slice(0, 20).map(p => `
              <tr>
                <td class="font-mono">${p.key || p.pair || '—'}</td>
                <td>${p.trades ?? '—'}</td>
                <td class="text-${(p.profit_percent||0)>0?'green':'red'}">${FMT.pct((p.profit_percent||0)*100)}</td>
              </tr>`).join('')}
            </tbody>
          </table>` : ''}
      `);
      Modal.open('result-detail-modal');
    } catch (err) {
      Toast.error('Could not load run detail: ' + err.message);
    }
  }

  function refresh() { load(); }

  return { init, refresh };
})();
