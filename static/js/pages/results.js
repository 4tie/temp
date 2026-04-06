/* =================================================================
   RESULTS PAGE
   Exposes: window.ResultsPage
   ================================================================= */

window.ResultsPage = (() => {
  let _el = null;
  let _runs = [];
  let _sortKey = 'started_at';
  let _sortDir = -1;
  let _pollTimer = null;
  let _loading = false;
  let _lastLoadedAt = null;
  let _latestRunIdSeen = null;
  let _autoOpenedRunId = null;
  let _metricDefs = {};
  let _resultsTableMetricKeys = [];

  function init() {
    _el = DOM.$('[data-view="results"]');
    if (!_el) return;
    _render();
    _bindActivePage();
    load();
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="results-page">
        <div class="results-header">
          <div class="results-header__main">
            <h1 class="results-header__title">Backtest Results</h1>
            <p class="results-header__subtitle">Compare and analyze completed backtest runs</p>
          </div>
          <div class="results-header__meta">
            <div class="results-header__status" id="results-last-updated">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
              </svg>
              <span>Waiting for data…</span>
            </div>
          </div>
        </div>
        <div id="results-table-wrap" class="results-content">
          <div class="results-loading">
            <div class="results-loading__spinner"></div>
            <div class="results-loading__text">Loading results…</div>
          </div>
        </div>
      </div>
    `);
  }

  function _bindActivePage() {
    AppState.subscribe('activePage', (page) => {
      if (page === 'results') {
        load({ silent: true });
        _startPolling();
      } else {
        _stopPolling();
      }
    });
    if (AppState.get('activePage') === 'results') {
      _startPolling();
    }
  }

  async function load({ silent = false } = {}) {
    if (_loading) return;
    _loading = true;
    try {
      const wrap = DOM.$('#results-table-wrap', _el);
      if (!silent && wrap && !_runs.length) {
        DOM.setHTML(wrap, '<div class="empty-state">Loading…</div>');
      }
      let data;
      if (!_resultsTableMetricKeys.length) {
        const [runsData, registry] = await Promise.all([
          API.getRuns(),
          API.getResultMetrics(),
        ]);
        data = runsData;
        _applyMetricRegistry(registry);
      } else {
        data = await API.getRuns();
      }
      _runs = (data.runs || []).filter(r => r.status === 'completed');
      _lastLoadedAt = new Date();
      _renderMeta();
      _renderTable();
      _autoShowLatestRun();
    } catch (err) {
      if (!silent) {
        Toast.error('Failed to load results: ' + err.message);
      }
    } finally {
      _loading = false;
    }
  }

  function _applyMetricRegistry(registry) {
    const metrics = registry?.metrics || [];
    _metricDefs = Object.fromEntries(metrics.map(metric => [metric.key, metric]));
    _resultsTableMetricKeys = registry?.groups?.results_table || [];
  }

  function _renderMeta() {
    const el = DOM.$('#results-last-updated', _el);
    if (!el) return;
    if (!_lastLoadedAt) {
      DOM.setHTML(el, `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12 6 12 12 16 14"/>
        </svg>
        <span>Waiting for data…</span>
      `);
      return;
    }
    const timeStr = _lastLoadedAt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    DOM.setHTML(el, `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
      </svg>
      <span>Updated ${timeStr}</span>
    `);
  }

  function _flat(r) {
    return {
      ...r,
      _metrics: r.result_metrics || {},
    };
  }

  function _displayStrategy(run) {
    const base = run.display_strategy || run.strategy || '—';
    const version = run.display_version || run.strategy_version || null;
    return version ? `${base} · ${version}` : base;
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
      DOM.setHTML(wrap, `
        <div class="results-empty">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M9 11l3 3L22 4"/>
            <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
          </svg>
          <h3>No Results Yet</h3>
          <p>Complete a backtest to see results here</p>
          <button class="btn btn--primary" onclick="window.App?.navigate?.('backtesting')">Run Backtest</button>
        </div>
      `);
      return;
    }

    const flat = _runs.map(_flat);
    const metricDefs = _resultsTableMetricKeys
      .map(key => _metricDefs[key])
      .filter(Boolean);
    const sorted = [...flat].sort((a, b) => {
      const va = _sortValue(a, _sortKey);
      const vb = _sortValue(b, _sortKey);
      if (va === null && vb === null) return 0;
      if (va === null) return _sortDir;
      if (vb === null) return -_sortDir;
      return typeof va === 'number'
        ? (va - vb) * _sortDir
        : String(va).localeCompare(String(vb)) * _sortDir;
    });

    const th = (key, label) => `<th class="sortable ${_sortKey === key ? 'sorted' : ''}" data-sort="${key}">${label}${_sortKey === key ? (_sortDir === 1 ? ' ▲' : ' ▼') : ''}</th>`;

    DOM.setHTML(wrap, `
      <div class="results-table-card">
        <div class="results-table-header">
          <div class="results-table-count">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 11l3 3L22 4"/>
              <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
            </svg>
            <span>${sorted.length} ${sorted.length === 1 ? 'Result' : 'Results'}</span>
          </div>
        </div>
        <div class="results-table-wrap">
          <table class="results-table">
            <thead><tr>
              ${th('run_id', 'Run ID')}
              ${th('strategy', 'Strategy')}
              ${th('started_at', 'Date')}
              ${metricDefs.map(metric => th(`metric:${metric.key}`, metric.label)).join('')}
              <th class="results-table__actions">Actions</th>
            </tr></thead>
            <tbody>
              ${sorted.map(r => {
                const profitMetric = r._metrics?.profit_percent ?? r._metrics?.total_profit_pct;
                const profitTone = _metricTone({ key: 'profit_percent' }, profitMetric);
                return `
                  <tr class="results-table__row" data-run-id="${r.run_id || ''}">
                    <td class="results-table__id">
                      <span class="results-table__id-text">${FMT.truncate(r.run_id || '—', 12)}</span>
                    </td>
                    <td class="results-table__strategy">
                      <div class="results-table__strategy-name">${_esc(_displayStrategy(r))}</div>
                      <div class="results-table__strategy-class">${_esc(r.strategy_class || r.base_strategy || r.strategy || '—')}</div>
                    </td>
                    <td class="results-table__date">${FMT.tsShort(r.started_at)}</td>
                    ${metricDefs.map(metric => _renderMetricCell(metric, r._metrics?.[metric.key])).join('')}
                    <td class="results-table__actions">
                      <button class="results-table__btn results-table__btn--view" data-detail-btn data-run-id="${r.run_id || ''}" title="View Details">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                        View
                      </button>
                      <button class="results-table__btn results-table__btn--apply" data-apply-btn data-run-id="${r.run_id || ''}" title="Apply Configuration">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <polyline points="20 6 9 17 4 12"/>
                        </svg>
                        Apply
                      </button>
                    </td>
                  </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `);

    wrap.querySelectorAll('[data-sort]').forEach(th => {
      DOM.on(th, 'click', () => _sort(th.dataset.sort));
    });
    wrap.querySelectorAll('[data-detail-btn]').forEach(btn => {
      DOM.on(btn, 'click', e => {
        e.stopPropagation();
        _showDetail(btn.dataset.runId);
      });
    });
    wrap.querySelectorAll('[data-apply-btn]').forEach(btn => {
      DOM.on(btn, 'click', async (e) => {
        e.stopPropagation();
        await _applyConfig(btn.dataset.runId);
      });
    });
    wrap.querySelectorAll('tr[data-run-id]').forEach(row => {
      DOM.on(row, 'click', () => _showDetail(row.dataset.runId));
    });
  }

  function _sortValue(row, key) {
    if (!key) return null;
    if (key.startsWith('metric:')) {
      return row._metrics?.[key.slice(7)] ?? null;
    }
    return row[key] ?? null;
  }

  function _renderMetricCell(metric, value) {
    const tone = _metricTone(metric, value);
    const rendered = _formatMetric(metric, value);
    const toneClass = tone ? ` results-table__metric--${tone}` : '';
    return `<td class="results-table__metric${toneClass}">${rendered}</td>`;
  }

  function _formatMetric(metric, value) {
    if (value === null || value === undefined || value === '') return '—';
    const decimals = metric?.decimals ?? 2;
    switch (metric?.format) {
      case 'percent':
        return FMT.pct(value, decimals, !!metric.show_sign);
      case 'integer':
        return FMT.integer(value);
      case 'currency':
        return FMT.currency(value, decimals);
      case 'ratio':
      case 'number':
        return FMT.number(value, decimals);
      default:
        return String(value);
    }
  }

  function _metricTone(metric, value) {
    if (value === null || value === undefined || value === '') return '';
    switch (metric?.key) {
      case 'profit_percent':
      case 'profit_total_abs':
        return FMT.toneProfit(value);
      case 'win_rate':
        return FMT.toneWinRate(value);
      case 'max_drawdown':
        return FMT.toneDrawdown(value);
      case 'profit_factor':
      case 'sharpe_ratio':
        return FMT.toneRatio(value, 1);
      default:
        return '';
    }
  }

  async function _showDetail(runId) {
    if (!runId) return;
    try {
      ResultExplorer.open(runId);
    } catch (err) {
      Toast.error('Could not load run detail: ' + err.message);
    }
  }

  function _runTimestamp(run) {
    const candidates = [run?.completed_at, run?.started_at, run?.created_at];
    for (const value of candidates) {
      const ts = Date.parse(value || '');
      if (Number.isFinite(ts)) return ts;
    }
    return 0;
  }

  function _latestCompletedRunId() {
    if (!_runs.length) return null;
    const latest = [..._runs].sort((a, b) => {
      const delta = _runTimestamp(b) - _runTimestamp(a);
      if (delta !== 0) return delta;
      return String(b.run_id || '').localeCompare(String(a.run_id || ''));
    })[0];
    return latest?.run_id || null;
  }

  function _autoShowLatestRun() {
    const latestRunId = _latestCompletedRunId();
    if (!latestRunId) return;

    const hasNewLatest = latestRunId !== _latestRunIdSeen;
    _latestRunIdSeen = latestRunId;

    if (AppState.get('activePage') !== 'results') return;
    if (!hasNewLatest && _autoOpenedRunId) return;

    _autoOpenedRunId = latestRunId;
    _showDetail(latestRunId);
  }

  async function _applyConfig(runId) {
    if (!runId) return;
    try {
      const res = await API.applyRunConfig(runId);
      if (res.warnings?.length) {
        Toast.warning(`Config applied with warnings: ${res.warnings.join(' | ')}`);
      } else {
        Toast.success('Run config applied.');
      }
    } catch (err) {
      Toast.error('Failed to apply run config: ' + err.message);
    }
  }

  function _esc(str) {
    const d = document.createElement('div');
    d.textContent = String(str || '');
    return d.innerHTML;
  }

  function _startPolling() {
    if (_pollTimer) return;
    _pollTimer = setInterval(() => {
      if (AppState.get('activePage') !== 'results') return;
      load({ silent: true });
    }, 5000);
  }

  function _stopPolling() {
    if (_pollTimer) {
      clearInterval(_pollTimer);
      _pollTimer = null;
    }
  }

  function refresh() { load({ silent: true }); }

  return { init, refresh };
})();
