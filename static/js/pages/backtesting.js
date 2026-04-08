/* =================================================================
   BACKTESTING PAGE
   Exposes: window.BacktestPage
   ================================================================= */

window.BacktestPage = (() => {
  const _PENDING_STRATEGY_RERUN_KEY = '4tie_pending_strategy_intelligence_rerun';
  let _el = null;
  let _pollTimer = null;
  let _activeRunId = null;
  let _resultRunId = null;
  let _loadedResult = null;
  let _strategyRerunStarting = false;
  let _strategyRerunPhase = 'idle';
  let _quickParamsState = _createQuickParamsState();
  let _strategyRerunReview = _createStrategyRerunReviewState();
  let _intelligenceEventBound = false;
  let _pendingStrategyRerunConsuming = false;

  /* ── Favourites ── */
  const _FAV_KEY  = '4tie_fav_pairs';
  const _FORM_KEY = '4tie_bt_form';
  const _QUICK_PARAM_GROUP_ORDER = ['buy', 'sell'];
  function _getFavs() { try { return new Set(JSON.parse(localStorage.getItem(_FAV_KEY) || '[]')); } catch { return new Set(); } }
  function _saveFavs(s) { localStorage.setItem(_FAV_KEY, JSON.stringify([...s])); }

  function _createQuickParamsState() {
    return {
      runId: null,
      strategyName: null,
      strategyLabel: null,
      strategyPath: null,
      mode: 'editable',
      meta: null,
      parameters: [],
      seedValues: {},
      currentValues: {},
      loading: false,
      saving: false,
      error: '',
      empty: '',
      notice: '',
    };
  }

  function _createStrategyRerunReviewState() {
    return {
      active: false,
      sourceRunId: null,
      strategyName: null,
      strategyLabel: null,
      baselineParams: {},
      autoChanges: [],
      manualItems: [],
      unsupportedItems: [],
      improvementItems: [],
      improvementBrief: '',
      diagnosisTitle: '',
      contextOnly: false,
      validationMessage: '',
    };
  }

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
    const dot = localSet.has(pairs[0]) ? '<span style="color:var(--green)">⬤</span>' : configSet.has(pairs[0]) ? '<span style="color:var(--accent)">⬤</span>' : '';
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

  function _buildDownloadCommand() {
    const get = id => { const el = DOM.$(`#${id}`, _el); return el ? el.value : ''; };
    const timeframe = get('bt-timeframe') || '5m';
    const timerange = get('bt-timerange') || '';
    const pairs = _getSelectedPairs('bt-pairs-list');
    const cmd = [
      'python', '-m', 'freqtrade', 'download-data',
      '-c', 'user_data/config.json',
      '--timeframes', timeframe,
    ];
    if (timerange) cmd.push('--timerange', timerange);
    if (pairs.length) cmd.push('--pairs', ...pairs);
    return cmd;
  }

  function _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function _tokenizeEditedCommand(text) {
    const src = String(text || '').trim();
    if (!src) return [];
    const tokens = src.match(/"[^"]*"|'[^']*'|\S+/g) || [];
    return tokens.map(t => t.replace(/^['"]|['"]$/g, ''));
  }

  async function _editCommandBeforeRun(defaultCmd) {
    const initial = defaultCmd.join(' ');
    let edited = null;
    try {
      if (window.Modal && typeof window.Modal.codePrompt === 'function') {
        edited = await window.Modal.codePrompt({
          title: 'Edit Command',
          message: 'Review or modify the command before execution.',
          label: 'Command',
          value: initial,
          confirmLabel: 'Run',
          cancelLabel: 'Cancel',
        });
      } else {
        edited = window.prompt('Edit command before run:', initial);
      }
    } catch (err) {
      Toast.error('Command editor failed to open: ' + (err?.message || String(err)));
      return null;
    }
    if (edited === null) return null;
    const tokens = _tokenizeEditedCommand(edited);
    if (!tokens.length) {
      Toast.warning('Command cannot be empty.');
      return null;
    }
    return tokens;
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
      '--strategy', strategy || '<strategy>',
      '--timeframe', timeframe,
      '--export', 'trades',
      '--backtest-directory', `user_data/backtest_results/${strategy || '<strategy>'}`,
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
    void _consumePendingStrategyIntelligenceRerun();
  }

  function _readPendingStrategyIntelligenceRerun() {
    try {
      const raw = sessionStorage.getItem(_PENDING_STRATEGY_RERUN_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') {
        _clearPendingStrategyIntelligenceRerun();
        return null;
      }
      return parsed;
    } catch {
      _clearPendingStrategyIntelligenceRerun();
      return null;
    }
  }

  function _clearPendingStrategyIntelligenceRerun() {
    try {
      sessionStorage.removeItem(_PENDING_STRATEGY_RERUN_KEY);
    } catch {}
  }

  async function _consumePendingStrategyIntelligenceRerun() {
    if (_pendingStrategyRerunConsuming) return;
    const pending = _readPendingStrategyIntelligenceRerun();
    if (!pending) return;
    _pendingStrategyRerunConsuming = true;
    try {
      await _onStrategyIntelligenceEvent({ detail: pending });
      _clearPendingStrategyIntelligenceRerun();
    } catch (err) {
      Toast.error('Failed to start rerun: ' + (err?.message || err));
    } finally {
      _pendingStrategyRerunConsuming = false;
    }
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="page-frame page-frame--compact backtesting-page">
        <div class="page-header">
          <h1 class="page-header__title">Backtesting</h1>
          <p class="page-header__subtitle">Configure, run, review, and refine a backtest from one compact workspace.</p>
        </div>
      <div class="split-layout">
        <!-- Form panel -->
        <div class="split-layout__form">
          <div class="card card--panel bt-config-card">
            <div class="card__header"><span class="card__title">Configuration</span></div>
            <div class="card__body">
              <form id="bt-form" class="form">
                <div class="form-group">
                  <label class="form-label" for="bt-strategy">Strategy <span id="bt-strategy-saved" style="font-size:var(--text-xs);color:var(--green);opacity:0;transition:opacity 0.5s;margin-left:6px"></span></label>
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
                    <label class="form-label" for="bt-wallet">Starting Wallet <span id="bt-wallet-saved" style="font-size:var(--text-xs);color:var(--green);opacity:0;transition:opacity 0.5s;margin-left:6px"></span></label>
                    <input class="form-input" id="bt-wallet" name="dry_run_wallet" type="number" value="1000" min="1">
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="bt-max-trades">Max Open Trades <span id="bt-max-trades-saved" style="font-size:var(--text-xs);color:var(--green);opacity:0;transition:opacity 0.5s;margin-left:6px"></span></label>
                    <input class="form-input" id="bt-max-trades" name="max_open_trades" type="number" value="3" min="1">
                  </div>
                </div>
                <div class="form-group">
                  <label class="form-label" for="bt-stake">Stake Amount <span id="bt-stake-saved" style="font-size:var(--text-xs);color:var(--green);opacity:0;transition:opacity 0.5s;margin-left:6px"></span></label>
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
          <div class="card card--utility" id="bt-status-card" style="display:none">
            <div class="card__header">
              <span class="card__title">Status</span>
              <span class="badge" id="bt-status-badge">—</span>
            </div>
            <div class="card__body">
              <div class="log-panel" id="bt-logs"></div>
            </div>
          </div>
          <div class="card card--hero" id="bt-results-card" style="display:none">
            <div class="card__header">
              <span class="card__title">Results</span>
              <button class="btn btn--danger btn--sm" id="bt-delete-btn">Delete Run</button>
            </div>
            <div class="card__body" id="bt-results-body"></div>
          </div>
          <div class="card card--panel" id="bt-quick-params-card" style="display:none">
            <div class="card__header">
              <span class="card__title">Quick Parameter Changes</span>
            </div>
            <div class="card__body" id="bt-quick-params-body"></div>
          </div>
        </div>
      </div>
      </div>
    `);

    const form     = DOM.$('#bt-form', _el);
    const exchange = DOM.$('#bt-exchange', _el);
    const stopBtn  = DOM.$('#bt-stop-btn', _el);
    const delBtn   = DOM.$('#bt-delete-btn', _el);
    const resultCard = DOM.$('#bt-results-card', _el);
    const quickParamsBody = DOM.$('#bt-quick-params-body', _el);

    DOM.on(exchange, 'change', () => _loadPairs(exchange.value));
    DOM.on(form,     'submit', _onSubmit);
    DOM.on(stopBtn,  'click',  _onStop);
    DOM.on(delBtn,   'click',  _onDeleteRun);
    DOM.on(resultCard, 'click', (e) => {
      if (!_resultRunId) return;
      if (e.target.closest('#bt-delete-btn')) return;
      const reviewPanel = e.target.closest('.bt-intelligence__panel--comparison');
      if (reviewPanel) {
        const reviewAction = e.target.closest('[data-intelligence-review-action]');
        if (reviewAction) {
          e.preventDefault();
          e.stopPropagation();
          _onStrategyIntelligenceReviewAction(reviewAction.dataset.intelligenceReviewAction || '');
        }
        return;
      }
      const reviewAction = e.target.closest('[data-intelligence-review-action]');
      if (reviewAction) {
        e.preventDefault();
        e.stopPropagation();
        _onStrategyIntelligenceReviewAction(reviewAction.dataset.intelligenceReviewAction || '');
        return;
      }
      const intelligenceAction = e.target.closest('[data-intelligence-action]');
      if (intelligenceAction) {
        e.preventDefault();
        e.stopPropagation();
        _onStrategyIntelligenceAction(intelligenceAction.dataset.intelligenceAction || '');
        return;
      }
      ResultExplorer.open(_resultRunId);
    });
    DOM.on(resultCard, 'change', (e) => {
      const toggle = e.target.closest('[data-review-toggle]');
      if (!toggle) return;
      e.stopPropagation();
      _toggleStrategyRerunReviewChange(toggle.dataset.reviewToggle || '', Boolean(toggle.checked));
    });
    DOM.on(resultCard, 'keydown', (e) => {
      if (!_resultRunId) return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        ResultExplorer.open(_resultRunId);
      }
    });
    DOM.on(quickParamsBody, 'click', _onQuickParamsAction);
    DOM.on(quickParamsBody, 'input', _onQuickParamsInput);
    DOM.on(quickParamsBody, 'change', _onQuickParamsInput);
    DOM.on(quickParamsBody, 'focusout', _onQuickParamsCommit);

    _setupPickerEvents('bt-pairs-list', 'bt-pairs-count', 'bt-pairs-search', 'bt-pairs-all', 'bt-pairs-none', 'bt-pairs-favs');
    _wireSaveEvents();
    _wirePreviewEvents();
    _wireConfigSyncEvents();

    const dlFormBtn = DOM.$('#bt-dl-form-btn', _el);
    DOM.on(dlFormBtn, 'click', _onDownload);

    if (!_intelligenceEventBound) {
      _intelligenceEventBound = true;
      window.addEventListener('strategy-intelligence:rerun', _onStrategyIntelligenceEvent);
    }

    _syncRunState();
  }

  async function _syncRunState() {
    try {
      const data = await API.getRuns();
      const runs = _sortRunsNewest(data.runs || []);
      await _restoreLatestState(runs);
    } catch {}
  }

  async function _onDeleteRun() {
    if (!_resultRunId) { Toast.warning('No loaded result to delete.'); return; }
    await _deleteRun(_resultRunId);
  }

  async function _deleteRun(runId) {
    if (!runId) return;
    const confirmed = await Modal.confirm({
      title: 'Delete Run',
      message: `Delete run ${runId}? This cannot be undone.`,
      confirmLabel: 'Delete Run',
    });
    if (!confirmed) return;
    try {
      await API.deleteRun(runId);
      Toast.success(`Run deleted.`);
      if (runId === _activeRunId) {
        _activeRunId = null;
        _stopPoll();
        _setRunning(false);
        Auth.setRunning(false);
        DOM.hide(DOM.$('#bt-status-card', _el));
        AppState.set('stream', 'Run deleted.');
      }
      if (runId === _resultRunId) {
        _clearLoadedResult();
      }
      _syncRunState();
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

      const uniq = (arr) => [...new Set(arr)];
      const favLocal   = local.filter(p => favs.has(p));
      const favConfig  = config.filter(p => favs.has(p));
      const favPopular = popular.filter(p => favs.has(p));
      const allFavs    = uniq([...favLocal, ...favConfig, ...favPopular]);

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
          hint.style.color = 'var(--green)';
        } else {
          hint.textContent = 'No local data — select pairs then use Download Data';
          hint.style.color = 'var(--amber)';
        }
      }

      _refreshCommandPreview();
    } catch {
      listEl.innerHTML = '<div class="pairs-picker__empty">Failed to load pairs</div>';
    }
  }

  function _clearLoadedResult() {
    _resultRunId = null;
    _loadedResult = null;
    _strategyRerunStarting = false;
    _strategyRerunPhase = 'idle';
    _strategyRerunReview = _createStrategyRerunReviewState();
    DOM.hide(DOM.$('#bt-results-card', _el));
    _resetQuickParamsState();
    _syncIntelligenceRerunUiState();
  }

  function _resetQuickParamsState() {
    _quickParamsState = _createQuickParamsState();
    _renderQuickParams();
  }

  function _resolveRunStrategyName(meta = {}) {
    return meta.strategy_class || meta.base_strategy || meta.strategy || null;
  }

  function _resolveRunStrategyLabel(meta = {}) {
    const strategyName = _resolveRunStrategyName(meta);
    return meta.strategy || strategyName || 'Unknown strategy';
  }

  function _isDefaultStrategyPath(strategyPath) {
    if (!strategyPath) return true;
    return /[\\/]user_data[\\/]strategies[\\/]?$/i.test(String(strategyPath));
  }

  function _quickParamsMode() {
    return _quickParamsState.mode || 'editable';
  }

  function _quickParamsSummaryMetaText() {
    const mode = _quickParamsMode();
    if (mode === 'rerun-only') {
      return 'This run uses an external strategy workspace. Run Again will preserve that context.';
    }
    if (mode === 'unavailable') {
      return 'Strategy parameters are unavailable for this run.';
    }
    return 'Seeded from the loaded run first, then saved strategy values, then defaults.';
  }

  function _cloneJson(value) {
    return JSON.parse(JSON.stringify(value ?? {}));
  }

  function _stableStringify(value) {
    if (Array.isArray(value)) {
      return `[${value.map((item) => _stableStringify(item)).join(',')}]`;
    }
    if (value && typeof value === 'object') {
      return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${_stableStringify(value[key])}`).join(',')}}`;
    }
    return JSON.stringify(value);
  }

  function _strategyParamSetsEqual(a, b) {
    return _stableStringify(a || {}) === _stableStringify(b || {});
  }

  function _strategyRerunSelectedChanges() {
    return (_strategyRerunReview.autoChanges || []).filter((item) => item && item.selected);
  }

  function _strategyRerunItemLabel(item) {
    return item?.title || item?.label || item?.name || 'change';
  }

  function _strategyRerunAppliedChanges() {
    return _strategyRerunSelectedChanges().filter((item) => {
      return !_quickValuesEqual(
        _quickParamsState.currentValues?.[item.name],
        _strategyRerunReview.baselineParams?.[item.name],
      );
    }).map(_strategyRerunItemLabel);
  }

  function _strategyRerunSkippedChanges() {
    return (_strategyRerunReview.autoChanges || []).filter((item) => {
      if (!item) return false;
      if (!item.available) return true;
      if (!item.selected) return true;
      return _quickValuesEqual(
        _quickParamsState.currentValues?.[item.name],
        _strategyRerunReview.baselineParams?.[item.name],
      );
    }).map(_strategyRerunItemLabel);
  }

  function _strategyRerunFinalParams() {
    if (_quickHasParams()) return _cloneJson(_quickParamsState.currentValues);
    return _cloneJson(_loadedResult?.meta?.strategy_params || {});
  }

  function _strategyRerunContextOnly() {
    return _strategyRerunAppliedChanges().length === 0;
  }

  function _strategyRerunValidation() {
    const meta = _loadedResult?.meta || {};
    const strategyName = _quickParamsState.strategyName || _resolveRunStrategyName(meta);
    if (!_strategyRerunReview.active) {
      return { ok: false, message: 'No rerun review is active.', identical: false, contextOnly: false };
    }
    if (_activeRunId) {
      return { ok: false, message: 'A backtest is already running.', identical: false, contextOnly: false };
    }
    if (_quickParamsState.loading) {
      return { ok: false, message: 'Strategy parameters are still loading.', identical: false, contextOnly: false };
    }
    if (!strategyName) {
      return { ok: false, message: 'Target strategy is unavailable for rerun.', identical: false, contextOnly: false };
    }
    const finalParams = _strategyRerunFinalParams();
    const baselineParams = _strategyRerunReview.baselineParams || {};
    const contextOnly = _strategyRerunContextOnly();
    const identical = _strategyParamSetsEqual(finalParams, baselineParams);
    if (identical && !contextOnly) {
      return { ok: false, message: 'The reviewed rerun would be identical to the parent run.', identical: true, contextOnly };
    }
    return {
      ok: true,
      message: contextOnly
        ? 'Context-only rerun. No parameter changes will be applied automatically.'
        : 'Review is valid. Run Improved Backtest will use the selected changes.',
      identical,
      contextOnly,
    };
  }

  function _quickHasParams() {
    return Array.isArray(_quickParamsState.parameters) && _quickParamsState.parameters.length > 0;
  }

  function _quickValuesEqual(a, b) {
    return a === b;
  }

  function _quickDirtyCount() {
    if (!_quickHasParams()) return 0;
    return _quickParamsState.parameters.reduce((count, param) => {
      const current = _quickParamsState.currentValues[param.name];
      const seed = _quickParamsState.seedValues[param.name];
      return count + (_quickValuesEqual(current, seed) ? 0 : 1);
    }, 0);
  }

  function _findQuickParam(name) {
    return _quickParamsState.parameters.find((param) => param.name === name) || null;
  }

  function _coerceQuickParamValue(param, rawValue) {
    if (!param) return rawValue;

    if (param.type === 'bool') {
      return Boolean(rawValue);
    }

    if (rawValue == null || rawValue === '') {
      return param.default ?? null;
    }

    if (param.type === 'int') {
      const parsed = Number.parseInt(rawValue, 10);
      if (!Number.isFinite(parsed)) return param.default ?? param.low ?? 0;
      return parsed;
    }

    if (param.type === 'decimal') {
      const parsed = Number.parseFloat(rawValue);
      if (!Number.isFinite(parsed)) return param.default ?? param.low ?? 0;
      return parsed;
    }

    if (param.type === 'categorical') {
      const match = (param.options || []).find((option) => String(option) === String(rawValue));
      return match !== undefined ? match : rawValue;
    }

    return rawValue;
  }

  function _seedQuickParamValue(param, meta = {}) {
    const runParams = meta.strategy_params || {};
    if (Object.prototype.hasOwnProperty.call(runParams, param.name)) {
      return _coerceQuickParamValue(param, runParams[param.name]);
    }
    if (Object.prototype.hasOwnProperty.call(param, 'value')) {
      return _coerceQuickParamValue(param, param.value);
    }
    return _coerceQuickParamValue(param, param.default);
  }

  function _quickParamStep(param) {
    if (param.type !== 'decimal') return null;
    const decimals = Number.isInteger(param.decimals) ? Math.max(param.decimals, 0) : 3;
    if (decimals === 0) return '1';
    return (1 / (10 ** decimals)).toFixed(decimals);
  }

  function _quickParamLabel(name) {
    return String(name || '')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function _quickParamDescription(param) {
    if (!param) return '';
    const range = _quickParamRangeText(param);
    if (param.type === 'int') return `Integer${range ? ` · ${range}` : ''}`;
    if (param.type === 'decimal') return `Decimal${range ? ` · ${range}` : ''} · ${param.decimals ?? 3} dp`;
    if (param.type === 'categorical') return `Categorical · ${param.options?.length || 0} options`;
    if (param.type === 'bool') return 'Boolean';
    return param.type || 'Parameter';
  }

  function _quickParamRangeText(param) {
    if (!param) return '';
    if (param.low != null && param.high != null) return `${param.low} to ${param.high}`;
    if (param.low != null) return `From ${param.low}`;
    if (param.high != null) return `Up to ${param.high}`;
    return '';
  }

  function _quickGroupEditedCount(params) {
    return params.reduce((count, param) => {
      return count + (_quickValuesEqual(_quickParamsState.currentValues[param.name], _quickParamsState.seedValues[param.name]) ? 0 : 1);
    }, 0);
  }

  function _quickParamMetaBadges(param) {
    const tags = [];
    const range = _quickParamRangeText(param);
    if (param.type === 'int') {
      tags.push('Integer');
      if (range) tags.push(range);
    } else if (param.type === 'decimal') {
      tags.push('Decimal');
      if (range) tags.push(range);
      if (param.decimals != null) tags.push(`${param.decimals} dp`);
    } else if (param.type === 'categorical') {
      tags.push('Categorical');
      if (Array.isArray(param.options)) tags.push(`${param.options.length} options`);
    } else if (param.type === 'bool') {
      tags.push('Boolean');
    } else if (param.type) {
      tags.push(param.type);
    }

    return `
      <div class="quick-params__field-tags">
        ${tags.map((tag) => `<span class="quick-params__field-tag">${_esc(tag)}</span>`).join('')}
      </div>
    `;
  }

  function _groupQuickParams(parameters) {
    const groups = new Map();
    const sorted = [...parameters].sort((a, b) => {
      const aSpace = String(a.space || '');
      const bSpace = String(b.space || '');
      const aRank = _QUICK_PARAM_GROUP_ORDER.indexOf(aSpace);
      const bRank = _QUICK_PARAM_GROUP_ORDER.indexOf(bSpace);
      const normalizedARank = aRank === -1 ? Number.MAX_SAFE_INTEGER : aRank;
      const normalizedBRank = bRank === -1 ? Number.MAX_SAFE_INTEGER : bRank;
      if (normalizedARank !== normalizedBRank) return normalizedARank - normalizedBRank;
      if (aSpace !== bSpace) return aSpace.localeCompare(bSpace);
      return String(a.name || '').localeCompare(String(b.name || ''));
    });

    sorted.forEach((param) => {
      const space = param.space || 'other';
      if (!groups.has(space)) groups.set(space, []);
      groups.get(space).push(param);
    });

    return [...groups.entries()];
  }

  function _quickGroupLabel(space) {
    if (!space) return 'Other';
    return String(space).charAt(0).toUpperCase() + String(space).slice(1);
  }

  function _quickParamControl(param) {
    const inputId = `bt-qp-${param.name}`;
    const currentValue = _quickParamsState.currentValues[param.name];
    if (param.type === 'bool') {
      return `
        <label class="checkbox-label quick-params__checkbox" for="${_esc(inputId)}">
          <input
            id="${_esc(inputId)}"
            type="checkbox"
            data-quick-param="${_esc(param.name)}"
            ${currentValue ? 'checked' : ''}
          >
          <span>Enabled</span>
        </label>
      `;
    }

    if (param.type === 'categorical') {
      const options = (param.options || []).map((option) => `
        <option value="${_esc(option)}"${_quickValuesEqual(currentValue, option) ? ' selected' : ''}>${_esc(option)}</option>
      `).join('');
      return `
        <select
          class="form-select quick-params__control"
          id="${_esc(inputId)}"
          data-quick-param="${_esc(param.name)}"
        >
          ${options}
        </select>
      `;
    }

    const min = param.low != null ? ` min="${_esc(param.low)}"` : '';
    const max = param.high != null ? ` max="${_esc(param.high)}"` : '';
    const step = param.type === 'decimal' ? ` step="${_esc(_quickParamStep(param))}"` : ' step="1"';
    return `
      <input
        class="form-input form-input--sm quick-params__control"
        id="${_esc(inputId)}"
        type="number"
        value="${_esc(currentValue)}"
        data-quick-param="${_esc(param.name)}"${min}${max}${step}
      >
    `;
  }

  function _quickParamsNotice(message, tone = '') {
    const toneClass = tone ? ` quick-params__notice--${tone}` : '';
    return `<div class="quick-params__notice${toneClass}">${_esc(message)}</div>`;
  }

  function _setQuickParamControlValue(control, param, value) {
    if (!control || !param) return;
    if (param.type === 'bool') {
      control.checked = Boolean(value);
      return;
    }
    control.value = value == null ? '' : String(value);
  }

  function _normalizeQuickParamTarget(target) {
    const name = target?.dataset?.quickParam;
    const param = _findQuickParam(name);
    if (!param) return null;
    const rawValue = target.type === 'checkbox' ? target.checked : target.value;
    const normalizedValue = _coerceQuickParamValue(param, rawValue);
    _quickParamsState.currentValues[name] = normalizedValue;
    _setQuickParamControlValue(target, param, normalizedValue);
    return normalizedValue;
  }

  function _normalizeAllQuickParamControls() {
    if (!_quickHasParams()) return;
    _quickParamsState.parameters.forEach((param) => {
      const control = DOM.$(`[data-quick-param="${param.name}"]`, _el);
      if (!control) return;
      _normalizeQuickParamTarget(control);
    });
    _syncQuickParamsUiState();
  }

  function _quickParamsSummaryHtml() {
    const meta = _quickParamsState.meta || {};
    const mode = _quickParamsMode();
    const strategyName = _quickParamsState.strategyName || _resolveRunStrategyName(meta) || 'Unknown strategy';
    const strategyLabel = _quickParamsState.strategyLabel || _resolveRunStrategyLabel(meta);
    const runId = _quickParamsState.runId || _resultRunId || '—';
    const totalParams = _quickParamsState.parameters.length;
    const dirtyCount = _quickDirtyCount();
    let dirtyLabel = dirtyCount ? `${dirtyCount} unsaved change${dirtyCount === 1 ? '' : 's'}` : 'Clean';
    let dirtyTone = dirtyCount ? 'badge--amber' : 'badge--green';
    if (mode === 'rerun-only') {
      dirtyLabel = 'Rerun Only';
      dirtyTone = 'badge--amber';
    } else if (mode === 'unavailable') {
      dirtyLabel = 'Unavailable';
      dirtyTone = 'badge--red';
    }
    const subtitle = strategyLabel !== strategyName
      ? `Run ${runId} · ${strategyLabel} (${strategyName})`
      : `Run ${runId} · ${strategyName}`;

    return `
      <div class="quick-params__toolbar">
        <div class="quick-params__summary">
          <div class="quick-params__title">${_esc(subtitle)}</div>
          <div class="quick-params__meta">${_esc(_quickParamsSummaryMetaText())}</div>
          <div class="quick-params__summary-stats">
            ${totalParams ? `<span class="quick-params__summary-chip">${_esc(`${totalParams} parameters`)}</span>` : ''}
            ${mode === 'editable' ? '<span class="quick-params__summary-chip">Edit, then save and run</span>' : ''}
          </div>
        </div>
        <div class="quick-params__toolbar-right">
          <span class="badge ${dirtyTone}" id="bt-quick-dirty-badge">${_esc(dirtyLabel)}</span>
          <div class="quick-params__actions">
            <button type="button" class="btn btn--primary btn--sm" data-quick-action="save-run">Save and Run</button>
            <button type="button" class="btn btn--secondary btn--sm" data-quick-action="run">Run Again</button>
            <button type="button" class="btn btn--ghost btn--sm" data-quick-action="save">Save to Strategy</button>
            <button type="button" class="btn btn--ghost btn--sm" data-quick-action="reset">Reset</button>
          </div>
        </div>
      </div>
      <div class="quick-params__state" id="bt-quick-params-state"></div>
    `;
  }

  function _renderQuickParams() {
    const card = DOM.$('#bt-quick-params-card', _el);
    const body = DOM.$('#bt-quick-params-body', _el);
    if (!card || !body) return;

    if (!_resultRunId || !_loadedResult || _loadedResult.status !== 'completed') {
      DOM.hide(card);
      DOM.empty(body);
      return;
    }

    DOM.show(card);

    if (_quickParamsMode() === 'rerun-only') {
      const message = _quickParamsState.notice || 'Run Again will preserve the loaded strategy_path. Save to Strategy is only available for strategies in user_data/strategies.';
      body.innerHTML = `
        ${_quickParamsSummaryHtml()}
        ${_quickParamsNotice(message, 'amber')}
      `;
      _syncQuickParamsUiState();
      return;
    }

    if (_quickParamsMode() === 'unavailable') {
      const message = _quickParamsState.notice || _quickParamsState.error || 'Strategy parameters are unavailable for this run.';
      body.innerHTML = `
        ${_quickParamsSummaryHtml()}
        ${_quickParamsNotice(message, 'red')}
      `;
      _syncQuickParamsUiState();
      return;
    }

    if (_quickParamsState.loading) {
      body.innerHTML = `
        ${_quickParamsSummaryHtml()}
        ${_quickParamsNotice('Loading strategy parameters…')}
      `;
      _syncQuickParamsUiState();
      return;
    }

    if (_quickParamsState.error) {
      body.innerHTML = `
        ${_quickParamsSummaryHtml()}
        ${_quickParamsNotice(_quickParamsState.error, 'red')}
      `;
      _syncQuickParamsUiState();
      return;
    }

    if (!_quickHasParams()) {
      const message = _quickParamsState.empty || 'No detected strategy parameters are available for this run.';
      body.innerHTML = `
        ${_quickParamsSummaryHtml()}
        ${_quickParamsNotice(message)}
      `;
      _syncQuickParamsUiState();
      return;
    }

    const groupsHtml = _groupQuickParams(_quickParamsState.parameters).map(([space, params]) => `
      <section class="quick-params__group">
        <div class="quick-params__group-header">
          <h3 class="quick-params__group-title">${_esc(_quickGroupLabel(space))}</h3>
          <div class="quick-params__group-meta">
            <span class="quick-params__group-count">${_esc(`${params.length} params`)}</span>
            ${_quickGroupEditedCount(params) ? `<span class="quick-params__group-edited">${_esc(`${_quickGroupEditedCount(params)} edited`)}</span>` : ''}
          </div>
        </div>
        <div class="quick-params__grid">
          ${params.map((param) => {
            const dirty = !_quickValuesEqual(_quickParamsState.currentValues[param.name], _quickParamsState.seedValues[param.name]);
            return `
              <div class="quick-params__field${dirty ? ' quick-params__field--dirty' : ''}" data-quick-field="${_esc(param.name)}">
                <div class="quick-params__field-head">
                  <div class="quick-params__field-title-wrap">
                    <label class="quick-params__field-label" for="${_esc(`bt-qp-${param.name}`)}">${_esc(_quickParamLabel(param.name))}</label>
                    ${_quickParamMetaBadges(param)}
                  </div>
                  <span class="quick-params__field-badge"${dirty ? '' : ' style="display:none"'}>Edited</span>
                </div>
                ${_quickParamControl(param)}
              </div>
            `;
          }).join('')}
        </div>
      </section>
    `).join('');

    body.innerHTML = `
      ${_quickParamsSummaryHtml()}
      <div class="quick-params__groups">${groupsHtml}</div>
    `;
    _syncQuickParamsUiState();
  }

  function _syncQuickParamsUiState() {
    const body = DOM.$('#bt-quick-params-body', _el);
    if (!body) return;

    const mode = _quickParamsMode();
    const isEditable = mode === 'editable';
    const dirtyCount = _quickDirtyCount();
    const dirtyBadge = DOM.$('#bt-quick-dirty-badge', body);
    const stateEl = DOM.$('#bt-quick-params-state', body);
    const hasParams = _quickHasParams();
    const hasRunContext = Boolean(_loadedResult?.meta && (_quickParamsState.strategyName || _resolveRunStrategyName(_loadedResult.meta)));
    const isRunning = Boolean(_activeRunId);
    const disableRun = !hasRunContext || _quickParamsState.loading || _quickParamsState.saving || isRunning;
    const disableSaveRun = !isEditable || !hasParams || _quickParamsState.loading || _quickParamsState.saving || isRunning || dirtyCount === 0;
    const disableSave = !isEditable || !hasParams || _quickParamsState.loading || _quickParamsState.saving || dirtyCount === 0;
    const disableReset = !isEditable || !hasParams || _quickParamsState.loading || _quickParamsState.saving || dirtyCount === 0;

    body.querySelectorAll('[data-quick-field]').forEach((fieldEl) => {
      const name = fieldEl.dataset.quickField;
      const dirty = !_quickValuesEqual(_quickParamsState.currentValues[name], _quickParamsState.seedValues[name]);
      fieldEl.classList.toggle('quick-params__field--dirty', dirty);
      const badge = fieldEl.querySelector('.quick-params__field-badge');
      if (badge) badge.style.display = dirty ? '' : 'none';
    });

    const saveRunBtn = body.querySelector('[data-quick-action="save-run"]');
    const runBtn = body.querySelector('[data-quick-action="run"]');
    const saveBtn = body.querySelector('[data-quick-action="save"]');
    const resetBtn = body.querySelector('[data-quick-action="reset"]');
    if (saveRunBtn) {
      saveRunBtn.disabled = disableSaveRun;
      if (mode === 'rerun-only') {
        saveRunBtn.title = 'Save and Run is unavailable for external strategy workspaces.';
      } else if (mode === 'unavailable') {
        saveRunBtn.title = 'Strategy parameters are unavailable for this run.';
      } else if (dirtyCount === 0) {
        saveRunBtn.title = 'Change a parameter first, then Save and Run.';
      } else if (isRunning) {
        saveRunBtn.title = 'Another backtest is running right now.';
      } else {
        saveRunBtn.title = '';
      }
    }
    if (runBtn) {
      runBtn.disabled = disableRun;
      runBtn.title = isRunning ? 'Run Again is disabled while another backtest is active.' : '';
    }
    if (saveBtn) {
      saveBtn.disabled = disableSave;
      saveBtn.title = mode === 'rerun-only'
        ? 'Save to Strategy is only available for strategies in user_data/strategies.'
        : '';
    }
    if (resetBtn) {
      resetBtn.disabled = disableReset;
      resetBtn.title = mode === 'rerun-only'
        ? 'Reset is unavailable because this run is rerun-only.'
        : '';
    }

    body.querySelectorAll('[data-quick-param]').forEach((control) => {
      control.disabled = _quickParamsState.loading || _quickParamsState.saving || !isEditable;
    });

    if (dirtyBadge) {
      let badgeTone = dirtyCount ? 'badge--amber' : 'badge--green';
      let badgeText = dirtyCount ? `${dirtyCount} unsaved change${dirtyCount === 1 ? '' : 's'}` : 'Clean';
      if (mode === 'rerun-only') {
        badgeTone = 'badge--amber';
        badgeText = 'Rerun Only';
      } else if (mode === 'unavailable') {
        badgeTone = 'badge--red';
        badgeText = 'Unavailable';
      }
      dirtyBadge.className = `badge ${badgeTone}`;
      dirtyBadge.textContent = badgeText;
    }

    if (stateEl) {
      stateEl.className = 'quick-params__state';
      let stateText = '';
      if (_quickParamsState.loading) {
        stateText = 'Loading strategy parameters…';
      } else if (_quickParamsState.saving) {
        stateText = 'Saving strategy parameters…';
      } else if (isRunning) {
        stateText = `Backtest ${_activeRunId} is running. Run Again is disabled until it completes.`;
      } else if (isEditable && hasParams && dirtyCount) {
        stateText = 'Edited values are ready. Save and Run will persist them first, then start the same run context.';
        stateEl.classList.add('text-amber');
      } else if (isEditable && hasParams) {
        stateText = 'Current values match the loaded baseline. Use Run Again for a temporary rerun.';
      }
      stateEl.textContent = stateText;
      stateEl.style.display = stateText ? '' : 'none';
    }
  }

  async function _ensureQuickParamsForRun(runData) {
    const runId = runData?.run_id;
    const meta = runData?.meta || {};
    const strategyName = _resolveRunStrategyName(meta);
    const strategyLabel = _resolveRunStrategyLabel(meta);
    const strategyPath = meta.strategy_path || null;

    if (!runId) {
      _resetQuickParamsState();
      return;
    }

    if (
      _quickParamsState.runId === runId &&
      _quickParamsState.strategyName === strategyName &&
      (_quickParamsState.loading || _quickHasParams() || _quickParamsState.error || _quickParamsState.empty || _quickParamsState.notice)
    ) {
      return;
    }

    _quickParamsState = {
      ..._createQuickParamsState(),
      runId,
      strategyName,
      strategyLabel,
      strategyPath,
      meta,
      mode: 'editable',
      loading: false,
    };

    if (!strategyName) {
      _quickParamsState.mode = 'unavailable';
      _quickParamsState.notice = 'Strategy parameters are unavailable for this run because the strategy class could not be resolved.';
      _renderQuickParams();
      return;
    }

    if (!_isDefaultStrategyPath(strategyPath)) {
      _quickParamsState.mode = 'rerun-only';
      _quickParamsState.notice = 'This run used an external strategy workspace. Run Again will preserve that strategy_path, but Save to Strategy is only available for strategies in user_data/strategies.';
      _renderQuickParams();
      return;
    }

    _quickParamsState.loading = true;
    _renderQuickParams();

    try {
      const response = await API.getStrategyParams(strategyName);
      if (_quickParamsState.runId !== runId) return;

      const parameters = response.parameters || [];
      const seedValues = {};
      parameters.forEach((param) => {
        seedValues[param.name] = _seedQuickParamValue(param, meta);
      });

      _quickParamsState = {
        ..._quickParamsState,
        loading: false,
        mode: 'editable',
        parameters,
        seedValues,
        currentValues: { ...seedValues },
        error: '',
        empty: parameters.length ? '' : `No detected strategy parameters were found for ${strategyName}.`,
        notice: '',
      };
    } catch (err) {
      if (_quickParamsState.runId !== runId) return;
      _quickParamsState = {
        ..._quickParamsState,
        loading: false,
        mode: 'editable',
        parameters: [],
        seedValues: {},
        currentValues: {},
        error: `Strategy parameters are unavailable for ${strategyName}. ${err.message}`,
        empty: '',
        notice: '',
      };
    }

    _renderQuickParams();
  }

  function _onQuickParamsInput(event) {
    const target = event.target?.closest?.('[data-quick-param]');
    if (!target || !_quickHasParams()) return;

    const name = target.dataset.quickParam;
    const param = _findQuickParam(name);
    if (!param) return;

    if (event.type === 'change') {
      _normalizeQuickParamTarget(target);
      _syncQuickParamsUiState();
      _updateStrategyRerunReview();
      return;
    }

    const rawValue = target.type === 'checkbox' ? target.checked : target.value;
    _quickParamsState.currentValues[name] = _coerceQuickParamValue(param, rawValue);
    _syncQuickParamsUiState();
    _updateStrategyRerunReview();
  }

  function _onQuickParamsCommit(event) {
    const target = event.target?.closest?.('[data-quick-param]');
    if (!target || !_quickHasParams()) return;
    _normalizeQuickParamTarget(target);
    _syncQuickParamsUiState();
    _updateStrategyRerunReview();
  }

  async function _onQuickParamsAction(event) {
    const button = event.target.closest('[data-quick-action]');
    if (!button) return;

    if (button.dataset.quickAction === 'save-run') {
      await _saveAndRunQuickParams();
      return;
    }

    if (button.dataset.quickAction === 'run') {
      await _runQuickParamsBacktest();
      return;
    }

    if (button.dataset.quickAction === 'save') {
      await _saveQuickParams();
      return;
    }

    if (button.dataset.quickAction === 'reset') {
      _quickParamsState.currentValues = { ..._quickParamsState.seedValues };
      _renderQuickParams();
    }
  }

  async function _saveAndRunQuickParams() {
    if (!_quickHasParams() || !_quickDirtyCount()) return;
    const saved = await _saveQuickParams({ showToast: false });
    if (!saved) return;
    await _runQuickParamsBacktest();
  }

  function _ensureStrategyOption(value, label) {
    const select = DOM.$('#bt-strategy', _el);
    if (!select || !value) return;
    const existing = [...select.options].find((option) => option.value === value);
    if (existing) {
      existing.textContent = label || existing.textContent;
      select.value = value;
      return;
    }

    const option = document.createElement('option');
    option.value = value;
    option.textContent = label || value;
    option.dataset.temporary = 'true';
    select.appendChild(option);
    select.value = value;
  }

  async function _syncFormToRunContext(meta = {}, strategyName = null, strategyLabel = null) {
    const strategyValue = strategyName || _resolveRunStrategyName(meta) || '';
    const displayLabel = strategyLabel || _resolveRunStrategyLabel(meta) || strategyValue;
    _ensureStrategyOption(strategyValue, displayLabel);

    const setValue = (selector, value) => {
      const el = DOM.$(selector, _el);
      if (el && value != null) el.value = value;
    };

    setValue('#bt-exchange', meta.exchange || 'binance');
    setValue('#bt-timeframe', meta.timeframe || '5m');
    setValue('#bt-timerange', meta.timerange || '');
    setValue('#bt-wallet', meta.dry_run_wallet);
    setValue('#bt-max-trades', meta.max_open_trades);
    setValue('#bt-stake', meta.stake_amount);

    await _loadPairs(meta.exchange || 'binance', meta.pairs || []);
    _saveForm();
    _refreshCommandPreview();
  }

  async function _runQuickParamsBacktest(options = {}) {
    if (!_loadedResult?.meta) {
      Toast.warning('No completed run is loaded.');
      return;
    }
    const fromIntelligence = options.improvementSource === 'strategy_intelligence';
    if (_activeRunId) {
      if (fromIntelligence) {
        Toast.warning('A backtest is already running. Wait for it to finish before using Improve & Run.');
      }
      return;
    }
    if (fromIntelligence && _strategyRerunStarting) {
      return;
    }
    if (fromIntelligence) {
      _strategyRerunStarting = true;
      _setStrategyRerunPhase('starting');
    }

    try {
      _normalizeAllQuickParamControls();

      const meta = _loadedResult.meta;
      const strategyName = _quickParamsState.strategyName || _resolveRunStrategyName(meta);
      if (!strategyName) {
        Toast.error('Cannot rerun this result because the strategy class is unavailable.');
        return;
      }

      await _syncFormToRunContext(meta, strategyName, _quickParamsState.strategyLabel);

      const body = {
        strategy: strategyName,
        strategy_label: meta.strategy && meta.strategy !== strategyName ? meta.strategy : null,
        strategy_path: meta.strategy_path || null,
        pairs: Array.isArray(meta.pairs) ? [...meta.pairs] : [],
        timeframe: meta.timeframe || '5m',
        timerange: meta.timerange || null,
        exchange: meta.exchange || 'binance',
        parent_run_id: _resultRunId || null,
        improvement_source: options.improvementSource || null,
        improvement_items: Array.isArray(options.improvementItems) ? options.improvementItems : [],
        improvement_applied: Array.isArray(options.improvementApplied) ? options.improvementApplied : [],
        improvement_skipped: Array.isArray(options.improvementSkipped) ? options.improvementSkipped : [],
        improvement_brief: options.improvementBrief || null,
        strategy_params: _quickHasParams()
          ? { ..._quickParamsState.currentValues }
          : { ...(meta.strategy_params || {}) },
      };

      if (options.improvementSource === 'strategy_intelligence' && !options.contextOnly) {
        const baselineParams = _strategyRerunReview.baselineParams || (meta.strategy_params || {});
        if (_strategyParamSetsEqual(body.strategy_params, baselineParams)) {
          Toast.warning('The reviewed rerun would be identical to the parent run.');
          return;
        }
      }

      try {
        const hasCoverage = await _ensureCoverageWithAutoDownload(body);
        if (!hasCoverage) return;
      } catch (err) {
        Toast.error('Failed to validate/download pair data: ' + err.message);
        return;
      }

      _clearLoadedResult();
      _setRunning(true);
      try {
        const res = await API.startBacktest(body);
        _activeRunId = res.run_id;
        AppState.set('stream', `Backtest started: ${_activeRunId}`);
        Auth.setRunning(true);
        _startPoll(_activeRunId);
        Toast.success(options.toastMessage || 'Backtest started from the loaded result context.');
      } catch (err) {
        _setRunning(false);
        Toast.error('Failed to start backtest: ' + err.message);
      }
    } finally {
      if (fromIntelligence) {
        _strategyRerunStarting = false;
        _setStrategyRerunPhase('idle');
      }
    }
  }

  async function _saveQuickParams(options = {}) {
    const showToast = options.showToast !== false;
    if (!_quickHasParams()) return false;
    const strategyName = _quickParamsState.strategyName;
    if (!strategyName) {
      Toast.error('Cannot save parameters because the strategy class is unavailable.');
      return false;
    }

    _normalizeAllQuickParamControls();

    _quickParamsState.saving = true;
    _syncQuickParamsUiState();
    try {
      await API.saveStrategyParams(strategyName, { ..._quickParamsState.currentValues });
      _quickParamsState.seedValues = { ..._quickParamsState.currentValues };
      _quickParamsState.saving = false;
      _syncQuickParamsUiState();
      if (showToast) Toast.success(`Saved parameters to ${strategyName}.json.`);
      return true;
    } catch (err) {
      _quickParamsState.saving = false;
      _syncQuickParamsUiState();
      Toast.error('Failed to save strategy parameters: ' + err.message);
      return false;
    }
  }

  /* ── Download Data ── */
  let _dlPollTimer = null;

  async function _onDownload() {
    const selected = _getSelectedPairs('bt-pairs-list');

    if (!selected.length) { Toast.warning('Select at least one pair to download.'); return; }
    const defaultCmd = _buildDownloadCommand();
    const commandOverride = await _editCommandBeforeRun(defaultCmd);
    if (!commandOverride) return;

    const formBtn = DOM.$('#bt-dl-form-btn', _el);
    const logEl   = DOM.$('#bt-dl-logs', _el);
    const logWrap = DOM.$('#bt-dl-log-wrap', _el);

    if (formBtn) formBtn.disabled = true;
    if (logWrap) DOM.show(logWrap);

    try {
      const tf = DOM.$('#bt-timeframe', _el)?.value || '5m';
      const timerange = DOM.$('#bt-timerange', _el)?.value || null;
      const expandedTimerange = _expandDownloadTimerange(timerange);
      const res = await API.downloadData({
        pairs: selected,
        timeframe: tf,
        timerange: expandedTimerange,
        command_override: commandOverride,
      });
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

  async function _validateSelectedPairData({ pairs, timeframe, exchange, timerange }) {
    const effectiveTimerange = timerange ?? (DOM.$('#bt-timerange', _el)?.value || null);
    const data = await API.dataCoverage({ pairs, timeframe, exchange, timerange: effectiveTimerange });
    const missingPairs = data.missing_pairs || (data.coverage || [])
      .filter(item => !item.available || ((item.missing_days || []).length > 0) || ((item.incomplete_days || []).length > 0))
      .map(item => item.pair);

    return {
      ok: !missingPairs.length,
      missingPairs,
      details: (data.issue_details || []).slice(0, 3).join(' | '),
    };
  }

  async function _waitForDownloadCompletion(jobId) {
    const maxChecks = 480;
    for (let i = 0; i < maxChecks; i++) {
      const data = await API.getDownload(jobId);
      if (data.status === 'completed') return data;
      if (data.status === 'failed') {
        const tail = (data.logs || []).slice(-3).join(' | ');
        throw new Error(tail || 'Download job failed.');
      }
      await _sleep(2500);
    }
    throw new Error('Download timed out.');
  }

  function _expandDownloadTimerange(timerange) {
    const value = String(timerange || '').trim();
    const match = value.match(/^(\d{8})-(\d{8})$/);
    if (!match) return timerange || null;

    const startStr = match[1];
    const endStr = match[2];
    const start = Date.parse(`${startStr.slice(0, 4)}-${startStr.slice(4, 6)}-${startStr.slice(6, 8)}T00:00:00Z`);
    const end = Date.parse(`${endStr.slice(0, 4)}-${endStr.slice(4, 6)}-${endStr.slice(6, 8)}T00:00:00Z`);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) {
      return timerange || null;
    }

    const BUFFER_DAYS = 2;
    const bufferedStart = new Date(start - (BUFFER_DAYS * 86400000));
    const y = bufferedStart.getUTCFullYear();
    const m = String(bufferedStart.getUTCMonth() + 1).padStart(2, '0');
    const d = String(bufferedStart.getUTCDate()).padStart(2, '0');
    return `${y}${m}${d}-${endStr}`;
  }

  async function _ensureCoverageWithAutoDownload({ pairs, timeframe, exchange, timerange }) {
    let coverage = await _validateSelectedPairData({ pairs, timeframe, exchange, timerange });
    if (coverage.ok) return true;

    const expandedTimerange = _expandDownloadTimerange(timerange);
    Toast.info(`Missing/incomplete data detected for ${coverage.missingPairs.join(', ')}. Auto-downloading now…`);
    const res = await API.downloadData({
      pairs,
      timeframe,
      timerange: expandedTimerange,
    });
    const jobId = res.job_id || res.run_id;
    await _waitForDownloadCompletion(jobId);

    const ex = exchange || (DOM.$('#bt-exchange', _el)?.value || 'binance');
    await _loadPairs(ex);

    coverage = await _validateSelectedPairData({ pairs, timeframe, exchange, timerange });
    if (coverage.ok) {
      Toast.success('Market data auto-downloaded and validated.');
      return true;
    }

    Toast.error(
      `Missing/incomplete local data for: ${coverage.missingPairs.join(', ')}.${coverage.details ? ` ${coverage.details}` : ''}`
    );
    return false;
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
    const commandOverride = await _editCommandBeforeRun(_buildLiveCommand());
    if (!commandOverride) return;
    body.command_override = commandOverride;

    try {
      const hasCoverage = await _ensureCoverageWithAutoDownload(body);
      if (!hasCoverage) return;
    } catch (err) {
      Toast.error('Failed to validate/download pair data: ' + err.message);
      return;
    }

    _clearLoadedResult();
    _setRunning(true);
    try {
      const res = await API.startBacktest(body);
      _activeRunId = res.run_id;
      AppState.set('stream', `Backtest started: ${_activeRunId}`);
      Auth.setRunning(true);
      _startPoll(_activeRunId);
      Toast.success('Backtest started.');
    } catch (err) {
      _setRunning(false);
      Toast.error('Failed to start backtest: ' + err.message);
    }
  }

  function _startPoll(runId) {
    _activeRunId = runId;
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
          _activeRunId = null;
          AppState.set('stream', `Backtest ${data.status}: ${runId}`);
          if (data.status === 'completed') Toast.success('Backtest completed.');
          else Toast.error('Backtest failed.');
          _syncRunState();
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
    const statusRunId = data.run_id || null;
    const belongsToActiveRun = !_activeRunId || !statusRunId || statusRunId === _activeRunId;

    if (data.status === 'completed' && data.results && belongsToActiveRun) {
      DOM.show(resCard);
      _resultRunId = data.run_id || _activeRunId || _resultRunId;
      _loadedResult = data;
      _renderResults(resBody, data.results);
      void _ensureQuickParamsForRun(data);
    } else if (data.status === 'failed' && statusRunId && statusRunId === _activeRunId) {
      _clearLoadedResult();
    }
  }

  function _resultDateMs(value) {
    if (value == null || value === '') return null;
    if (typeof value === 'number') {
      if (value > 1e12) return value;
      if (value > 1e9) return value * 1000;
    }
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function _timerangeDays(timerange) {
    const match = String(timerange || '').match(/^(\d{8})-(\d{8})$/);
    if (!match) return null;
    const start = Date.parse(`${match[1].slice(0, 4)}-${match[1].slice(4, 6)}-${match[1].slice(6, 8)}T00:00:00Z`);
    const end = Date.parse(`${match[2].slice(0, 4)}-${match[2].slice(4, 6)}-${match[2].slice(6, 8)}T00:00:00Z`);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null;
    return Math.max(((end - start) / 86400000) + 1, 1);
  }

  function _deriveBacktestDays(results) {
    const run = results.run_metadata || {};
    const runDays = FMT.toNumber(run.backtest_days ?? run.backtestDays);
    if (runDays && runDays > 0) return runDays;

    const startMs = _resultDateMs(run.backtest_start ?? run.backtestStart ?? run.backtest_start_ts ?? run.backtestStartTs);
    const endMs = _resultDateMs(run.backtest_end ?? run.backtestEnd ?? run.backtest_end_ts ?? run.backtestEndTs);
    if (startMs != null && endMs != null && endMs >= startMs) {
      return Math.max((endMs - startMs) / 86400000, 1);
    }

    const timerangeDays = _timerangeDays(run.timerange);
    if (timerangeDays != null) return timerangeDays;

    const daily = Array.isArray(results.daily_profit) ? results.daily_profit : [];
    if (daily.length > 0) return daily.length;

    const dayRows = results.periodic_breakdown?.day || [];
    if (Array.isArray(dayRows) && dayRows.length > 0) return dayRows.length;

    const trades = Array.isArray(results.trades) ? results.trades : [];
    if (trades.length > 0) {
      const tradeStart = trades
        .map((trade) => _resultDateMs(trade.openDate || trade.open_date || trade.closeDate || trade.close_date))
        .filter((value) => value != null)
        .sort((a, b) => a - b);
      const tradeEnd = trades
        .map((trade) => _resultDateMs(trade.closeDate || trade.close_date || trade.openDate || trade.open_date))
        .filter((value) => value != null)
        .sort((a, b) => b - a);
      if (tradeStart.length && tradeEnd.length && tradeEnd[0] >= tradeStart[0]) {
        return Math.max((tradeEnd[0] - tradeStart[0]) / 86400000, 1);
      }
    }

    return null;
  }

  function _deriveWinLossStats(results) {
    const summaryMetrics = results.summary_metrics || {};
    const metricWins = FMT.toNumber(summaryMetrics.wins);
    const metricLosses = FMT.toNumber(summaryMetrics.losses);
    const metricDraws = FMT.toNumber(summaryMetrics.draws);
    if (metricWins != null || metricLosses != null || metricDraws != null) {
      return {
        wins: metricWins ?? 0,
        losses: metricLosses ?? 0,
        draws: metricDraws ?? 0,
      };
    }

    const perPair = Array.isArray(results.per_pair) ? results.per_pair : [];
    if (perPair.length) {
      return perPair.reduce((acc, row) => {
        acc.wins += FMT.toNumber(row.wins) ?? 0;
        acc.losses += FMT.toNumber(row.losses) ?? 0;
        acc.draws += FMT.toNumber(row.draws) ?? 0;
        return acc;
      }, { wins: 0, losses: 0, draws: 0 });
    }

    const trades = Array.isArray(results.trades) ? results.trades : [];
    if (trades.length) {
      return trades.reduce((acc, trade) => {
        const profit = FMT.toNumber(trade.profit_abs ?? trade.profitAbs ?? trade.profit_pct ?? trade.profitPct) ?? 0;
        if (profit > 0) acc.wins += 1;
        else if (profit < 0) acc.losses += 1;
        else acc.draws += 1;
        return acc;
      }, { wins: 0, losses: 0, draws: 0 });
    }

    return { wins: null, losses: null, draws: null };
  }

  function _resultSummaryCard(title, value, meta = '', tone = '', variant = '') {
    return `
      <article class="bt-summary-card${variant ? ` bt-summary-card--${variant}` : ''}">
        <div class="bt-summary-card__label">${_esc(title)}</div>
        <div class="bt-summary-card__value ${tone ? `text-${tone}` : ''}">${value}</div>
        ${meta ? `<div class="bt-summary-card__meta">${meta}</div>` : ''}
      </article>
    `;
  }

  function _resultRiskMeta(results, drawdownAbs) {
    const risk = results.risk_metrics || {};
    const lossStreak = FMT.toNumber(risk.max_consecutive_losses ?? results.summary?.maxConsecutiveLosses);
    const duration = risk.drawdown_duration || results.summary?.drawdownDuration;
    if (duration) return `Peak-to-trough drawdown lasted ${_esc(duration)}`;
    if (lossStreak != null && lossStreak > 0) return `Worst losing streak reached ${FMT.integer(lossStreak)} trades`;
    if (drawdownAbs != null) return `Peak-to-trough wallet drop was ${FMT.currency(drawdownAbs)}`;
    return '';
  }

  function _issueTone(severity) {
    return window.StrategyIntelligenceUI?.issueTone?.(severity) || 'muted';
  }

  function _comparisonDeltaValue(row) {
    if (!row || row.diff == null) return '—';
    if (row.format === 'currency') return FMT.currency(row.diff);
    if (row.format === 'integer') return `${row.diff > 0 ? '+' : ''}${FMT.integer(row.diff)}`;
    if (row.format === 'ratio') return `${row.diff > 0 ? '+' : ''}${FMT.number(row.diff, 2)}`;
    return FMT.pct(row.diff, 1, true);
  }

  function _comparisonTone(row) {
    if (!row || row.diff == null) return '';
    const signed = row.higher_is_better === false ? -row.diff : row.diff;
    return FMT.toneProfit(signed);
  }

  function _intelligenceComparisonRows(comparison) {
    return window.StrategyIntelligenceUI?.comparisonRows?.(comparison) || [];
  }

  function _intelligenceSuggestionGroups(intelligence) {
    return window.StrategyIntelligenceUI?.suggestionGroups?.(intelligence) || { quickParams: [], manualGuidance: [] };
  }

  function _intelligenceVisibleIssues(diagnosis) {
    return window.StrategyIntelligenceUI?.visibleIssues?.(diagnosis) || [];
  }

  function _intelligenceMetricSnapshotText(snapshot) {
    if (!snapshot || typeof snapshot !== 'object') return '';
    const parts = [];
    if (FMT.toNumber(snapshot.total_trades) != null) parts.push(`${FMT.integer(snapshot.total_trades)} trades`);
    if (FMT.toNumber(snapshot.win_rate_pct) != null) parts.push(`${FMT.pct(snapshot.win_rate_pct, 1, false)} win rate`);
    if (FMT.toNumber(snapshot.profit_factor) != null) parts.push(`Profit factor ${FMT.number(snapshot.profit_factor, 2)}`);
    if (FMT.toNumber(snapshot.total_profit_pct) != null) parts.push(`${FMT.pct(snapshot.total_profit_pct)} return`);
    if (FMT.toNumber(snapshot.max_drawdown_pct) != null) parts.push(`${FMT.pct(snapshot.max_drawdown_pct, 1, false)} max drawdown`);
    return parts.join(' · ');
  }

  function _intelligenceMetricSnapshotText(snapshot) {
    return window.StrategyIntelligenceUI?.metricSnapshotText?.(snapshot) || '';
  }

  function _intelligenceStatPill(item) {
    return `
      <div class="si-stat-pill" data-intelligence-stat="${_esc(item.label || '')}">
        <span class="si-stat-pill__label">${_esc(item.label || '')}</span>
        <span class="si-stat-pill__value text-${_esc(item.tone || 'muted')}">${_esc(item.value || '—')}</span>
      </div>
    `;
  }

  function _intelligenceActionCard(card, kind) {
    return `
      <article class="si-action-card si-action-card--${_esc(kind)}" data-intelligence-action-card="${_esc(kind)}">
        <div class="si-action-card__title">${_esc(card.title || 'Suggestion')}</div>
        <div class="si-action-card__body">${_esc(card.description || '')}</div>
        ${card.meta ? `<div class="si-action-card__meta">${_esc(card.meta)}</div>` : ''}
        ${card.evidence ? `<div class="si-action-card__evidence">${_esc(card.evidence)}</div>` : ''}
      </article>
    `;
  }

  function _reviewPayloadSummaryHtml() {
    const meta = _loadedResult?.meta || {};
    const payload = {
      strategy: _quickParamsState.strategyName || _resolveRunStrategyName(meta) || null,
      pairs: Array.isArray(meta.pairs) ? [...meta.pairs] : [],
      timeframe: meta.timeframe || '5m',
      timerange: meta.timerange || null,
      strategy_params: _strategyRerunFinalParams(),
    };
    return `<pre class="result-explorer__json">${_esc(JSON.stringify(payload, null, 2))}</pre>`;
  }

  function _renderStrategyRerunReview() {
    if (!_strategyRerunReview.active) return '';
    const validation = _strategyRerunValidation();
    const applied = _strategyRerunAppliedChanges();
    const skipped = _strategyRerunSkippedChanges();
    return `
      <article class="bt-intelligence__panel bt-intelligence__panel--comparison">
        <div class="bt-intelligence__panel-title">Improve & Re-run Review</div>
        <div class="bt-intelligence__list">
          <div class="bt-intelligence__item">
            <div class="bt-intelligence__item-title">${_esc(_strategyRerunReview.diagnosisTitle || 'Rerun Review')}</div>
            <div class="bt-intelligence__item-body">${_esc(_strategyRerunReview.improvementBrief || 'Review the proposed changes before rerunning.')}</div>
            <div class="bt-intelligence__item-evidence">${_esc(`Source run: ${_strategyRerunReview.sourceRunId || 'unknown'}`)}</div>
          </div>
          ${_strategyRerunReview.autoChanges.length ? `
            <div class="bt-intelligence__item-title bt-intelligence__item-title--subsection">Proposed Quick Changes</div>
            ${_strategyRerunReview.autoChanges.map((item) => `
              <label class="checkbox-label quick-params__checkbox" style="align-items:flex-start">
                <input type="checkbox" data-review-toggle="${_esc(item.name)}" ${item.selected ? 'checked' : ''} ${item.available ? '' : 'disabled'}>
                <span>
                  <strong>${_esc(item.label || item.name)}</strong>
                  <span style="display:block;color:var(--text-muted)">${_esc(item.available ? `${item.name} -> ${item.proposedValue}` : (item.unavailableReason || 'Unavailable in Quick Params'))}</span>
                  ${item.reason ? `<span style="display:block;color:var(--text-dim)">${_esc(item.reason)}</span>` : ''}
                </span>
              </label>
            `).join('')}
          ` : '<div class="bt-intelligence__item"><div class="bt-intelligence__item-body">No direct quick-parameter changes are available for this rerun.</div></div>'}
          ${_strategyRerunReview.manualItems.length ? `
            <div class="bt-intelligence__item-title bt-intelligence__item-title--subsection">Manual Guidance</div>
            ${_strategyRerunReview.manualItems.map((item) => `
              <div class="bt-intelligence__item">
                <div class="bt-intelligence__item-body">${_esc(item)}</div>
              </div>
            `).join('')}
          ` : ''}
          ${_strategyRerunReview.unsupportedItems.length ? `
            <div class="bt-intelligence__item-title bt-intelligence__item-title--subsection">Unsupported / Unavailable</div>
            ${_strategyRerunReview.unsupportedItems.map((item) => `
              <div class="bt-intelligence__item">
                <div class="bt-intelligence__item-title">${_esc(item.title || item.parameter || 'Suggestion')}</div>
                <div class="bt-intelligence__item-body">${_esc(item.reason || item.unavailableReason || 'This suggestion cannot be auto-applied in Quick Params.')}</div>
              </div>
            `).join('')}
          ` : ''}
          <div class="bt-intelligence__item-title bt-intelligence__item-title--subsection">Reviewed Payload</div>
          ${_reviewPayloadSummaryHtml()}
          <div class="bt-intelligence__item-evidence">${_esc(validation.message)}</div>
          <div class="bt-intelligence__item-evidence">${_esc(`Applied: ${applied.length} · Skipped: ${skipped.length} · ${validation.contextOnly ? 'Context-only rerun' : 'Parameter rerun'}`)}</div>
          <div class="bt-intelligence__actions" style="justify-content:flex-start">
            <button type="button" class="btn btn--primary btn--sm" data-intelligence-review-action="run" ${validation.ok ? '' : 'disabled'}>Run Improved Backtest</button>
            <button type="button" class="btn btn--secondary btn--sm" data-intelligence-review-action="cancel">Cancel Review</button>
          </div>
        </div>
      </article>
    `;
  }

  function _updateStrategyRerunReview() {
    if (!_strategyRerunReview.active || !_loadedResult?.results) return;
    _strategyRerunReview.contextOnly = _strategyRerunContextOnly();
    _renderResults(DOM.$('#bt-results-body', _el), _loadedResult.results);
  }

  async function _prepareStrategyIntelligenceRerunReview(intelligence, pending = null) {
    if (!_loadedResult?.meta || !intelligence) {
      Toast.warning('No strategy intelligence is available for this run yet.');
      return;
    }
    _setStrategyRerunPhase('preparing');
    try {
      const runId = _loadedResult.run_id || _resultRunId || null;
      await _ensureQuickParamsForRun(_loadedResult);
      if (runId && _quickParamsState.runId === runId && _quickParamsState.loading) {
        await _waitForQuickParamsReady(runId);
      }
      if (_quickHasParams()) {
        _quickParamsState.currentValues = { ..._quickParamsState.seedValues };
      }
      const rerunPlan = intelligence.rerun_plan || {};
      const autoChangesRaw = Array.isArray(rerunPlan.auto_param_changes) ? rerunPlan.auto_param_changes : [];
      const unsupportedRaw = Array.isArray(rerunPlan.unsupported_items) ? rerunPlan.unsupported_items : [];
      const manualItems = Array.isArray(rerunPlan.manual_actions) ? rerunPlan.manual_actions : [];
      const suggestions = Array.isArray(intelligence.suggestions) ? intelligence.suggestions : [];
      const quickSuggestionByParam = new Map(
        suggestions
          .filter((item) => item && item.action_type === 'quick_param' && item.parameter)
          .map((item) => [item.parameter, item])
      );
      const baselineParams = _quickHasParams()
        ? { ..._quickParamsState.seedValues }
        : { ...(_loadedResult.meta.strategy_params || pending?.baselineParams || {}) };
      const autoChanges = autoChangesRaw.map((change) => {
        const suggestion = quickSuggestionByParam.get(change.name) || null;
        const param = _findQuickParam(change.name);
        const available = Boolean(param);
        const proposedValue = param ? _coerceQuickParamValue(param, change.value) : change.value;
        const baselineValue = available ? baselineParams[change.name] : undefined;
        const different = available ? !_quickValuesEqual(baselineValue, proposedValue) : false;
        if (available && different && _quickHasParams()) {
          _quickParamsState.currentValues[change.name] = proposedValue;
        }
        return {
          ...change,
          title: change.title || suggestion?.title || change.label || change.name,
          label: change.label || suggestion?.title || change.name,
          proposedValue,
          available,
          selected: available && different,
          unavailableReason: available ? '' : 'Parameter is not available in Quick Params for this strategy.',
        };
      });
      const missingUnsupported = autoChanges
        .filter((item) => !item.available)
        .map((item) => ({
          title: item.label || item.name,
          parameter: item.name,
          reason: item.unavailableReason,
          unavailableReason: item.unavailableReason,
        }));
      const improvementItems = suggestions.slice(0, 6).map((item) => item.title).filter(Boolean);
      const primary = intelligence.diagnosis?.primary || {};
      _strategyRerunReview = {
        active: true,
        sourceRunId: runId,
        strategyName: _quickParamsState.strategyName || _resolveRunStrategyName(_loadedResult.meta),
        strategyLabel: _quickParamsState.strategyLabel || _resolveRunStrategyLabel(_loadedResult.meta),
        baselineParams,
        autoChanges,
        manualItems,
        unsupportedItems: [...unsupportedRaw, ...missingUnsupported],
        improvementItems,
        improvementBrief: primary.explanation || pending?.brief || '',
        diagnosisTitle: primary.title || pending?.diagnosisTitle || '',
        contextOnly: autoChanges.filter((item) => item.selected).length === 0,
        validationMessage: '',
      };
      _renderQuickParams();
      _updateStrategyRerunReview();
      _setStrategyRerunPhase('review');
      Toast.info('Review the proposed changes, then run the improved backtest explicitly.');
    } finally {
      if (_strategyRerunPhase !== 'review' && !_strategyRerunStarting) _setStrategyRerunPhase('idle');
    }
  }

  function _strategyRerunStatusLabel(phase) {
    if (phase === 'preparing') return 'Preparing...';
    if (phase === 'applying') return 'Applying Changes...';
    if (phase === 'review') return 'Review Ready';
    if (phase === 'starting') return 'Starting Rerun...';
    return 'Improve & Run';
  }

  function _setStrategyRerunPhase(phase) {
    _strategyRerunPhase = phase || 'idle';
    _syncIntelligenceRerunUiState();
  }

  function _renderIntelligenceSummary(results) {
    const intelligence = results.strategy_intelligence || {};
    const vm = window.StrategyIntelligenceUI?.build?.(intelligence) || {};
    const primary = vm.primaryCard || {};
    const issues = Array.isArray(vm.issueCards) ? vm.issueCards : [];
    const quickParams = Array.isArray(vm.quickActionCards) ? vm.quickActionCards : [];
    const manualGuidance = Array.isArray(vm.manualGuidanceCards) ? vm.manualGuidanceCards : [];
    const summaryChips = Array.isArray(vm.summaryChips) ? vm.summaryChips : [];
    const primaryStats = Array.isArray(vm.primaryStats) ? vm.primaryStats : [];
    const comparison = intelligence.comparison_to_parent || null;
    const iterationMemory = intelligence.iteration_memory || {};
    if (!issues.length && !quickParams.length && !manualGuidance.length && !primary.title) return '';

    const comparisonRows = _intelligenceComparisonRows(comparison);

    return `
      <section class="bt-intelligence">
        <div class="bt-intelligence__header">
          <div class="bt-intelligence__copy">
            <div class="bt-intelligence__eyebrow">Strategy Intelligence</div>
            <div class="bt-intelligence__title">Diagnosis and next moves</div>
            <div class="bt-intelligence__subtitle">Review the diagnosis, evidence, and recommended next moves before rerunning.</div>
            <div class="bt-intelligence__meta">
              ${summaryChips.map((chip) => `<span class="bt-intelligence__meta-chip">${_esc(chip.label || '')}</span>`).join('')}
            </div>
          </div>
          <div class="bt-intelligence__actions">
            <button type="button" class="btn btn--primary btn--sm" data-intelligence-action="rerun" data-state="idle">Improve & Run</button>
            <button type="button" class="btn btn--secondary btn--sm" data-intelligence-action="explore">Open Full Explorer</button>
          </div>
        </div>
        <div class="bt-intelligence__grid">
          <article class="bt-intelligence__panel">
            <div class="bt-intelligence__panel-title">Primary Diagnosis</div>
            <div class="si-hero si-hero--${_issueTone(primary.severity)}" data-intelligence-primary>
              <div class="si-hero__head">
                <div>
                  <div class="si-hero__eyebrow">Primary diagnosis</div>
                  <div class="si-hero__title">${_esc(primary.title || 'Run diagnosis')}</div>
                </div>
                <div class="si-chip-row">
                  ${primary.severity ? `<span class="si-chip si-chip--tone-${_issueTone(primary.severity)}">${_esc(primary.severity)}</span>` : ''}
                  ${primary.confidence ? `<span class="si-chip">Confidence: ${_esc(primary.confidence)}</span>` : ''}
                </div>
              </div>
              <div class="si-hero__body">${_esc(primary.explanation || 'Review the issues and suggested next moves before rerunning.')}</div>
              <div class="si-hero__evidence" data-intelligence-evidence>${_esc(primary.evidence || 'No metric-backed evidence was captured.')}</div>
              ${primaryStats.length ? `<div class="si-stat-row" data-intelligence-stats>${primaryStats.map(_intelligenceStatPill).join('')}</div>` : ''}
              ${primary.confidenceNote ? `<div class="si-hero__confidence" data-intelligence-confidence-note>${_esc(primary.confidenceNote)}</div>` : ''}
            </div>
          </article>
          <article class="bt-intelligence__panel">
            <div class="bt-intelligence__panel-title">Detected Issues</div>
            <div class="bt-intelligence__list si-issue-list">
              ${issues.length ? issues.slice(0, 3).map((issue) => `
                <article class="si-issue-card si-issue-card--${_esc(issue.tone || 'muted')}" data-intelligence-issue-card>
                  <div class="si-issue-card__title">${_esc(issue.title || 'Issue')}</div>
                  <div class="si-issue-card__body">${_esc(issue.description || '')}</div>
                  ${issue.evidence ? `<div class="si-issue-card__evidence">${_esc(issue.evidence)}</div>` : ''}
                </article>
              `).join('') : ''}
              ${!issues.length ? `<div class="bt-intelligence__item"><div class="bt-intelligence__item-body">No secondary issues were detected beyond the primary diagnosis.</div></div>` : ''}
            </div>
          </article>
          <article class="bt-intelligence__panel">
            <div class="bt-intelligence__panel-title">Next Moves</div>
            <div class="bt-intelligence__list">
              ${quickParams.length ? `
                <div class="si-action-group" data-intelligence-action-group="quick">
                  <div class="si-action-group__title">Quick Parameter Actions</div>
                  <div class="si-action-group__list">
                    ${quickParams.slice(0, 3).map((suggestion) => _intelligenceActionCard(suggestion, 'quick')).join('')}
                  </div>
                </div>
              ` : ''}
              ${manualGuidance.length ? `
                <div class="si-action-group si-action-group--manual" data-intelligence-action-group="manual">
                  <div class="si-action-group__title">Manual Guidance</div>
                  <div class="si-action-group__list">
                    ${manualGuidance.slice(0, 3).map((suggestion) => _intelligenceActionCard(suggestion, 'manual')).join('')}
                  </div>
                </div>
              ` : ''}
              ${!quickParams.length && !manualGuidance.length ? `<div class="bt-intelligence__item"><div class="bt-intelligence__item-body">No suggested follow-up actions were generated for this run.</div></div>` : ''}
            </div>
          </article>
          ${comparisonRows.length ? `
            <article class="bt-intelligence__panel bt-intelligence__panel--comparison">
              <div class="bt-intelligence__panel-title">Compared To Previous Iteration</div>
              <div class="bt-intelligence__compare-grid">
                ${comparisonRows.map((row) => `
                  <div class="bt-intelligence__compare-item">
                    <span class="bt-intelligence__compare-label">${_esc(row.label)}</span>
                    <span class="bt-intelligence__compare-value ${_comparisonTone(row) ? `text-${_comparisonTone(row)}` : ''}">${_comparisonDeltaValue(row)}</span>
                  </div>
                `).join('')}
              </div>
            </article>
          ` : ''}
          ${(iterationMemory.improvement_applied?.length || iterationMemory.improvement_skipped?.length || iterationMemory.improvement_brief) ? `
            <article class="bt-intelligence__panel bt-intelligence__panel--comparison">
              <div class="bt-intelligence__panel-title">Last Rerun Intent</div>
              <div class="bt-intelligence__list">
                ${iterationMemory.improvement_brief ? `<div class="bt-intelligence__item"><div class="bt-intelligence__item-body">${_esc(iterationMemory.improvement_brief)}</div></div>` : ''}
                ${iterationMemory.improvement_applied?.length ? `<div class="bt-intelligence__item-evidence">${_esc(`Applied: ${iterationMemory.improvement_applied.join(', ')}`)}</div>` : ''}
                ${iterationMemory.improvement_skipped?.length ? `<div class="bt-intelligence__item-evidence">${_esc(`Skipped: ${iterationMemory.improvement_skipped.join(', ')}`)}</div>` : ''}
              </div>
            </article>
          ` : ''}
          ${_renderStrategyRerunReview()}
        </div>
      </section>
    `;
  }

  async function _onStrategyIntelligenceEvent(event) {
    const detail = event?.detail || {};
    if (detail.runId && detail.runId !== _resultRunId) {
      await _loadLatestResult(detail.runId);
    }
    await _prepareStrategyIntelligenceRerunReview(
      detail.intelligence || _loadedResult?.results?.strategy_intelligence || null,
      detail,
    );
  }

  function _onStrategyIntelligenceAction(action) {
    if (action === 'explore') {
      if (_resultRunId) ResultExplorer.open(_resultRunId);
      return;
    }
    if (action === 'rerun') {
      void _prepareStrategyIntelligenceRerunReview(_loadedResult?.results?.strategy_intelligence || null);
    }
  }

  function _toggleStrategyRerunReviewChange(name, selected) {
    const item = (_strategyRerunReview.autoChanges || []).find((change) => change.name === name);
    if (!item) return;
    item.selected = Boolean(selected) && item.available;
    if (_quickHasParams() && item.available) {
      _quickParamsState.currentValues[name] = item.selected
        ? item.proposedValue
        : _strategyRerunReview.baselineParams[name];
      _renderQuickParams();
    }
    _updateStrategyRerunReview();
  }

  async function _onStrategyIntelligenceReviewAction(action) {
    if (action === 'cancel') {
      _strategyRerunReview = _createStrategyRerunReviewState();
      if (_quickHasParams()) {
        _quickParamsState.currentValues = { ..._quickParamsState.seedValues };
        _renderQuickParams();
      }
      _setStrategyRerunPhase('idle');
      if (_loadedResult?.results) _renderResults(DOM.$('#bt-results-body', _el), _loadedResult.results);
      return;
    }
    if (action !== 'run') return;

    const validation = _strategyRerunValidation();
    if (!validation.ok) {
      Toast.warning(validation.message);
      return;
    }

    const appliedChanges = _strategyRerunAppliedChanges();
    const skippedChanges = _strategyRerunSkippedChanges();
    await _runQuickParamsBacktest({
      improvementSource: 'strategy_intelligence',
      improvementItems: _strategyRerunReview.improvementItems,
      improvementApplied: appliedChanges,
      improvementSkipped: skippedChanges,
      improvementBrief: _strategyRerunReview.improvementBrief || null,
      contextOnly: validation.contextOnly,
      toastMessage: validation.contextOnly
        ? 'Started a context-only rerun from the reviewed strategy intelligence.'
        : 'Started a reviewed rerun with the selected strategy intelligence changes.',
    });
    _strategyRerunReview = _createStrategyRerunReviewState();
  }

  async function _waitForQuickParamsReady(runId, timeoutMs = 6000) {
    const started = Date.now();
    while (
      _quickParamsState.runId === runId &&
      _quickParamsState.loading &&
      (Date.now() - started) < timeoutMs
    ) {
      await _sleep(50);
    }
  }

  function _renderResults(el, results) {
    if (!el || !results) return;
    const ov = results.overview || {};
    const summary = results.summary || {};
    const risk = results.risk_metrics || {};
    const intelligenceSummary = results.strategy_intelligence?.summary || {};
    const profitPct = FMT.toNumber(intelligenceSummary.net_profit_pct ?? FMT.resultProfitPercent(summary));
    const totalProfitAbs = FMT.toNumber(intelligenceSummary.net_profit_abs ?? summary.totalProfit ?? ov.profit_total_abs);
    const totalTrades = FMT.toNumber(intelligenceSummary.total_trades ?? summary.totalTrades ?? ov.total_trades);
    const winRate = FMT.toNumber(intelligenceSummary.win_rate ?? FMT.resultWinRate(summary.winRate ?? ov.win_rate));
    const drawdownPct = FMT.toNumber(intelligenceSummary.max_drawdown ?? FMT.resultDrawdownPercent(summary.maxDrawdown ?? ov.max_drawdown ?? risk.max_drawdown));
    const drawdownAbs = FMT.toNumber(summary.maxDrawdownAbs ?? ov.max_drawdown_abs ?? risk.max_drawdown_abs);
    const sharpe = FMT.toNumber(summary.sharpeRatio ?? summary.sharpe_ratio ?? ov.sharpe_ratio);
    const startingBalance = FMT.toNumber(intelligenceSummary.starting_wallet ?? ov.starting_balance ?? summary.startingBalance);
    const finalBalance = FMT.toNumber(intelligenceSummary.final_wallet ?? ov.final_balance ?? summary.finalBalance);
    const walletDelta = (startingBalance != null && finalBalance != null) ? (finalBalance - startingBalance) : null;
    const backtestDays = _deriveBacktestDays(results);
    const tradesPerDay = FMT.toNumber(intelligenceSummary.trades_per_day ?? summary.tradesPerDay ?? summary.trades_per_day)
      ?? ((totalTrades != null && backtestDays) ? (totalTrades / backtestDays) : null);
    const tradeMeta = tradesPerDay != null
      ? `${FMT.number(tradesPerDay, 1)} trades/day${backtestDays ? ` · ${FMT.number(backtestDays, 1)} day${backtestDays === 1 ? '' : 's'}` : ''}`
      : '';
    const winLoss = _deriveWinLossStats(results);
    const winLossMeta = (winLoss.wins != null || winLoss.losses != null)
      ? [
          winLoss.wins != null ? `${FMT.integer(winLoss.wins)} wins` : null,
          winLoss.losses != null ? `${FMT.integer(winLoss.losses)} losses` : null,
          winLoss.draws ? `${FMT.integer(winLoss.draws)} draws` : null,
        ].filter(Boolean).join(' · ')
      : '';
    const resultCard = DOM.$('#bt-results-card', _el);
    if (resultCard) {
      resultCard.classList.add('result-explorer-card');
      resultCard.tabIndex = 0;
      resultCard.setAttribute('role', 'button');
      resultCard.setAttribute('aria-label', 'Open result explorer');
    }
    const walletFlowLabel = walletDelta != null && walletDelta !== 0
      ? `${walletDelta > 0 ? 'Gained' : 'Lost'} ${FMT.currency(Math.abs(walletDelta))} from the starting wallet`
      : 'Start and final wallet ended at the same level';
    const netResultMeta = profitPct != null ? `Profit moved ${FMT.pct(profitPct)} versus the starting wallet` : 'Profit percentage was unavailable';
    el.innerHTML = `
      <div class="result-explorer-card__hint">Click anywhere in this card to open the full explorer.</div>
      <div class="bt-results-summary">
        <div class="bt-results-primary">
          <article class="bt-summary-card bt-summary-card--wallet">
            <div class="bt-summary-card__label">Start Wallet → Final Wallet</div>
            <div class="bt-wallet-flow">
              <div class="bt-wallet-flow__item">
                <span class="bt-wallet-flow__tag">Start</span>
                <span class="bt-wallet-flow__value">${FMT.currency(startingBalance)}</span>
              </div>
              <span class="bt-wallet-flow__arrow">→</span>
              <div class="bt-wallet-flow__item">
                <span class="bt-wallet-flow__tag">Final</span>
                <span class="bt-wallet-flow__value ${walletDelta != null ? `text-${FMT.toneProfit(walletDelta)}` : ''}">${FMT.currency(finalBalance)}</span>
              </div>
            </div>
            <div class="bt-summary-card__meta">${walletFlowLabel}</div>
          </article>
          <article class="bt-summary-card bt-summary-card--net">
            <div class="bt-summary-card__label">Net Profit / Loss</div>
            <div class="bt-summary-card__hero ${totalProfitAbs != null ? `text-${FMT.toneProfit(totalProfitAbs)}` : ''}">${totalProfitAbs != null ? FMT.currency(totalProfitAbs) : '—'}</div>
            <div class="bt-summary-card__subvalue ${profitPct != null ? `text-${FMT.toneProfit(profitPct)}` : ''}">${profitPct != null ? FMT.pct(profitPct) : '—'}</div>
            <div class="bt-summary-card__meta">${_esc(netResultMeta)}</div>
          </article>
        </div>
        <div class="bt-results-grid">
          ${_resultSummaryCard('Trade Activity', totalTrades != null ? `${FMT.integer(totalTrades)} total trades` : '—', tradeMeta || 'Trading frequency was unavailable', tradesPerDay != null ? (tradesPerDay >= 4 ? 'amber' : 'muted') : '', 'activity')}
          ${_resultSummaryCard('Win Rate Across Closed Trades', winRate != null ? FMT.pct(winRate, 1, false) : '—', winLossMeta || 'Win/loss breakdown was unavailable', FMT.toneWinRate(winRate), 'quality')}
          ${_resultSummaryCard('Maximum Drawdown', drawdownPct != null ? FMT.pct(drawdownPct, 1, false) : '—', _resultRiskMeta(results, drawdownAbs) || 'Peak-to-trough drawdown context was unavailable', FMT.toneDrawdown(drawdownPct), 'risk')}
        </div>
        ${sharpe != null ? `
          <div class="bt-results-tech">
            <span class="bt-results-tech__label">Strategy Efficiency</span>
            <div class="bt-results-tech__item">
              <span class="bt-results-tech__metric">Sharpe Ratio</span>
              <span class="bt-results-tech__value text-${FMT.toneRatio(sharpe, 1)}">${FMT.number(sharpe, 3)}</span>
            </div>
          </div>
        ` : ''}
        ${_renderIntelligenceSummary(results)}
      </div>`;
    _syncIntelligenceRerunUiState();
  }

  function _onStop() {
    if (!_activeRunId) return;
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
    _syncQuickParamsUiState();
    _syncIntelligenceRerunUiState();
  }

  function _syncIntelligenceRerunUiState() {
    if (!_el) return;
    const resultCard = DOM.$('#bt-results-card', _el);
    if (!resultCard) return;
    const rerunBtn = resultCard.querySelector('[data-intelligence-action="rerun"]');
    if (!rerunBtn) return;
    const blockedByActiveRun = Boolean(_activeRunId);
    const phase = blockedByActiveRun ? 'blocked' : (_strategyRerunPhase || 'idle');
    rerunBtn.disabled = blockedByActiveRun || phase !== 'idle' || Boolean(_strategyRerunStarting);
    rerunBtn.dataset.state = phase;
    rerunBtn.setAttribute('aria-busy', phase === 'idle' || phase === 'blocked' ? 'false' : 'true');
    rerunBtn.textContent = _strategyRerunStatusLabel(phase);
    if (blockedByActiveRun) {
      rerunBtn.title = 'A backtest is already running. Wait for it to finish before using Improve & Run.';
    } else if (phase === 'review') {
      rerunBtn.title = 'A rerun review is open below. Confirm it explicitly or cancel it.';
    } else {
      rerunBtn.title = phase === 'idle' ? '' : 'Preparing strategy-intelligence rerun from this result.';
    }
  }

  function _stopPoll() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
  }

  function _sortRunsNewest(runs) {
    return [...runs].sort((a, b) => {
      const delta = _runTimestamp(b) - _runTimestamp(a);
      if (delta !== 0) return delta;
      return String(b.run_id || '').localeCompare(String(a.run_id || ''));
    });
  }

  function _runTimestamp(run) {
    const candidates = [run?.completed_at, run?.started_at, run?.created_at];
    for (const value of candidates) {
      const ts = Date.parse(value || '');
      if (Number.isFinite(ts)) return ts;
    }
    return 0;
  }

  async function _restoreLatestState(runs) {
    const latestCompleted = runs.find((run) => run.status === 'completed' && run.run_id);
    const latestRunning = runs.find((run) => run.status === 'running' && run.run_id);

    if (latestCompleted) {
      await _loadLatestResult(latestCompleted.run_id);
    } else {
      _clearLoadedResult();
    }

    if (latestRunning) {
      await _resumeActiveRun(latestRunning.run_id);
      return;
    }

    if (!_pollTimer) {
      _activeRunId = null;
      _setRunning(false);
      DOM.hide(DOM.$('#bt-status-card', _el));
    }
  }

  async function _loadLatestResult(runId) {
    if (!runId) return;
    try {
      const data = await API.getRun(runId);
      if (data.status !== 'completed' || !data.results) return;
      _loadedResult = data;
      _resultRunId = runId;
      DOM.show(DOM.$('#bt-results-card', _el));
      _renderResults(DOM.$('#bt-results-body', _el), data.results);
      await _ensureQuickParamsForRun(data);
    } catch {}
  }

  async function _resumeActiveRun(runId) {
    if (!runId) return;
    if (_activeRunId === runId && _pollTimer) return;
    _activeRunId = runId;
    _setRunning(true);
    try {
      const data = await API.getRun(runId);
      _updateStatus(data);
    } catch {}
    _startPoll(runId);
  }

  function _esc(str) {
    const d = document.createElement('div');
    d.textContent = String(str || '');
    return d.innerHTML;
  }

  function refresh() {
    _loadFormData();
    _syncRunState();
    void _consumePendingStrategyIntelligenceRerun();
  }

  return { init, refresh };
})();


