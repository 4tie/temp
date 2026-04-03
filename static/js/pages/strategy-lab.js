/* =================================================================
   STRATEGY LAB PAGE
   Exposes: window.StrategyLabPage
   ================================================================= */

window.StrategyLabPage = (() => {
  let _el = null;
  let _strategies = [];
  let _selected = null;

  function init() {
    _el = DOM.$('[data-view="strategy-lab"]');
    if (!_el) return;
    _render();
    load();
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="page-header">
        <h1 class="page-header__title">Strategy Lab</h1>
        <p class="page-header__subtitle">Browse, inspect, and analyze your FreqTrade strategy files.</p>
      </div>
      <div class="split-layout split-layout--lab">
        <div class="split-layout__sidebar">
          <div class="card card--fill">
            <div class="card__header">
              <span class="card__title">Strategies</span>
              <span class="badge badge--muted" id="sl-count">0</span>
            </div>
            <div class="card__body card__body--flush">
              <div class="search-wrap">
                <input class="form-input form-input--sm" id="sl-search" type="search" placeholder="Search strategies…">
              </div>
              <ul class="strategy-list" id="sl-list">
                <li class="empty-state">Loading…</li>
              </ul>
            </div>
          </div>
        </div>
        <div class="split-layout__main">
          <div class="card card--fill" id="sl-detail">
            <div class="card__body">
              <div class="empty-state">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color:var(--text-disabled);margin-bottom:var(--space-3)">
                  <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18"/>
                </svg>
                <p>Select a strategy to inspect its parameters</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    `);

    DOM.on(DOM.$('#sl-search', _el), 'input', e => _filterList(e.target.value));
  }

  async function load() {
    try {
      const data = await API.getStrategies();
      _strategies = data.strategies || [];
      DOM.setText(DOM.$('#sl-count', _el), String(_strategies.length));
      _renderList(_strategies);
    } catch (err) {
      Toast.error('Failed to load strategies: ' + err.message);
    }
  }

  function _renderList(list) {
    const ul = DOM.$('#sl-list', _el);
    if (!ul) return;
    if (!list.length) {
      ul.innerHTML = '<li class="empty-state">No strategies found.</li>';
      return;
    }
    ul.innerHTML = list.map(s => {
      const name = s.name || s;
      return `<li class="strategy-item ${_selected === name ? 'active' : ''}" data-strategy="${_esc(name)}">${_esc(name)}</li>`;
    }).join('');

    ul.querySelectorAll('[data-strategy]').forEach(item => {
      DOM.on(item, 'click', () => _selectStrategy(item.dataset.strategy, item));
    });
  }

  function _filterList(query) {
    const q = (query || '').toLowerCase();
    const filtered = q
      ? _strategies.filter(s => (s.name || s).toLowerCase().includes(q))
      : _strategies;
    _renderList(filtered);
  }

  async function _selectStrategy(name, listItem) {
    _selected = name;
    DOM.$$('.strategy-item', _el).forEach(i => i.classList.remove('active'));
    if (listItem) listItem.classList.add('active');

    const detail = DOM.$('#sl-detail', _el);
    detail.innerHTML = `<div class="card__body"><div class="empty-state">Loading parameters…</div></div>`;

    try {
      const data   = await API.getStrategyParams(name);
      const params = data.parameters || [];
      _renderDetail(detail, name, params);
    } catch (err) {
      detail.innerHTML = `<div class="card__body"><div class="empty-state text-red">Failed: ${_esc(err.message)}</div></div>`;
    }
  }

  function _renderDetail(el, name, params) {
    el.innerHTML = `
      <div class="card__header">
        <span class="card__title">${_esc(name)}</span>
        <span class="badge badge--violet">${params.length} parameters</span>
      </div>
      <div class="card__body">
        ${params.length ? `
          <table class="data-table">
            <thead><tr><th>Parameter</th><th>Type</th><th>Default</th><th>Description</th></tr></thead>
            <tbody>
              ${params.map(p => `
                <tr>
                  <td class="font-mono text-sm">${_esc(p.name || '—')}</td>
                  <td><span class="badge badge--muted">${_esc(p.type || '—')}</span></td>
                  <td class="font-mono text-sm text-amber">${_esc(String(p.default ?? '—'))}</td>
                  <td class="text-secondary text-sm">${_esc(p.description || '—')}</td>
                </tr>`).join('')}
            </tbody>
          </table>` : '<div class="empty-state">No configurable parameters found.</div>'}
      </div>`;
  }

  function _esc(str) {
    const d = document.createElement('div');
    d.textContent = String(str || '');
    return d.innerHTML;
  }

  function refresh() { load(); }

  return { init, refresh };
})();
