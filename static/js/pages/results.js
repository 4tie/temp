/* =================================================================
   RESULTS PAGE
   Exposes: window.ResultsPage
   ================================================================= */

window.ResultsPage = (() => {
  let _runs = [];
  let _filteredRuns = [];
  let _currentPage = 1;
  const _itemsPerPage = 20;
  let _sortColumn = 'started_at';
  let _sortDirection = 'desc';
  let _searchQuery = '';
  let _activeFilter = 'all';
  let _loading = false;
  let _pollTimer = null;

  // ── field helpers ────────────────────────────────────────────────

  function _runId(run)       { return run.run_id || run.id || ''; }
  function _strategy(run)    { return run.display_strategy || run.strategy || run.strategy_class || '—'; }
  function _version(run)     { return run.display_version || run.version_id || run.strategy_version || ''; }
  function _status(run)      { return run.status || 'unknown'; }
  function _date(run)        { return run.started_at || run.completed_at || run.created_at || ''; }
  function _profit(run)      { return parseFloat(run.profit_percent ?? run.total_profit_pct ?? run.result_metrics?.profit_percent ?? 0) || 0; }
  function _trades(run)      { return parseInt(run.total_trades ?? run.result_metrics?.total_trades ?? 0, 10) || 0; }
  function _winRate(run)     { return parseFloat(run.win_rate ?? run.result_metrics?.win_rate ?? 0) || 0; }
  function _drawdown(run)    { return parseFloat(run.max_drawdown ?? run.result_metrics?.max_drawdown ?? 0) || 0; }
  function _sharpe(run)      { return parseFloat(run.sharpe_ratio ?? run.result_metrics?.sharpe_ratio ?? 0) || 0; }

  // ── init ─────────────────────────────────────────────────────────

  function init() {
    if (!document.querySelector('[data-view="results"]')) return;
    loadData();
    _bindPageVisibility();
  }

  function _bindPageVisibility() {
    if (window.AppState) {
      AppState.subscribe('activePage', page => {
        if (page === 'results') { loadData({ silent: true }); _startPolling(); }
        else _stopPolling();
      });
      if (AppState.get('activePage') === 'results') _startPolling();
    }
  }

  function _startPolling() {
    if (_pollTimer) return;
    _pollTimer = setInterval(() => loadData({ silent: true }), 8000);
  }

  function _stopPolling() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
  }

  // ── data loading ─────────────────────────────────────────────────

  function loadData({ silent = false } = {}) {
    if (_loading) return;
    _loading = true;
    if (!silent) showLoading();

    const apiCall = (window.API && API.getRuns)
      ? API.getRuns()
      : fetch('/api/runs').then(r => r.json());

    apiCall
      .then(data => {
        _runs = (data.runs || []);
        _loading = false;
        if (!silent) hideLoading();
        applyFilters();
        renderTable();
        updateStats();
        updatePagination();
      })
      .catch(err => {
        _loading = false;
        if (!silent) hideLoading();
        console.error('ResultsPage: failed to load runs:', err);
        if (!silent) showEmptyState();
      });
  }

  // ── filtering / sorting ──────────────────────────────────────────

  function applyFilters() {
    let filtered = [..._runs];

    if (_searchQuery) {
      const q = _searchQuery.toLowerCase();
      filtered = filtered.filter(run =>
        _strategy(run).toLowerCase().includes(q) ||
        _runId(run).toLowerCase().includes(q) ||
        (_version(run) || '').toLowerCase().includes(q)
      );
    }

    switch (_activeFilter) {
      case 'profitable':
        filtered = filtered.filter(run => _profit(run) > 0);
        break;
      case 'completed':
        filtered = filtered.filter(run => _status(run) === 'completed');
        break;
      case 'recent': {
        const cutoff = Date.now() - 7 * 86400000;
        filtered = filtered.filter(run => Date.parse(_date(run)) >= cutoff);
        break;
      }
    }

    filtered.sort((a, b) => {
      let av, bv;
      switch (_sortColumn) {
        case 'strategy':   av = _strategy(a); bv = _strategy(b); break;
        case 'profit':     av = _profit(a);   bv = _profit(b);   break;
        case 'trades':     av = _trades(a);   bv = _trades(b);   break;
        case 'winrate':    av = _winRate(a);  bv = _winRate(b);  break;
        case 'drawdown':   av = _drawdown(a); bv = _drawdown(b); break;
        case 'sharpe':     av = _sharpe(a);   bv = _sharpe(b);   break;
        default:           av = Date.parse(_date(a)) || 0; bv = Date.parse(_date(b)) || 0;
      }
      if (av === bv) return 0;
      return (av > bv ? 1 : -1) * (_sortDirection === 'asc' ? 1 : -1);
    });

    _filteredRuns = filtered;
  }

  // ── rendering ────────────────────────────────────────────────────

  function renderTable() {
    const tableBody = document.getElementById('results-table-body');
    if (!tableBody) return;

    if (_filteredRuns.length === 0) { showEmptyState(); return; }
    hideEmptyState();

    const start = (_currentPage - 1) * _itemsPerPage;
    const pageRuns = _filteredRuns.slice(start, start + _itemsPerPage);

    tableBody.innerHTML = pageRuns.map(run => {
      const id      = _runId(run);
      const strat   = _strategy(run);
      const ver     = _version(run);
      const status  = _status(run);
      const profit  = _profit(run);
      const trades  = _trades(run);
      const wr      = _winRate(run);
      const dd      = _drawdown(run);
      const sharpe  = _sharpe(run);
      const dateStr = _formatDate(_date(run));
      const profCls = profit > 0 ? 'positive' : profit < 0 ? 'negative' : 'neutral';

      return `
        <tr class="results-table-row" data-run-id="${_esc(id)}">
          <td class="results-cell-strategy">
            ${_esc(strat)}${ver ? `<span class="results-cell-version"> · ${_esc(ver)}</span>` : ''}
          </td>
          <td class="results-cell-date">${_esc(dateStr)}</td>
          <td class="results-cell-profit ${profCls}">${_fmtPct(profit)}</td>
          <td class="font-mono">${trades}</td>
          <td class="${wr >= 50 ? 'positive' : 'negative'}">${_fmtPct(wr, false)}</td>
          <td class="negative font-mono">${dd !== 0 ? _fmtPct(dd, false) : '—'}</td>
          <td class="font-mono">${sharpe ? sharpe.toFixed(2) : '—'}</td>
          <td><span class="results-cell-status ${_esc(status)}">${_esc(_cap(status))}</span></td>
          <td class="results-cell-actions">
            <button class="results-action-btn primary" data-open-run="${_esc(id)}">Explore</button>
          </td>
        </tr>`;
    }).join('');

    tableBody.querySelectorAll('[data-open-run]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        _openRun(btn.dataset.openRun);
      });
    });

    tableBody.querySelectorAll('.results-table-row').forEach(row => {
      row.addEventListener('click', () => _openRun(row.dataset.runId));
    });
  }

  function _openRun(runId) {
    if (!runId) return;
    if (window.ResultExplorer && ResultExplorer.open) {
      ResultExplorer.open(runId);
    }
  }

  function updateStats() {
    if (!_runs.length) return;
    const completed   = _runs.filter(r => _status(r) === 'completed');
    const profitable  = completed.filter(r => _profit(r) > 0);
    const avgProfit   = completed.length
      ? completed.reduce((s, r) => s + _profit(r), 0) / completed.length
      : 0;
    const best = completed.reduce((b, r) => _profit(r) > _profit(b || r) ? r : (b || r), null);

    _setText('total-runs',    _runs.length);
    _setText('avg-return',    _fmtPct(avgProfit));
    _setText('best-strategy', best ? _strategy(best) : '—');
    _setText('success-rate',  completed.length ? _fmtPct(profitable.length / completed.length * 100, false) : '—');
    _setText('runs-change',   `${completed.length} completed`);
    _setText('return-change', avgProfit >= 0 ? 'avg across runs' : 'avg across runs');
    _setText('best-return',   best ? `${_fmtPct(_profit(best))} return` : '—');
    _setText('success-change',`${profitable.length} profitable`);

    _setClass('return-change', avgProfit);
    _setClass('success-change', profitable.length);
  }

  function updatePagination() {
    const total     = _filteredRuns.length;
    const totalPages = Math.max(1, Math.ceil(total / _itemsPerPage));
    const startItem  = total ? (_currentPage - 1) * _itemsPerPage + 1 : 0;
    const endItem    = Math.min(_currentPage * _itemsPerPage, total);

    _setText('pagination-start', startItem);
    _setText('pagination-end',   endItem);
    _setText('pagination-total', total);

    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    if (prevBtn) prevBtn.disabled = _currentPage <= 1;
    if (nextBtn) nextBtn.disabled = _currentPage >= totalPages;

    const nums = document.getElementById('pagination-numbers');
    if (nums) nums.innerHTML = _pageNumbers(totalPages);
  }

  function _pageNumbers(totalPages) {
    const max = 5;
    let s = Math.max(1, _currentPage - Math.floor(max / 2));
    let e = Math.min(totalPages, s + max - 1);
    if (e - s + 1 < max) s = Math.max(1, e - max + 1);
    let html = '';
    for (let i = s; i <= e; i++) {
      html += `<button class="results-pagination-btn${i === _currentPage ? ' active' : ''}"
        onclick="window.ResultsPage.changePage(${i})">${i}</button>`;
    }
    return html;
  }

  // ── event binding ────────────────────────────────────────────────

  function bindEvents() {
    const search = document.getElementById('results-search');
    if (search) search.addEventListener('input', _debounce(e => {
      _searchQuery = e.target.value.toLowerCase();
      _currentPage = 1;
      applyFilters(); renderTable(); updatePagination();
    }, 250));

    document.querySelectorAll('.results-filter-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.results-filter-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        _activeFilter = chip.dataset.filter || 'all';
        _currentPage = 1;
        applyFilters(); renderTable(); updatePagination();
      });
    });

    document.querySelectorAll('[data-sort]').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.dataset.sort;
        if (_sortColumn === col) _sortDirection = _sortDirection === 'asc' ? 'desc' : 'asc';
        else { _sortColumn = col; _sortDirection = 'desc'; }
        applyFilters(); renderTable();
      });
    });

    document.getElementById('prev-page')?.addEventListener('click', () => changePage(_currentPage - 1));
    document.getElementById('next-page')?.addEventListener('click', () => changePage(_currentPage + 1));
  }

  function changePage(page) {
    const totalPages = Math.max(1, Math.ceil(_filteredRuns.length / _itemsPerPage));
    if (page < 1 || page > totalPages) return;
    _currentPage = page;
    renderTable();
    updatePagination();
  }

  // ── visibility helpers ───────────────────────────────────────────

  function showLoading() {
    document.getElementById('results-loading')?.style.setProperty('display', 'flex');
    const c = document.querySelector('.results-table-container');
    if (c) c.style.display = 'none';
  }

  function hideLoading() {
    document.getElementById('results-loading')?.style.setProperty('display', 'none');
    const c = document.querySelector('.results-table-container');
    if (c) c.style.display = 'block';
  }

  function showEmptyState() {
    document.getElementById('results-empty')?.style.setProperty('display', 'block');
    const c = document.querySelector('.results-table-container');
    if (c) c.style.display = 'none';
  }

  function hideEmptyState() {
    document.getElementById('results-empty')?.style.setProperty('display', 'none');
    const c = document.querySelector('.results-table-container');
    if (c) c.style.display = 'block';
  }

  // ── utilities ────────────────────────────────────────────────────

  function _formatDate(str) {
    if (!str) return '—';
    const d = new Date(str);
    if (isNaN(d)) return str;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function _fmtPct(v, sign = true) {
    const n = parseFloat(v);
    if (!isFinite(n)) return '—';
    return `${sign && n > 0 ? '+' : ''}${n.toFixed(1)}%`;
  }

  function _cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

  function _esc(v) {
    const d = document.createElement('div');
    d.textContent = String(v ?? '');
    return d.innerHTML;
  }

  function _setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function _setClass(id, val) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('positive', 'negative');
    el.classList.add(val > 0 ? 'positive' : val < 0 ? 'negative' : '');
  }

  function _debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  return { init, bindEvents, changePage, refresh: () => loadData({ silent: true }) };
})();

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => { window.ResultsPage.init(); window.ResultsPage.bindEvents(); });
} else {
  window.ResultsPage.init();
  window.ResultsPage.bindEvents();
}
