/* =================================================================
   RESULTS PAGE
   Exposes: window.ResultsPage
   ================================================================= */

window.ResultsPage = (() => {
  const SORT_PRESETS = [
    { id: 'newest', label: 'Newest', key: 'started_at', dir: -1 },
    { id: 'profit', label: 'Profit %', metricCandidates: ['profit_percent', 'total_profit_pct'], dir: -1 },
    { id: 'winrate', label: 'Win Rate', metricCandidates: ['win_rate'], dir: -1 },
    { id: 'drawdown', label: 'Drawdown', metricCandidates: ['max_drawdown'], dir: 1 },
  ];
  const METRIC_PRESETS = [
    { id: 'compact', label: 'Compact', count: 4 },
    { id: 'extended', label: 'Extended', count: 6 },
    { id: 'all', label: 'All', count: null },
  ];

  let _el = null;
  let _runs = [];
  let _sortKey = 'started_at';
  let _sortDir = -1;
  let _sortPreset = 'newest';
  let _metricPreset = 'extended';
  let _searchQuery = '';
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
    _metricPreset = _defaultMetricPreset();
    _render();
    _bindActivePage();
    load();
  }

  function _defaultMetricPreset() {
    if (window.innerWidth <= 860) return 'compact';
    if (window.innerWidth <= 1280) return 'extended';
    return 'extended';
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="results-page page-frame page-frame--compact">
        <div class="results-header">
          <div class="results-header__main">
            <h1 class="results-header__title">Backtest Results</h1>
            <p class="results-header__subtitle">Compare completed runs, inspect versioned strategies, and move directly into detailed analysis.</p>
          </div>
          <div class="results-header__meta">
            <div class="results-header__status" id="results-last-updated">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
              </svg>
              <span>Waiting for data...</span>
            </div>
          </div>
        </div>
        <div id="results-table-wrap" class="results-content">
          <div class="results-loading">
            <div class="results-loading__spinner"></div>
            <div class="results-loading__text">Loading results...</div>
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
        DOM.setHTML(wrap, '<div class="empty-state">Loading...</div>');
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
      _runs = (data.runs || []).filter((run) => run.status === 'completed');
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
    _metricDefs = Object.fromEntries(metrics.map((metric) => [metric.key, metric]));
    _resultsTableMetricKeys = Array.isArray(registry?.groups?.results_table)
      ? registry.groups.results_table
      : [];
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
        <span>Waiting for data...</span>
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

  function _flat(run) {
    return {
      ...run,
      _metrics: run.result_metrics || {},
    };
  }

  function _displayStrategy(run) {
    const base = run.display_strategy || run.strategy || '-';
    const version = run.display_version || run.version_id || run.strategy_version || null;
    return version ? `${base} | ${version}` : base;
  }

  function _strategySearchText(run) {
    return [
      run.run_id,
      _displayStrategy(run),
      run.display_strategy,
      run.strategy,
      run.strategy_class,
      run.base_strategy,
    ].filter(Boolean).join(' ').toLowerCase();
  }

  function _resolveMetricKey(candidates = []) {
    for (const key of candidates) {
      if (_metricDefs[key]) return key;
      if (_resultsTableMetricKeys.includes(key)) return key;
    }
    return null;
  }

  function _visibleMetricDefs() {
    const defs = _resultsTableMetricKeys
      .map((key) => _metricDefs[key])
      .filter(Boolean);
    const preset = METRIC_PRESETS.find((item) => item.id === _metricPreset) || METRIC_PRESETS[1];
    if (!preset.count) return defs;
    return defs.slice(0, preset.count);
  }

  function _filteredRuns(flatRuns) {
    const query = _searchQuery.trim().toLowerCase();
    if (!query) return flatRuns;
    return flatRuns.filter((run) => _strategySearchText(run).includes(query));
  }

  function _sortedRuns(flatRuns) {
    return [...flatRuns].sort((a, b) => {
      const va = _sortValue(a, _sortKey);
      const vb = _sortValue(b, _sortKey);
      if (va === null && vb === null) return 0;
      if (va === null) return _sortDir;
      if (vb === null) return -_sortDir;
      return typeof va === 'number'
        ? (va - vb) * _sortDir
        : String(va).localeCompare(String(vb)) * _sortDir;
    });
  }

  function _resolveSortPreset(id) {
    const preset = SORT_PRESETS.find((item) => item.id === id);
    if (!preset) return null;
    if (preset.key) return preset;
    const metricKey = _resolveMetricKey(preset.metricCandidates);
    if (!metricKey) return null;
    return { ...preset, key: `metric:${metricKey}` };
  }

  function _syncSortPresetFromState() {
    const match = SORT_PRESETS.find((preset) => {
      const resolved = _resolveSortPreset(preset.id);
      return resolved && resolved.key === _sortKey && resolved.dir === _sortDir;
    });
    _sortPreset = match ? match.id : 'custom';
  }

  function _applySortPreset(id) {
    const preset = _resolveSortPreset(id);
    if (!preset) return;
    _sortKey = preset.key;
    _sortDir = preset.dir;
    _sortPreset = preset.id;
    _renderTable();
  }

  function _sort(key) {
    if (_sortKey === key) _sortDir *= -1;
    else {
      _sortKey = key;
      _sortDir = -1;
    }
    _syncSortPresetFromState();
    _renderTable();
  }

  function _tableMetricExtremes(metricDefs, runs) {
    const extremes = {};
    metricDefs.forEach((metric) => {
      const values = runs
        .map((run) => FMT.toNumber ? FMT.toNumber(run._metrics?.[metric.key]) : Number(run._metrics?.[metric.key]))
        .filter((value) => value !== null && value !== undefined && Number.isFinite(value));
      if (!values.length) return;
      const higherIsBetter = _metricHigherIsBetter(metric);
      extremes[metric.key] = {
        best: higherIsBetter ? Math.max(...values) : Math.min(...values),
        worst: higherIsBetter ? Math.min(...values) : Math.max(...values),
      };
    });
    return extremes;
  }

  function _metricHigherIsBetter(metric) {
    if (typeof metric?.higher_is_better === 'boolean') return metric.higher_is_better;
    return metric?.key !== 'max_drawdown';
  }

  function _latestRunSummary(runId) {
    if (!runId) return 'No completed runs';
    const run = _runs.find((item) => item.run_id === runId);
    if (!run) return runId;
    return `${_displayStrategy(run)} | ${FMT.tsShort(run.started_at || run.completed_at || run.created_at)}`;
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
    const visibleMetricDefs = _visibleMetricDefs();
    const filtered = _filteredRuns(flat);
    const sorted = _sortedRuns(filtered);
    const latestRunId = _latestCompletedRunId();
    const metricExtremes = _tableMetricExtremes(visibleMetricDefs, filtered);
    const totalCount = flat.length;
    const shownCount = sorted.length;
    const latestSummary = _latestRunSummary(latestRunId);
    const th = (key, label, extraClass = '') => {
      const sortedLabel = _sortKey === key ? (_sortDir === 1 ? ' ^' : ' v') : '';
      return `<th class="sortable ${_sortKey === key ? 'sorted' : ''} ${extraClass}" data-sort="${key}">${label}${sortedLabel}</th>`;
    };

    DOM.setHTML(wrap, `
      <div class="results-table-card results-table-card--terminal">
        <div class="results-table-header">
          <div class="results-table-count">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 11l3 3L22 4"/>
              <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
            </svg>
            <span>${shownCount} of ${totalCount} ${totalCount === 1 ? 'result' : 'results'}</span>
          </div>
          <div class="results-table-header__latest">
            <span class="results-table-header__label">Latest run</span>
            <span class="results-table-header__value" data-results-latest-summary>${_esc(latestSummary)}</span>
          </div>
        </div>
        <div class="results-toolbar" data-results-toolbar>
          <label class="results-toolbar__search">
            <span class="results-toolbar__label">Search</span>
            <input class="form-input results-toolbar__input" type="search" value="${_esc(_searchQuery)}" placeholder="Run ID, strategy, or class" data-results-search>
          </label>
          <div class="results-toolbar__group">
            <span class="results-toolbar__label">Quick sort</span>
            <div class="results-toolbar__chips">
              ${SORT_PRESETS.map((preset) => {
                const resolved = _resolveSortPreset(preset.id);
                const disabled = resolved ? '' : 'disabled';
                const active = _sortPreset === preset.id ? ' is-active' : '';
                return `<button type="button" class="results-toolbar__chip${active}" data-results-sort-preset="${preset.id}" ${disabled}>${_esc(preset.label)}</button>`;
              }).join('')}
            </div>
          </div>
          <div class="results-toolbar__group">
            <span class="results-toolbar__label">Metrics</span>
            <div class="results-toolbar__chips">
              ${METRIC_PRESETS.map((preset) => {
                const active = _metricPreset === preset.id ? ' is-active' : '';
                return `<button type="button" class="results-toolbar__chip${active}" data-results-metric-preset="${preset.id}">${_esc(preset.label)}</button>`;
              }).join('')}
            </div>
          </div>
        </div>
        <div class="results-table-wrap">
          <table class="results-table results-table--terminal">
            <thead>
              <tr>
                ${th('run_id', 'Run ID', 'results-table__col--id')}
                ${th('strategy', 'Strategy', 'results-table__col--strategy')}
                ${th('started_at', 'Date', 'results-table__col--date')}
                ${visibleMetricDefs.map((metric) => th(`metric:${metric.key}`, metric.label, 'results-table__col--metric')).join('')}
                <th class="results-table__actions results-table__col--actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${sorted.length ? sorted.map((run) => _renderRow(run, visibleMetricDefs, metricExtremes, latestRunId)).join('') : `
                <tr>
                  <td class="results-table__empty" colspan="${4 + visibleMetricDefs.length}">
                    No runs match the current search.
                  </td>
                </tr>
              `}
            </tbody>
          </table>
        </div>
      </div>
    `);

    wrap.querySelectorAll('[data-results-search]').forEach((input) => {
      DOM.on(input, 'input', () => {
        _searchQuery = input.value || '';
        _renderTable();
      });
    });
    wrap.querySelectorAll('[data-results-sort-preset]').forEach((button) => {
      DOM.on(button, 'click', () => _applySortPreset(button.dataset.resultsSortPreset || ''));
    });
    wrap.querySelectorAll('[data-results-metric-preset]').forEach((button) => {
      DOM.on(button, 'click', () => {
        _metricPreset = button.dataset.resultsMetricPreset || 'extended';
        _renderTable();
      });
    });
    wrap.querySelectorAll('[data-sort]').forEach((header) => {
      DOM.on(header, 'click', () => _sort(header.dataset.sort));
    });
    wrap.querySelectorAll('[data-detail-btn]').forEach((button) => {
      DOM.on(button, 'click', (event) => {
        event.stopPropagation();
        _showDetail(button.dataset.runId);
      });
    });
    wrap.querySelectorAll('[data-apply-btn]').forEach((button) => {
      DOM.on(button, 'click', async (event) => {
        event.stopPropagation();
        await _applyConfig(button.dataset.runId);
      });
    });
    wrap.querySelectorAll('tr[data-run-id]').forEach((row) => {
      DOM.on(row, 'click', () => _showDetail(row.dataset.runId));
    });
  }

  function _renderRow(run, visibleMetricDefs, metricExtremes, latestRunId) {
    const latest = run.run_id === latestRunId;
    const strategyClass = run.strategy_class || run.base_strategy || run.strategy || '-';
    const dateValue = FMT.tsShort(run.started_at || run.completed_at || run.created_at);
    const latestNote = latest ? 'Latest completed run' : 'Completed run';
    return `
      <tr class="results-table__row${latest ? ' results-table__row--latest' : ''}" data-run-id="${run.run_id || ''}" data-row-latest="${latest ? 'true' : 'false'}">
        <td class="results-table__id">
          <div class="results-table__identity">
            <span class="results-table__id-text">${FMT.truncate(run.run_id || '-', 16)}</span>
            ${latest ? '<span class="results-table__badge results-table__badge--latest">Latest</span>' : ''}
          </div>
        </td>
        <td class="results-table__strategy">
          <div class="results-table__strategy-name">${_esc(_displayStrategy(run))}</div>
          <div class="results-table__strategy-class">${_esc(strategyClass)}</div>
        </td>
        <td class="results-table__date">
          <div class="results-table__date-main">${_esc(dateValue)}</div>
          <div class="results-table__date-sub">${_esc(latestNote)}</div>
        </td>
        ${visibleMetricDefs.map((metric) => _renderMetricCell(metric, run._metrics?.[metric.key], metricExtremes[metric.key])).join('')}
        <td class="results-table__actions">
          <div class="results-table__action-group">
            <button class="results-table__btn results-table__btn--view" data-detail-btn data-run-id="${run.run_id || ''}" title="View Details">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
              View
            </button>
            <button class="results-table__btn results-table__btn--apply" data-apply-btn data-run-id="${run.run_id || ''}" title="Apply Configuration">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              Apply
            </button>
          </div>
        </td>
      </tr>`;
  }

  function _sortValue(row, key) {
    if (!key) return null;
    if (key.startsWith('metric:')) {
      return row._metrics?.[key.slice(7)] ?? null;
    }
    if (key === 'strategy') return _displayStrategy(row);
    return row[key] ?? null;
  }

  function _renderMetricCell(metric, value, extremes) {
    const tone = _metricTone(metric, value);
    const rendered = _formatMetric(metric, value);
    const numeric = FMT.toNumber ? FMT.toNumber(value) : Number(value);
    const hasNumeric = numeric !== null && numeric !== undefined && Number.isFinite(numeric);
    const isBest = hasNumeric && extremes && numeric === extremes.best;
    const isWorst = hasNumeric && extremes && numeric === extremes.worst && extremes.best !== extremes.worst;
    const stateClass = isBest ? ' results-table__metric-cell--best' : (isWorst ? ' results-table__metric-cell--worst' : '');
    const toneClass = tone ? ` results-table__metric--${tone}` : '';
    const flag = isBest ? '<span class="results-table__metric-flag">Best</span>' : (isWorst ? '<span class="results-table__metric-flag">Lag</span>' : '');
    return `
      <td class="results-table__metric${toneClass}${stateClass}">
        <div class="results-table__metric-value">${rendered}</div>
        ${flag}
      </td>`;
  }

  function _formatMetric(metric, value) {
    if (value === null || value === undefined || value === '') return '-';
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
      case 'total_profit_pct':
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

  function refresh() {
    load({ silent: true });
  }

  return { init, refresh };
})();
