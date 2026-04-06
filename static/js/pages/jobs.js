/* =================================================================
   JOBS PAGE
   Exposes: window.JobsPage
   ================================================================= */

window.JobsPage = (() => {
  let _el = null;
  let _pollTimer = null;
  const _SOURCE_LABELS = {
    backtest: 'Backtest',
    hyperopt: 'Hyperopt',
    download: 'Download',
    ai_loop: 'AI Loop',
    evolution: 'Evolution',
  };

  function init() {
    _el = DOM.$('[data-view="jobs"]');
    if (!_el) return;
    _render();
    load();
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="jobs-page" id="jobs-page">
        <div class="page-header">
          <h1 class="page-header__title">Jobs</h1>
          <p class="page-header__subtitle">All active jobs plus a unified activity log for background events.</p>
          <div class="page-header__meta" id="jobs-meta">Waiting for job data…</div>
        </div>
        <div class="jobs-toolbar">
          <div class="jobs-summary" id="jobs-summary">
            <div class="empty-state">Loading…</div>
          </div>
          <div class="toolbar jobs-toolbar__actions">
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
        </div>
        <div class="card jobs-table-card">
          <div class="card__header">
            <span class="card__title">Run Monitor</span>
            <span class="badge badge--muted" id="jobs-total-badge">0 jobs</span>
          </div>
          <div class="card__body card__body--flush" id="jobs-table-wrap"><div class="empty-state">Loading…</div></div>
        </div>
        <div class="card jobs-activity-card">
          <div class="card__header">
            <span class="card__title">Activity Timeline</span>
            <span class="badge badge--muted" id="jobs-activity-badge">0 events</span>
          </div>
          <div class="card__body" id="jobs-activity-wrap"><div class="empty-state">Loading…</div></div>
        </div>
      </div>
    `);
    DOM.on(DOM.$('#jobs-refresh-btn', _el), 'click', load);
  }

  async function load() {
    _stopPoll();
    try {
      const [btData, hoData, activityData] = await Promise.all([
        API.getRuns().catch(() => ({ runs: [] })),
        API.getHyperoptRuns().catch(() => ({ runs: [] })),
        API.getActivity(120).catch(() => ({ events: [] })),
      ]);

      const btRuns  = (btData.runs  || []).map(r => ({ ...r, type: 'Backtest' }));
      const hoRuns  = (hoData.runs  || []).map(r => ({ ...r, type: 'Hyperopt' }));
      const all     = [...btRuns, ...hoRuns].sort((a, b) =>
        (b.started_at || '').localeCompare(a.started_at || '')
      );
      const events = activityData.events || [];

      const active = all.filter(r => r.status === 'running').length;
      const activeEventCount = events.filter(event => String(event.status || '').toLowerCase() === 'running').length;
      AppState.set('activeJobs', active);

      _renderSummary(all, events);
      _renderTable(all);
      _renderActivity(events);

      if (active > 0 || activeEventCount > 0) {
        _pollTimer = setInterval(load, 5000);
      }
    } catch (err) {
      Toast.error('Failed to load jobs: ' + err.message);
    }
  }

  function _renderSummary(rows, events) {
    const summary = DOM.$('#jobs-summary', _el);
    const meta = DOM.$('#jobs-meta', _el);
    const totalBadge = DOM.$('#jobs-total-badge', _el);
    const activityBadge = DOM.$('#jobs-activity-badge', _el);
    if (meta) {
      const running = rows.filter(r => r.status === 'running').length;
      const latestEvent = events && events.length ? events[0] : null;
      meta.textContent = running
        ? `${running} active job${running === 1 ? '' : 's'} polling live.`
        : (latestEvent
          ? `No active jobs. Latest event: ${latestEvent.message || _formatAction(latestEvent.action)}.`
          : 'No active jobs. Snapshot reflects the latest persisted runs.');
    }
    if (totalBadge) {
      totalBadge.textContent = `${rows.length} job${rows.length === 1 ? '' : 's'}`;
    }
    if (activityBadge) {
      activityBadge.textContent = `${events.length} event${events.length === 1 ? '' : 's'}`;
    }
    if (!summary) return;

    const counts = {
      total: rows.length,
      running: rows.filter(r => r.status === 'running').length,
      completed: rows.filter(r => r.status === 'completed').length,
      failed: rows.filter(r => r.status === 'failed').length,
    };

    summary.innerHTML = `
      <div class="stat-card stat-card--muted jobs-stat-card">
        <span class="stat-card__value">${counts.total}</span>
        <span class="stat-card__label">Total</span>
      </div>
      <div class="stat-card stat-card--violet jobs-stat-card">
        <span class="stat-card__value">${counts.running}</span>
        <span class="stat-card__label">Running</span>
      </div>
      <div class="stat-card stat-card--green jobs-stat-card">
        <span class="stat-card__value">${counts.completed}</span>
        <span class="stat-card__label">Completed</span>
      </div>
      <div class="stat-card stat-card--red jobs-stat-card">
        <span class="stat-card__value">${counts.failed}</span>
        <span class="stat-card__label">Failed</span>
      </div>
    `;
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
              <td><span class="badge jobs-type-pill">${r.type}</span></td>
              <td>${r.strategy || '—'}</td>
              <td><span class="badge badge--${FMT.statusColor(r.status)}">${FMT.statusLabel(r.status)}</span></td>
              <td class="text-muted text-sm">${FMT.ts(r.started_at)}</td>
            </tr>`).join('')}
        </tbody>
      </table>`);
  }

  function _renderActivity(events) {
    const wrap = DOM.$('#jobs-activity-wrap', _el);
    if (!wrap) return;
    if (!events.length) {
      DOM.setHTML(wrap, '<div class="empty-state">No activity has been logged yet.</div>');
      return;
    }
    DOM.setHTML(wrap, `
      <div class="jobs-activity-list">
        ${events.map(event => `
          <article class="jobs-activity-item">
            <div class="jobs-activity-item__head">
              <div class="jobs-activity-item__badges">
                <span class="badge jobs-type-pill">${_esc(_sourceLabel(event.source))}</span>
                <span class="badge badge--muted">${_esc(_categoryLabel(event.category))}</span>
                <span class="badge badge--${_statusTone(event.status)}">${_esc(_formatAction(event.action))}</span>
              </div>
              <span class="text-muted text-sm">${_esc(FMT.ts(event.timestamp))}</span>
            </div>
            <div class="jobs-activity-item__message">${_esc(event.message || _defaultMessage(event))}</div>
            <div class="jobs-activity-item__detail text-muted text-sm">${_esc(_detailLine(event))}</div>
          </article>
        `).join('')}
      </div>
    `);
  }

  function _sourceLabel(source) {
    return _SOURCE_LABELS[String(source || '').toLowerCase()] || String(source || 'App');
  }

  function _categoryLabel(category) {
    return String(category || 'event').toLowerCase() === 'job' ? 'Job' : 'Event';
  }

  function _statusTone(status) {
    const value = String(status || '').toLowerCase();
    if (value === 'completed' || value === 'ok') return 'green';
    if (value === 'running') return 'amber';
    if (value === 'failed' || value === 'stopped') return 'red';
    if (value === 'warning') return 'amber';
    return 'muted';
  }

  function _formatAction(action) {
    const raw = String(action || 'event').replace(/[_-]+/g, ' ').trim();
    if (!raw) return 'Event';
    return raw.charAt(0).toUpperCase() + raw.slice(1);
  }

  function _defaultMessage(event) {
    return `${_sourceLabel(event.source)} ${_formatAction(event.action).toLowerCase()}.`;
  }

  function _detailLine(event) {
    const parts = [];
    if (event.run_id) parts.push(`Run ${event.run_id}`);
    else if (event.job_id) parts.push(`Job ${event.job_id}`);
    if (event.loop_id) parts.push(`Loop ${event.loop_id}`);
    if (event.strategy) parts.push(event.strategy);
    if (Number.isFinite(Number(event.cycle_index))) parts.push(`Cycle ${event.cycle_index}`);
    return parts.join(' · ') || 'System activity';
  }

  function _esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function _stopPoll() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
  }

  function refresh() { load(); }

  return { init, refresh };
})();
