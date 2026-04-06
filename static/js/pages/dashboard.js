/* =================================================================
   DASHBOARD PAGE
   Exposes: window.DashboardPage
   ================================================================= */

window.DashboardPage = (() => {
  let _el = null;

  function init() {
    _el = DOM.$('[data-view="dashboard"]');
    if (!_el) return;
    _render();
    load();
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="page-header">
        <h1 class="page-header__title">Dashboard</h1>
        <p class="page-header__subtitle">Overview of your trading strategies and recent activity.</p>
      </div>
      <div class="stat-grid" id="dash-stats">
        ${_statCard('Total Backtests', '—', 'green',  'dash-total-bt')}
        ${_statCard('Active Jobs',     '—', 'amber',  'dash-active-jobs')}
        ${_statCard('Hyperopt Runs',   '—', 'violet', 'dash-total-ho')}
        ${_statCard('Strategies',      '—', 'muted',  'dash-strategies')}
      </div>
      <div class="dashboard-grid">
        <section class="card card--fill dashboard-panel">
          <div class="card__header">
            <span class="card__title">Recent Backtest Runs</span>
          </div>
          <div class="card__body card__body--flush" id="dash-recent-runs"><div class="empty-state">Loading…</div></div>
        </section>
        <section class="card card--fill dashboard-panel">
          <div class="card__header">
            <span class="card__title">Recent Hyperopt Runs</span>
          </div>
          <div class="card__body card__body--flush" id="dash-recent-hyperopt"><div class="empty-state">Loading…</div></div>
        </section>
      </div>
    `);
  }

  function _statCard(label, value, accent, id) {
    return `
      <div class="stat-card stat-card--${accent}">
        <div class="stat-card__value" id="${id}">${value}</div>
        <div class="stat-card__label">${label}</div>
      </div>`;
  }

  async function load() {
    try {
      const [runsData, hoData, strategiesData] = await Promise.all([
        API.getRuns().catch(() => ({ runs: [] })),
        API.getHyperoptRuns().catch(() => ({ runs: [] })),
        API.getStrategies().catch(() => ({ strategies: [] })),
      ]);

      const runs     = runsData.runs     || [];
      const hoRuns   = hoData.runs       || [];
      const strats   = strategiesData.strategies || [];
      const active   = runs.filter(r => r.status === 'running').length
                     + hoRuns.filter(r => r.status === 'running').length;

      DOM.setText(DOM.$('#dash-total-bt'),     String(runs.length));
      DOM.setText(DOM.$('#dash-active-jobs'),  String(active));
      DOM.setText(DOM.$('#dash-total-ho'),     String(hoRuns.length));
      DOM.setText(DOM.$('#dash-strategies'),   String(strats.length));
      AppState.set('activeJobs', active);

      _renderRunsTable('#dash-recent-runs', runs.slice(-5).reverse(), 'backtest');
      _renderRunsTable('#dash-recent-hyperopt', hoRuns.slice(-5).reverse(), 'hyperopt');
    } catch (err) {
      Toast.error('Failed to load dashboard: ' + err.message);
    }
  }

  function _renderRunsTable(selector, rows, type) {
    const el = DOM.$(_el.id ? `#${_el.id} ${selector}` : selector) || DOM.$(selector);
    if (!el) return;
    if (!rows.length) {
      DOM.setHTML(el, '<div class="empty-state">No runs yet.</div>');
      return;
    }
    DOM.setHTML(el, `
      <table class="data-table">
        <thead><tr>
          <th>Run ID</th><th>Strategy</th><th>Status</th><th>Started</th>
        </tr></thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              <td class="font-mono text-sm">${FMT.truncate(r.run_id || r.id || '—', 20)}</td>
              <td>${_displayStrategy(r)}</td>
              <td><span class="badge badge--${FMT.statusColor(r.status)}">${FMT.statusLabel(r.status)}</span></td>
              <td class="text-muted text-sm">${FMT.ts(r.started_at)}</td>
            </tr>`).join('')}
        </tbody>
      </table>`);
  }

  function _displayStrategy(run) {
    const base = run.display_strategy || run.strategy || '—';
    const version = run.display_version || run.strategy_version || null;
    return version ? `${base} · ${version}` : base;
  }

  function refresh() { load(); }

  return { init, refresh };
})();
