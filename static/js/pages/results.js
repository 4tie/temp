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
      <div class="page-header">
        <h1 class="page-header__title">Results</h1>
        <p class="page-header__subtitle">Completed backtest runs with key performance metrics.</p>
        <div class="page-header__meta text-muted text-sm" id="results-last-updated">Waiting for data…</div>
      </div>
      <div id="results-table-wrap"><div class="empty-state">Loading…</div></div>
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
      DOM.setText(el, 'Waiting for data…');
      return;
    }
    DOM.setText(el, `Auto-refreshing · last updated ${_lastLoadedAt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`);
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
      DOM.setHTML(wrap, '<div class="empty-state">No completed backtest runs yet.</div>');
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
      <table class="data-table data-table--hoverable">
        <thead><tr>
          ${th('run_id',        'Run ID')}
          ${th('strategy',     'Strategy / Version')}
          ${th('started_at',   'Date')}
          ${metricDefs.map(metric => th(`metric:${metric.key}`, metric.label)).join('')}
          <th></th>
        </tr></thead>
        <tbody>
          ${sorted.map(r => {
            return `
              <tr class="cursor-pointer" data-run-id="${r.run_id || ''}">
                <td class="font-mono text-sm">${FMT.truncate(r.run_id || '—', 18)}</td>
                <td>
                  <div>${_esc(_displayStrategy(r))}</div>
                  <div class="text-muted text-xs">${_esc(r.strategy_class || r.base_strategy || r.strategy || '—')}</div>
                </td>
                <td class="text-muted text-sm">${FMT.tsShort(r.started_at)}</td>
                ${metricDefs.map(metric => _renderMetricCell(metric, r._metrics?.[metric.key])).join('')}
                <td>
                  <button class="btn btn--ghost btn--sm" data-detail-btn data-run-id="${r.run_id || ''}">View</button>
                  <button class="btn btn--secondary btn--sm" data-apply-btn data-run-id="${r.run_id || ''}">Apply Config</button>
                </td>
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
    const cls = tone ? ` class="text-${tone} font-medium"` : '';
    return `<td${cls}>${rendered}</td>`;
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
