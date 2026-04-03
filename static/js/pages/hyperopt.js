/* =================================================================
   HYPEROPT PAGE
   Exposes: window.HyperoptPage
   ================================================================= */

window.HyperoptPage = (() => {
  let _el = null;
  let _pollTimer = null;
  let _currentRunId = null;

  /* ── Favourites ── */
  const _FAV_KEY  = '4tie_fav_pairs';
  const _FORM_KEY = '4tie_ho_form';
  function _getFavs() { try { return new Set(JSON.parse(localStorage.getItem(_FAV_KEY) || '[]')); } catch { return new Set(); } }
  function _saveFavs(s) { localStorage.setItem(_FAV_KEY, JSON.stringify([...s])); }

  /* ── Form persistence ── */
  function _saveForm() {
    const get = id => { const el = DOM.$(`#${id}`, _el); return el ? el.value : undefined; };
    const spacesEls = _el ? [..._el.querySelectorAll('#ho-spaces input[type="checkbox"]')] : [];
    const saved = {
      strategy:     get('ho-strategy'),
      exchange:     get('ho-exchange'),
      loss:         get('ho-loss'),
      spaces:       spacesEls.filter(c => c.checked).map(c => c.value),
      epochs:       get('ho-epochs'),
      jobs:         get('ho-jobs'),
      timeframe:    get('ho-timeframe'),
      timerange:    get('ho-timerange'),
      wallet:       get('ho-wallet'),
      min_trades:   get('ho-min-trades'),
      dl_exchange:  get('ho-dl-exchange'),
      dl_timeframe: get('ho-dl-timeframe'),
      dl_days:      get('ho-dl-days'),
      pairs:        _getSelectedPairs('ho-pairs-list'),
    };
    try { localStorage.setItem(_FORM_KEY, JSON.stringify(saved)); } catch {}
  }

  function _loadSavedForm() {
    try { return JSON.parse(localStorage.getItem(_FORM_KEY) || 'null'); } catch { return null; }
  }

  function _applySavedForm(saved) {
    if (!saved) return;
    const set = (id, v) => { const el = DOM.$(`#${id}`, _el); if (el && v != null && v !== '') el.value = v; };
    set('ho-strategy',   saved.strategy);
    set('ho-exchange',   saved.exchange);
    set('ho-loss',       saved.loss);
    set('ho-epochs',     saved.epochs);
    set('ho-jobs',       saved.jobs);
    set('ho-timeframe',  saved.timeframe);
    set('ho-timerange',  saved.timerange);
    set('ho-wallet',     saved.wallet);
    set('ho-min-trades', saved.min_trades);
    set('ho-dl-exchange',  saved.dl_exchange);
    set('ho-dl-timeframe', saved.dl_timeframe);
    set('ho-dl-days',      saved.dl_days);
    if (Array.isArray(saved.spaces)) {
      const spacesEls = _el ? [..._el.querySelectorAll('#ho-spaces input[type="checkbox"]')] : [];
      spacesEls.forEach(c => { c.checked = saved.spaces.includes(c.value); });
    }
  }

  function _wireSaveEvents() {
    const ids = ['ho-strategy','ho-exchange','ho-loss','ho-epochs','ho-jobs','ho-timeframe','ho-timerange','ho-wallet','ho-min-trades','ho-dl-exchange','ho-dl-timeframe','ho-dl-days'];
    ids.forEach(id => {
      const el = DOM.$(`#${id}`, _el);
      if (el) { el.addEventListener('change', _saveForm); el.addEventListener('input', _saveForm); }
    });
    const spacesEl = DOM.$('#ho-spaces', _el);
    if (spacesEl) spacesEl.addEventListener('change', _saveForm);
    const list = document.getElementById('ho-pairs-list');
    if (list) list.addEventListener('change', e => { if (e.target.classList.contains('pairs-row__check')) _saveForm(); });
  }

  /* ── Picker helpers ── */
  function _updateCount(listId, countId) {
    const checked = document.querySelectorAll(`#${listId} .pairs-row__check:checked`).length;
    const el = document.getElementById(countId);
    if (el) el.textContent = `${checked} selected`;
  }

  function _renderGroup(label, pairs, localSet, configSet, favs, checked = new Set()) {
    if (!pairs.length) return '';
    const dot = localSet.has(pairs[0]) ? '<span style="color:var(--color-green)">⬤</span>' : configSet.has(pairs[0]) ? '<span style="color:var(--violet)">⬤</span>' : '';
    return `<div class="pairs-picker__group-label">${dot} ${_esc(label)}</div>` +
      pairs.map(p => {
        const isFav = favs.has(p);
        const isCk  = checked.has(p);
        const tag   = localSet.has(p) ? '<span class="pairs-row__tag pairs-row__tag--local">Data</span>'
                    : configSet.has(p) ? '<span class="pairs-row__tag pairs-row__tag--config">Config</span>'
                    : '';
        return `<div class="pairs-row${isCk ? ' pairs-row--checked' : ''}" data-pair="${_esc(p)}">
          <button type="button" class="pairs-row__fav${isFav ? ' pairs-row__fav--active' : ''}" data-fav="${_esc(p)}" title="Favourite">♥</button>
          <input type="checkbox" class="pairs-row__check" value="${_esc(p)}"${isCk ? ' checked' : ''}>
          <span class="pairs-row__name">${_esc(p)}</span>${tag}
        </div>`;
      }).join('');
  }

  function _setupPickerEvents(listId, countId, searchId, allBtnId, noneBtnId, favsBtnId) {
    const list = document.getElementById(listId);
    if (!list) return;
    list.addEventListener('change', e => {
      if (!e.target.classList.contains('pairs-row__check')) return;
      const row = e.target.closest('.pairs-row');
      if (row) row.classList.toggle('pairs-row--checked', e.target.checked);
      _updateCount(listId, countId);
    });
    list.addEventListener('click', e => {
      const favBtn = e.target.closest('.pairs-row__fav');
      if (!favBtn) return;
      e.preventDefault();
      const pair = favBtn.dataset.fav;
      const favs = _getFavs();
      if (favs.has(pair)) favs.delete(pair); else favs.add(pair);
      _saveFavs(favs);
      favBtn.classList.toggle('pairs-row__fav--active', favs.has(pair));
    });
    const searchEl = document.getElementById(searchId);
    if (searchEl) {
      searchEl.addEventListener('input', () => {
        const q = searchEl.value.trim().toLowerCase();
        list.querySelectorAll('.pairs-row').forEach(row => {
          row.style.display = (!q || row.dataset.pair.toLowerCase().includes(q)) ? '' : 'none';
        });
        list.querySelectorAll('.pairs-picker__group-label').forEach(gl => {
          let visible = false;
          let sib = gl.nextElementSibling;
          while (sib && !sib.classList.contains('pairs-picker__group-label')) {
            if (sib.style.display !== 'none') { visible = true; break; }
            sib = sib.nextElementSibling;
          }
          gl.style.display = visible || !q ? '' : 'none';
        });
      });
    }
    const allBtn  = document.getElementById(allBtnId);
    const noneBtn = document.getElementById(noneBtnId);
    const favsBtn = document.getElementById(favsBtnId);
    if (allBtn)  allBtn.addEventListener('click',  () => { list.querySelectorAll('.pairs-row__check').forEach(c => { c.checked = true;  c.closest('.pairs-row').classList.add('pairs-row--checked'); }); _updateCount(listId, countId); _saveForm(); });
    if (noneBtn) noneBtn.addEventListener('click', () => { list.querySelectorAll('.pairs-row__check').forEach(c => { c.checked = false; c.closest('.pairs-row').classList.remove('pairs-row--checked'); }); _updateCount(listId, countId); _saveForm(); });
    if (favsBtn) favsBtn.addEventListener('click', () => {
      const favs = _getFavs();
      list.querySelectorAll('.pairs-row__check').forEach(c => { const f = favs.has(c.value); c.checked = f; c.closest('.pairs-row').classList.toggle('pairs-row--checked', f); });
      _updateCount(listId, countId);
      _saveForm();
    });
  }

  function _getSelectedPairs(listId) {
    return [...document.querySelectorAll(`#${listId} .pairs-row__check:checked`)].map(c => c.value);
  }

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
                  <label class="form-label">Pairs</label>
                  <div class="pairs-picker" id="ho-pairs-picker">
                    <div class="pairs-picker__toolbar">
                      <input class="form-input pairs-picker__search" id="ho-pairs-search" type="text" placeholder="Search pairs…" autocomplete="off">
                      <div class="pairs-picker__actions">
                        <button type="button" class="pairs-picker__action" id="ho-pairs-all">All</button>
                        <button type="button" class="pairs-picker__action" id="ho-pairs-none">Clear</button>
                        <button type="button" class="pairs-picker__action" id="ho-pairs-favs">★ Favs</button>
                      </div>
                      <span class="pairs-picker__count" id="ho-pairs-count">0 selected</span>
                    </div>
                    <div class="pairs-picker__list" id="ho-pairs-list">
                      <div class="pairs-picker__empty">Loading…</div>
                    </div>
                  </div>
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
                  <button type="button" class="btn btn--secondary" id="ho-dl-form-btn">
                    <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor"><path d="M8 12l-5-5 1.4-1.4L7 9.2V2h2v7.2l2.6-3.6L13 7l-5 5zM2 14h12v-2H2v2z"/></svg>
                    Download Data
                  </button>
                  <button type="button" class="btn btn--danger" id="ho-stop-btn" style="display:none">Stop</button>
                </div>
                <div class="form form--compact" style="margin-top:var(--space-3)">
                  <div class="form-row">
                    <div class="form-group">
                      <label class="form-label" for="ho-dl-exchange">DL Exchange</label>
                      <select class="form-select" id="ho-dl-exchange">
                        <option value="binance">Binance</option>
                        <option value="kraken">Kraken</option>
                        <option value="okx">OKX</option>
                      </select>
                    </div>
                    <div class="form-group">
                      <label class="form-label" for="ho-dl-timeframe">DL Timeframe</label>
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
                  <div id="ho-dl-log-wrap" style="display:none;margin-top:var(--space-3)">
                    <div class="log-panel" id="ho-dl-logs" style="max-height:160px"></div>
                  </div>
                </div>
              </form>
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
              <div id="ho-cmd"></div>
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

    _setupPickerEvents('ho-pairs-list', 'ho-pairs-count', 'ho-pairs-search', 'ho-pairs-all', 'ho-pairs-none', 'ho-pairs-favs');
    _wireSaveEvents();

    const dlFormBtn = DOM.$('#ho-dl-form-btn', _el);
    DOM.on(dlFormBtn, 'click', _onDownload);
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

      const saved = _loadSavedForm();
      if (saved) _applySavedForm(saved);

      const exVal = DOM.$('#ho-exchange', _el).value || 'binance';
      const preSelected = saved?.pairs?.length ? saved.pairs : null;
      await _loadPairs(exVal, preSelected);
      await _loadHistory();
    } catch (err) {
      Toast.warning('Could not fully load hyperopt form: ' + err.message);
    }
  }

  async function _loadPairs(exchange, preSelected = null) {
    const listEl = DOM.$('#ho-pairs-list', _el);
    if (!listEl) return;
    listEl.innerHTML = '<div class="pairs-picker__empty">Loading…</div>';
    try {
      const data    = await API.getPairs(exchange);
      const local   = data.local_pairs   || [];
      const config  = data.config_pairs  || [];
      const popular = data.popular_pairs || [];

      const localSet  = new Set(local);
      const configSet = new Set(config);
      const favs      = _getFavs();
      const selected  = preSelected ? new Set(preSelected) : new Set();

      const allFavs        = [...local, ...config, ...popular].filter(p => favs.has(p));
      const nonFavLocal    = local.filter(p => !favs.has(p));
      const nonFavConfig   = config.filter(p => !favs.has(p));
      const nonFavPopular  = popular.filter(p => !favs.has(p));

      let html = '';
      if (allFavs.length)      html += _renderGroup('Favourites',      allFavs,       localSet, configSet, favs, selected);
      if (nonFavLocal.length)  html += _renderGroup('Downloaded Data', nonFavLocal,   localSet, configSet, favs, selected);
      if (nonFavConfig.length) html += _renderGroup('From Config',     nonFavConfig,  localSet, configSet, favs, selected);
      if (nonFavPopular.length)html += _renderGroup('Popular Pairs',   nonFavPopular, localSet, configSet, favs, selected);

      listEl.innerHTML = html || '<div class="pairs-picker__empty">No pairs found</div>';
      _updateCount('ho-pairs-list', 'ho-pairs-count');

      const hint = DOM.$('#ho-pairs-hint', _el);
      if (hint) {
        if (local.length) { hint.textContent = `${local.length} pair(s) with downloaded data`; hint.style.color = 'var(--color-green)'; }
        else              { hint.textContent = 'No local data — select pairs then use Download Data'; hint.style.color = 'var(--color-amber)'; }
      }
    } catch {
      listEl.innerHTML = '<div class="pairs-picker__empty">Failed to load pairs</div>';
    }
  }

  /* ── Download Data ── */
  let _dlPollTimer = null;

  async function _onDownload() {
    const exchange = DOM.$('#ho-dl-exchange', _el)?.value || 'binance';
    const tf       = DOM.$('#ho-dl-timeframe', _el)?.value || '5m';
    const days     = parseInt(DOM.$('#ho-dl-days', _el)?.value) || 30;
    const selected = _getSelectedPairs('ho-pairs-list');

    if (!selected.length) { Toast.warning('Select at least one pair to download.'); return; }

    const formBtn = DOM.$('#ho-dl-form-btn', _el);
    const logEl   = DOM.$('#ho-dl-logs', _el);
    const logWrap = DOM.$('#ho-dl-log-wrap', _el);

    if (formBtn) formBtn.disabled = true;
    if (logWrap) DOM.show(logWrap);

    try {
      const res = await API.downloadData({ pairs: selected, timeframe: tf, exchange, days });
      _pollDownload(res.job_id || res.run_id, logEl, formBtn);
      Toast.info('Download started…');
    } catch (err) {
      if (formBtn) formBtn.disabled = false;
      Toast.error('Download failed: ' + err.message);
    }
  }

  function _pollDownload(jobId, logEl, formBtn) {
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
          if (formBtn) formBtn.disabled = false;
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
    const pairs   = _getSelectedPairs('ho-pairs-list');
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

  const _CMD_EXEC = new Set(['python','python3','-m','freqtrade','backtesting','hyperopt','download-data']);
  function _classifyToken(tok) {
    if (_CMD_EXEC.has(tok))                              return 'exec';
    if (tok.startsWith('-'))                              return 'flag';
    if (tok.includes('/') || tok.includes('user_data'))  return 'path';
    return 'value';
  }

  function _renderCommandBlock(container, cmd) {
    if (!container || !cmd?.length) return;
    const flat = cmd.join(' ');
    const highlighted = cmd.map(tok => {
      const type = _classifyToken(tok);
      return `<span class="cmd-token cmd-token--${type}">${_esc(tok)}</span>`;
    }).join(' ');

    container.innerHTML = `
      <div class="cmd-block">
        <div class="cmd-block__header">
          <span class="cmd-block__label">Command</span>
          <button class="cmd-block__copy">Copy</button>
        </div>
        <pre class="cmd-block__pre">${highlighted}</pre>
      </div>`;

    const copyBtn = container.querySelector('.cmd-block__copy');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(flat).then(() => {
          copyBtn.textContent = 'Copied!';
          copyBtn.classList.add('cmd-block__copy--copied');
          setTimeout(() => { copyBtn.textContent = 'Copy'; copyBtn.classList.remove('cmd-block__copy--copied'); }, 2000);
        }).catch(() => { copyBtn.textContent = 'Copy failed'; setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000); });
      });
    }
  }

  function _updateStatus(data) {
    const badge      = DOM.$('#ho-status-badge', _el);
    const cmdEl      = DOM.$('#ho-cmd', _el);
    const logsEl     = DOM.$('#ho-logs', _el);
    const progressEl = DOM.$('#ho-progress', _el);
    const resCard    = DOM.$('#ho-results-card', _el);
    const resBody    = DOM.$('#ho-results-body', _el);
    const applyBtn   = DOM.$('#ho-apply-btn', _el);

    if (badge) { badge.className = `badge badge--${FMT.statusColor(data.status)}`; badge.textContent = FMT.statusLabel(data.status); }
    if (cmdEl && data.meta?.command?.length && !cmdEl.querySelector('.cmd-block')) {
      _renderCommandBlock(cmdEl, data.meta.command);
    }

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
