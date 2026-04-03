/* =================================================================
   BACKTESTING PAGE
   Exposes: window.BacktestPage
   ================================================================= */

window.BacktestPage = (() => {
  let _el = null;
  let _pollTimer = null;
  let _currentRunId = null;

  /* ── Favourites ── */
  const _FAV_KEY  = '4tie_fav_pairs';
  const _FORM_KEY = '4tie_bt_form';
  function _getFavs() { try { return new Set(JSON.parse(localStorage.getItem(_FAV_KEY) || '[]')); } catch { return new Set(); } }
  function _saveFavs(s) { localStorage.setItem(_FAV_KEY, JSON.stringify([...s])); }

  /* ── Form persistence ── */
  function _saveForm() {
    const get = id => { const el = DOM.$(`#${id}`, _el); return el ? el.value : undefined; };
    const saved = {
      strategy:     get('bt-strategy'),
      exchange:     get('bt-exchange'),
      timeframe:    get('bt-timeframe'),
      timerange:    get('bt-timerange'),
      wallet:       get('bt-wallet'),
      max_trades:   get('bt-max-trades'),
      stake:        get('bt-stake'),
      dl_exchange:  get('bt-dl-exchange'),
      dl_timeframe: get('bt-dl-timeframe'),
      dl_days:      get('bt-dl-days'),
      pairs:        _getSelectedPairs('bt-pairs-list'),
    };
    try { localStorage.setItem(_FORM_KEY, JSON.stringify(saved)); } catch {}
  }

  function _loadSavedForm() {
    try { return JSON.parse(localStorage.getItem(_FORM_KEY) || 'null'); } catch { return null; }
  }

  function _applySavedForm(saved) {
    if (!saved) return;
    const set = (id, v) => { const el = DOM.$(`#${id}`, _el); if (el && v != null && v !== '') el.value = v; };
    set('bt-strategy',   saved.strategy);
    set('bt-exchange',   saved.exchange);
    set('bt-timeframe',  saved.timeframe);
    set('bt-timerange',  saved.timerange);
    set('bt-wallet',     saved.wallet);
    set('bt-max-trades', saved.max_trades);
    set('bt-stake',      saved.stake);
    set('bt-dl-exchange',  saved.dl_exchange);
    set('bt-dl-timeframe', saved.dl_timeframe);
    set('bt-dl-days',      saved.dl_days);
  }

  function _wireSaveEvents() {
    const ids = ['bt-strategy','bt-exchange','bt-timeframe','bt-timerange','bt-wallet','bt-max-trades','bt-stake','bt-dl-exchange','bt-dl-timeframe','bt-dl-days'];
    ids.forEach(id => {
      const el = DOM.$(`#${id}`, _el);
      if (el) { el.addEventListener('change', _saveForm); el.addEventListener('input', _saveForm); }
    });
    const list = document.getElementById('bt-pairs-list');
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
        const isFav  = favs.has(p);
        const isCk   = checked.has(p);
        const isLocal = localSet.has(p);
        const isCfg  = configSet.has(p);
        const tag = isLocal ? '<span class="pairs-row__tag pairs-row__tag--local">Data</span>'
                  : isCfg   ? '<span class="pairs-row__tag pairs-row__tag--config">Config</span>'
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
      _refreshCommandPreview();
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
          const next = gl.nextElementSibling;
          gl.style.display = (!next || next.style.display !== 'none') ? '' : 'none';
        });
      });
    }

    const allBtn  = document.getElementById(allBtnId);
    const noneBtn = document.getElementById(noneBtnId);
    const favsBtn = document.getElementById(favsBtnId);

    if (allBtn) allBtn.addEventListener('click', () => {
      list.querySelectorAll('.pairs-row__check').forEach(c => { c.checked = true; c.closest('.pairs-row').classList.add('pairs-row--checked'); });
      _updateCount(listId, countId);
      _saveForm();
      _refreshCommandPreview();
    });
    if (noneBtn) noneBtn.addEventListener('click', () => {
      list.querySelectorAll('.pairs-row__check').forEach(c => { c.checked = false; c.closest('.pairs-row').classList.remove('pairs-row--checked'); });
      _updateCount(listId, countId);
      _saveForm();
      _refreshCommandPreview();
    });
    if (favsBtn) favsBtn.addEventListener('click', () => {
      const favs = _getFavs();
      list.querySelectorAll('.pairs-row__check').forEach(c => {
        const isFav = favs.has(c.value);
        c.checked = isFav;
        c.closest('.pairs-row').classList.toggle('pairs-row--checked', isFav);
      });
      _updateCount(listId, countId);
      _saveForm();
      _refreshCommandPreview();
    });
  }

  function _getSelectedPairs(listId) {
    return [...document.querySelectorAll(`#${listId} .pairs-row__check:checked`)].map(c => c.value);
  }

  /* ── Live command preview ── */
  function _buildLiveCommand() {
    const get = id => { const el = DOM.$(`#${id}`, _el); return el ? el.value : ''; };
    const strategy  = get('bt-strategy')  || '';
    const timeframe = get('bt-timeframe') || '5m';
    const timerange = get('bt-timerange') || '';
    const pairs     = _getSelectedPairs('bt-pairs-list');

    const cmd = [
      'python', '-m', 'freqtrade', 'backtesting',
      '-c', 'user_data/config.json',
      '--timeframe', timeframe,
      '--export', 'trades',
      '--export-filename', `user_data/backtest_results/${strategy || '<strategy>'}/result.json`,
    ];

    if (timerange) cmd.push('--timerange', timerange);
    if (pairs.length) cmd.push('--pairs', ...pairs);

    return cmd;
  }

  function _refreshCommandPreview() {
    const cmdEl = DOM.$('#bt-cmd-preview', _el);
    if (!cmdEl) return;
    const pairs = _getSelectedPairs('bt-pairs-list');
    if (!pairs.length) { cmdEl.innerHTML = ''; return; }
    const cmd = _buildLiveCommand();
    _renderCommandBlock(cmdEl, cmd);
  }

  function _wirePreviewEvents() {
    const liveIds = ['bt-strategy', 'bt-timeframe', 'bt-timerange'];
    liveIds.forEach(id => {
      const el = DOM.$(`#${id}`, _el);
      if (el) {
        el.addEventListener('change', _refreshCommandPreview);
        el.addEventListener('input', _refreshCommandPreview);
      }
    });
  }

  /* ── Live config sync for 4 fields ── */
  let _savedIndicatorTimer = null;
  function _showSaved(fieldId) {
    const el = DOM.$(`#${fieldId}-saved`, _el);
    if (!el) return;
    el.textContent = 'Saved';
    el.style.opacity = '1';
    clearTimeout(_savedIndicatorTimer);
    _savedIndicatorTimer = setTimeout(() => { el.style.opacity = '0'; }, 2000);
  }

  function _wireConfigSyncEvents() {
    const configFields = [
      { id: 'bt-strategy',   key: 'strategy' },
      { id: 'bt-wallet',     key: 'dry_run_wallet' },
      { id: 'bt-max-trades', key: 'max_open_trades' },
      { id: 'bt-stake',      key: 'stake_amount' },
    ];
    configFields.forEach(({ id, key }) => {
      const el = DOM.$(`#${id}`, _el);
      if (!el) return;
      el.addEventListener('change', async () => {
        let value = el.value;
        if (key === 'dry_run_wallet') value = parseFloat(value) || 1000;
        if (key === 'max_open_trades') value = parseInt(value) || 3;
        try {
          await API.patchConfig({ [key]: value });
          _showSaved(id);
          _refreshCommandPreview();
        } catch {}
      });
    });
  }

  function init() {
    _el = DOM.$('[data-view="backtesting"]');
    if (!_el) return;
    _render();
    _loadFormData();
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="page-header">
        <h1 class="page-header__title">Backtesting</h1>
        <p class="page-header__subtitle">Configure and run a backtest against historical market data.</p>
      </div>
      <div class="split-layout">
        <!-- Form panel -->
        <div class="split-layout__form">
          <div class="card">
            <div class="card__header"><span class="card__title">Configuration</span></div>
            <div class="card__body">
              <form id="bt-form" class="form">
                <div class="form-group">
                  <label class="form-label" for="bt-strategy">Strategy <span id="bt-strategy-saved" style="font-size:var(--text-xs);color:var(--color-green);opacity:0;transition:opacity 0.5s;margin-left:6px"></span></label>
                  <select class="form-select" id="bt-strategy" name="strategy" required>
                    <option value="">Loading strategies…</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label" for="bt-exchange">Exchange</label>
                  <select class="form-select" id="bt-exchange" name="exchange">
                    <option value="binance">Binance</option>
                    <option value="kraken">Kraken</option>
                    <option value="ftx">FTX</option>
                    <option value="okx">OKX</option>
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Pairs</label>
                  <div class="pairs-picker" id="bt-pairs-picker">
                    <div class="pairs-picker__toolbar">
                      <input class="form-input pairs-picker__search" id="bt-pairs-search" type="text" placeholder="Search pairs…" autocomplete="off">
                      <div class="pairs-picker__actions">
                        <button type="button" class="pairs-picker__action" id="bt-pairs-all">All</button>
                        <button type="button" class="pairs-picker__action" id="bt-pairs-none">Clear</button>
                        <button type="button" class="pairs-picker__action" id="bt-pairs-favs">★ Favs</button>
                      </div>
                      <span class="pairs-picker__count" id="bt-pairs-count">0 selected</span>
                    </div>
                    <div class="pairs-picker__list" id="bt-pairs-list">
                      <div class="pairs-picker__empty">Loading…</div>
                    </div>
                  </div>
                  <div id="bt-pairs-hint" class="form-hint" style="margin-top:4px"></div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label" for="bt-timeframe">Timeframe</label>
                    <select class="form-select" id="bt-timeframe" name="timeframe">
                      <option value="1m">1m</option>
                      <option value="5m" selected>5m</option>
                      <option value="15m">15m</option>
                      <option value="30m">30m</option>
                      <option value="1h">1h</option>
                      <option value="4h">4h</option>
                      <option value="1d">1d</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="bt-timerange">Timerange</label>
                    <input class="form-input" id="bt-timerange" name="timerange" type="text" placeholder="20230101-20240101">
                  </div>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label" for="bt-wallet">Starting Wallet <span id="bt-wallet-saved" style="font-size:var(--text-xs);color:var(--color-green);opacity:0;transition:opacity 0.5s;margin-left:6px"></span></label>
                    <input class="form-input" id="bt-wallet" name="dry_run_wallet" type="number" value="1000" min="1">
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="bt-max-trades">Max Open Trades <span id="bt-max-trades-saved" style="font-size:var(--text-xs);color:var(--color-green);opacity:0;transition:opacity 0.5s;margin-left:6px"></span></label>
                    <input class="form-input" id="bt-max-trades" name="max_open_trades" type="number" value="3" min="1">
                  </div>
                </div>
                <div class="form-group">
                  <label class="form-label" for="bt-stake">Stake Amount <span id="bt-stake-saved" style="font-size:var(--text-xs);color:var(--color-green);opacity:0;transition:opacity 0.5s;margin-left:6px"></span></label>
                  <input class="form-input" id="bt-stake" name="stake_amount" type="text" value="unlimited">
                </div>
                <div id="bt-cmd-preview"></div>
                <div class="form-actions">
                  <button type="submit" class="btn btn--primary" id="bt-run-btn">
                    <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor"><path d="M3 2l10 6-10 6V2z"/></svg>
                    Run Backtest
                  </button>
                  <button type="button" class="btn btn--secondary" id="bt-dl-form-btn">
                    <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor"><path d="M8 12l-5-5 1.4-1.4L7 9.2V2h2v7.2l2.6-3.6L13 7l-5 5zM2 14h12v-2H2v2z"/></svg>
                    Download Data
                  </button>
                  <button type="button" class="btn btn--danger" id="bt-stop-btn" style="display:none">Stop</button>
                </div>
                <div class="form form--compact" style="margin-top:var(--space-3)">
                  <div id="bt-dl-log-wrap" style="display:none;margin-top:var(--space-3)">
                    <div class="log-panel" id="bt-dl-logs" style="max-height:160px"></div>
                  </div>
                </div>
              </form>
            </div>
          </div>
        </div>
        <!-- Output panel -->
        <div class="split-layout__output">
          <div class="card" id="bt-status-card" style="display:none">
            <div class="card__header">
              <span class="card__title">Status</span>
              <span class="badge" id="bt-status-badge">—</span>
            </div>
            <div class="card__body">
              <div class="log-panel" id="bt-logs"></div>
            </div>
          </div>
          <div class="card" id="bt-results-card" style="display:none">
            <div class="card__header">
              <span class="card__title">Results</span>
              <button class="btn btn--danger btn--sm" id="bt-delete-btn">Delete Run</button>
            </div>
            <div class="card__body" id="bt-results-body"></div>
          </div>
          <div class="card" id="bt-history-card">
            <div class="card__header"><span class="card__title">Recent Runs</span></div>
            <div class="card__body" id="bt-history-body"><div class="empty-state">No runs yet.</div></div>
          </div>
        </div>
      </div>
    `);

    const form     = DOM.$('#bt-form', _el);
    const exchange = DOM.$('#bt-exchange', _el);
    const stopBtn  = DOM.$('#bt-stop-btn', _el);
    const delBtn   = DOM.$('#bt-delete-btn', _el);

    DOM.on(exchange, 'change', () => _loadPairs(exchange.value));
    DOM.on(form,     'submit', _onSubmit);
    DOM.on(stopBtn,  'click',  _onStop);
    DOM.on(delBtn,   'click',  _onDeleteRun);

    _setupPickerEvents('bt-pairs-list', 'bt-pairs-count', 'bt-pairs-search', 'bt-pairs-all', 'bt-pairs-none', 'bt-pairs-favs');
    _wireSaveEvents();
    _wirePreviewEvents();
    _wireConfigSyncEvents();

    const dlFormBtn = DOM.$('#bt-dl-form-btn', _el);
    DOM.on(dlFormBtn, 'click', _onDownload);

    _loadHistory();
  }

  async function _loadHistory() {
    const wrap = DOM.$('#bt-history-body', _el);
    if (!wrap) return;
    try {
      const data = await API.getRuns();
      const runs = (data.runs || []).slice(-8).reverse();
      if (!runs.length) { wrap.innerHTML = '<div class="empty-state">No runs yet.</div>'; return; }
      wrap.innerHTML = `
        <table class="data-table data-table--sm">
          <thead><tr><th>Run ID</th><th>Strategy</th><th>Status</th><th>Started</th><th></th></tr></thead>
          <tbody>
            ${runs.map(r => `
              <tr>
                <td class="font-mono text-sm">${FMT.truncate(r.run_id || '—', 18)}</td>
                <td>${r.strategy || '—'}</td>
                <td><span class="badge badge--${FMT.statusColor(r.status)}">${FMT.statusLabel(r.status)}</span></td>
                <td class="text-muted text-sm">${FMT.tsShort(r.started_at)}</td>
                <td><button class="btn btn--danger btn--sm" data-delete-run="${_esc(r.run_id || '')}">Delete</button></td>
              </tr>`).join('')}
          </tbody>
        </table>`;
      wrap.querySelectorAll('[data-delete-run]').forEach(btn => {
        DOM.on(btn, 'click', () => _deleteRun(btn.dataset.deleteRun));
      });
    } catch {}
  }

  async function _onDeleteRun() {
    if (!_currentRunId) { Toast.warning('No active run to delete.'); return; }
    await _deleteRun(_currentRunId);
  }

  async function _deleteRun(runId) {
    if (!runId) return;
    if (!confirm(`Delete run ${runId}? This cannot be undone.`)) return;
    try {
      await API.deleteRun(runId);
      Toast.success(`Run deleted.`);
      if (runId === _currentRunId) {
        _currentRunId = null;
        DOM.hide(DOM.$('#bt-status-card', _el));
        DOM.hide(DOM.$('#bt-results-card', _el));
        AppState.set('stream', 'Run deleted.');
      }
      _loadHistory();
    } catch (err) {
      Toast.error('Failed to delete run: ' + err.message);
    }
  }

  async function _loadFormData() {
    try {
      const [strats, lastCfg, configJson] = await Promise.all([
        API.getStrategies().catch(() => ({ strategies: [] })),
        API.getLastConfig().catch(() => ({ config: null })),
        API.getConfig().catch(() => null),
      ]);

      const select = DOM.$('#bt-strategy', _el);
      const strategies = strats.strategies || [];
      if (strategies.length) {
        select.innerHTML = strategies.map(s =>
          `<option value="${_esc(s.name || s)}">${_esc(s.name || s)}</option>`
        ).join('');
      } else {
        select.innerHTML = '<option value="">No strategies found</option>';
      }

      const saved = _loadSavedForm();
      if (saved) {
        _applySavedForm(saved);
      } else if (lastCfg.config) {
        _applyLastConfig(lastCfg.config);
      }

      if (configJson) {
        _applyConfigJson(configJson);
      }

      const exVal     = DOM.$('#bt-exchange', _el).value || 'binance';
      const preSelected = saved?.pairs?.length ? saved.pairs : (lastCfg.config?.pairs || null);
      await _loadPairs(exVal, preSelected);

      _refreshCommandPreview();
    } catch (err) {
      Toast.warning('Could not load form data: ' + err.message);
    }
  }

  function _applyConfigJson(cfg) {
    const set = (id, v) => { const el = DOM.$(`#${id}`, _el); if (el && v != null) el.value = v; };
    if (cfg.strategy     != null) set('bt-strategy',   cfg.strategy);
    if (cfg.dry_run_wallet != null) set('bt-wallet',   cfg.dry_run_wallet);
    if (cfg.max_open_trades != null) set('bt-max-trades', cfg.max_open_trades);
    if (cfg.stake_amount != null) set('bt-stake',      cfg.stake_amount);
  }

  async function _loadPairs(exchange, preSelected = null) {
    const listEl = DOM.$('#bt-pairs-list', _el);
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

      const favLocal   = local.filter(p => favs.has(p));
      const favConfig  = config.filter(p => favs.has(p));
      const favPopular = popular.filter(p => favs.has(p));
      const allFavs    = [...favLocal, ...favConfig, ...favPopular];

      const nonFavLocal   = local.filter(p => !favs.has(p));
      const nonFavConfig  = config.filter(p => !favs.has(p));
      const nonFavPopular = popular.filter(p => !favs.has(p));

      let html = '';
      if (allFavs.length)      html += _renderGroup('Favourites',       allFavs,      localSet, configSet, favs, selected);
      if (nonFavLocal.length)  html += _renderGroup('Downloaded Data',  nonFavLocal,  localSet, configSet, favs, selected);
      if (nonFavConfig.length) html += _renderGroup('From Config',      nonFavConfig, localSet, configSet, favs, selected);
      if (nonFavPopular.length) html += _renderGroup('Popular Pairs',   nonFavPopular,localSet, configSet, favs, selected);

      listEl.innerHTML = html || '<div class="pairs-picker__empty">No pairs found</div>';
      _updateCount('bt-pairs-list', 'bt-pairs-count');

      const hint = DOM.$('#bt-pairs-hint', _el);
      if (hint) {
        if (local.length) {
          hint.textContent = `${local.length} pair(s) with downloaded data`;
          hint.style.color = 'var(--color-green)';
        } else {
          hint.textContent = 'No local data — select pairs then use Download Data';
          hint.style.color = 'var(--color-amber)';
        }
      }

      _refreshCommandPreview();
    } catch {
      listEl.innerHTML = '<div class="pairs-picker__empty">Failed to load pairs</div>';
    }
  }

  /* ── Download Data ── */
  let _dlPollTimer = null;

  async function _onDownload() {
    const tf       = DOM.$('#bt-timeframe', _el)?.value || '5m';
    const selected = _getSelectedPairs('bt-pairs-list');

    if (!selected.length) { Toast.warning('Select at least one pair to download.'); return; }

    const formBtn = DOM.$('#bt-dl-form-btn', _el);
    const logEl   = DOM.$('#bt-dl-logs', _el);
    const logWrap = DOM.$('#bt-dl-log-wrap', _el);

    if (formBtn) formBtn.disabled = true;
    if (logWrap) DOM.show(logWrap);

    try {
      const res = await API.downloadData({ pairs: selected, timeframe: tf });
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
            const ex = DOM.$('#bt-exchange', _el)?.value || 'binance';
            await _loadPairs(ex);
          } else {
            Toast.error('Download failed.');
          }
        }
      } catch {}
    }, 2500);
  }

  function _applyLastConfig(cfg) {
    const set = (id, v) => { const el = DOM.$(id, _el); if (el && v != null) el.value = v; };
    set('#bt-strategy',   cfg.strategy);
    set('#bt-exchange',   cfg.exchange);
    set('#bt-timeframe',  cfg.timeframe);
    set('#bt-timerange',  cfg.timerange);
    set('#bt-wallet',     cfg.dry_run_wallet);
    set('#bt-max-trades', cfg.max_open_trades);
    set('#bt-stake',      cfg.stake_amount);
  }

  async function _onSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const fd   = new FormData(form);
    const selectedPairs = _getSelectedPairs('bt-pairs-list');

    if (!selectedPairs.length) { Toast.warning('Select at least one pair.'); return; }

    const body = {
      strategy:        fd.get('strategy'),
      pairs:           selectedPairs,
      timeframe:       fd.get('timeframe') || '5m',
      timerange:       fd.get('timerange') || null,
      exchange:        fd.get('exchange') || 'binance',
    };

    _setRunning(true);
    try {
      const res = await API.startBacktest(body);
      _currentRunId = res.run_id;
      AppState.set('stream', `Backtest started: ${_currentRunId}`);
      Auth.setRunning(true);
      _startPoll(_currentRunId);
      Toast.success('Backtest started.');
    } catch (err) {
      _setRunning(false);
      Toast.error('Failed to start backtest: ' + err.message);
    }
  }

  function _startPoll(runId) {
    _stopPoll();
    const card = DOM.$('#bt-status-card', _el);
    DOM.show(card);
    _pollTimer = setInterval(async () => {
      try {
        const data = await API.getRun(runId);
        _updateStatus(data);
        if (data.status === 'completed' || data.status === 'failed') {
          _stopPoll();
          _setRunning(false);
          Auth.setRunning(false);
          AppState.set('stream', `Backtest ${data.status}: ${runId}`);
          if (data.status === 'completed') Toast.success('Backtest completed.');
          else Toast.error('Backtest failed.');
        }
      } catch {}
    }, 2000);
  }

  const _CMD_EXEC = new Set(['python','python3','-m','freqtrade','backtesting','hyperopt','download-data']);
  function _classifyToken(tok) {
    if (_CMD_EXEC.has(tok))                         return 'exec';
    if (tok.startsWith('-'))                         return 'flag';
    if (tok.includes('/') || tok.includes('user_data')) return 'path';
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
          setTimeout(() => {
            copyBtn.textContent = 'Copy';
            copyBtn.classList.remove('cmd-block__copy--copied');
          }, 2000);
        }).catch(() => {
          copyBtn.textContent = 'Copy failed';
          setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
        });
      });
    }
  }

  function _updateStatus(data) {
    const badge   = DOM.$('#bt-status-badge', _el);
    const logs    = DOM.$('#bt-logs', _el);
    const resCard = DOM.$('#bt-results-card', _el);
    const resBody = DOM.$('#bt-results-body', _el);

    if (badge) {
      badge.className = `badge badge--${FMT.statusColor(data.status)}`;
      badge.textContent = FMT.statusLabel(data.status);
    }
    if (logs) {
      logs.innerHTML = (data.logs || []).slice(-200).map(l => `<div class="log-line">${_esc(l)}</div>`).join('');
      logs.scrollTop = logs.scrollHeight;
    }
    if (data.status === 'completed' && data.results) {
      DOM.show(resCard);
      _renderResults(resBody, data.results);
    }
  }

  function _renderResults(el, results) {
    if (!el || !results) return;
    const ov = results.overview || {};
    el.innerHTML = `
      <div class="results-overview">
        ${_metric('Total Profit %',   FMT.pct((ov.profit_percent||0)*100), (ov.profit_percent||0)>0?'green':'red')}
        ${_metric('Profit (abs)',      FMT.currency(ov.profit_total_abs||0))}
        ${_metric('Total Trades',     ov.total_trades ?? '—')}
        ${_metric('Win Rate',         ov.win_rate != null ? FMT.pct((ov.win_rate||0)*100,1,false) : '—', 'muted')}
        ${_metric('Max Drawdown',     ov.max_drawdown != null ? FMT.pct(Math.abs((ov.max_drawdown||0)*100),1,false) : '—', 'red')}
        ${_metric('Sharpe Ratio',     FMT.number(ov.sharpe_ratio))}
        ${_metric('Final Balance',    FMT.currency(ov.final_balance))}
      </div>`;
  }

  function _metric(label, value, color = '') {
    return `<div class="metric-item"><span class="metric-label">${label}</span><span class="metric-value ${color ? 'text-' + color : ''}">${value}</span></div>`;
  }

  function _onStop() {
    if (!_currentRunId) return;
    _stopPoll();
    _setRunning(false);
    Auth.setRunning(false);
    Toast.info('Stopped polling. Job may still be running on server.');
  }

  function _setRunning(running) {
    const runBtn  = DOM.$('#bt-run-btn', _el);
    const stopBtn = DOM.$('#bt-stop-btn', _el);
    if (runBtn)  runBtn.disabled = running;
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

  function refresh() { _loadFormData(); }

  return { init, refresh };
})();
