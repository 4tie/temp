/* =================================================================
   JOBS PAGE
   Exposes: window.JobsPage
   ================================================================= */

window.JobsPage = (() => {
  let _el = null;
  let _pollTimer = null;

  function init() {
    _el = DOM.$('[data-view="jobs"]');
    if (!_el) return;
    _render();
    load();
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="page-header">
        <h1 class="page-header__title">Jobs</h1>
        <p class="page-header__subtitle">All active and recent backtest and hyperopt jobs.</p>
      </div>
      <div class="toolbar">
        <button class="btn btn--secondary btn--sm" id="jobs-refresh-btn">
          <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M13.5 2.5A6.5 6.5 0 0 0 2 8"/>
            <path d="M2.5 13.5A6.5 6.5 0 0 0 14 8"/>
            <polyline points="13.5,2.5 13.5,5.5 10.5,5.5" stroke-linejoin="round"/>
            <polyline points="2.5,13.5 2.5,10.5 5.5,10.5" stroke-linejoin="round"/>
          </svg>
          Refresh
        </button>
      </div>
      <div id="jobs-table-wrap"><div class="empty-state">Loading…</div></div>
    `);
    DOM.on(DOM.$('#jobs-refresh-btn', _el), 'click', load);
  }

  async function load() {
    _stopPoll();
    try {
      const [btData, hoData] = await Promise.all([
        API.getRuns().catch(() => ({ runs: [] })),
        API.getHyperoptRuns().catch(() => ({ runs: [] })),
      ]);

      const btRuns  = (btData.runs  || []).map(r => ({ ...r, type: 'Backtest' }));
      const hoRuns  = (hoData.runs  || []).map(r => ({ ...r, type: 'Hyperopt' }));
      const all     = [...btRuns, ...hoRuns].sort((a, b) =>
        (b.started_at || '').localeCompare(a.started_at || '')
      );

      const active = all.filter(r => r.status === 'running').length;
      AppState.set('activeJobs', active);

      _renderTable(all);

      if (active > 0) {
        _pollTimer = setInterval(load, 5000);
      }
    } catch (err) {
      Toast.error('Failed to load jobs: ' + err.message);
    }
  }

  function _renderTable(rows) {
    const wrap = DOM.$('#jobs-table-wrap', _el);
    if (!wrap) return;
    if (!rows.length) {
      DOM.setHTML(wrap, '<div class="empty-state">No jobs found.</div>');
      return;
    }
    DOM.setHTML(wrap, `
      <table class="data-table">
        <thead><tr>
          <th>Run ID</th><th>Type</th><th>Strategy</th>
          <th>Status</th><th>Started</th>
        </tr></thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              <td class="font-mono text-sm">${FMT.truncate(r.run_id || r.id || '—', 22)}</td>
              <td><span class="badge badge--violet">${r.type}</span></td>
              <td>${r.strategy || '—'}</td>
              <td><span class="badge badge--${FMT.statusColor(r.status)}">${FMT.statusLabel(r.status)}</span></td>
              <td class="text-muted text-sm">${FMT.ts(r.started_at)}</td>
            </tr>`).join('')}
        </tbody>
      </table>`);
  }

  function _stopPoll() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
  }

  function refresh() { load(); }

  return { init, refresh };
})();
