/* =================================================================
   STRATEGY LAB PAGE
   Exposes: window.StrategyLabPage
   ================================================================= */

window.StrategyLabPage = (() => {
  const _PREF_EDITOR_VISIBLE = 'strategy_lab_editor_visible';

  let _el = null;
  let _strategies = [];
  let _selected = null;

  let _sourceOriginal = '';
  let _dirty = false;
  let _editorVisible = true;
  let _diffVisible = false;
  let _paramNames = [];
  let _paramMarkers = [];
  let _highlightTimer = null;

  let _editor = null;
  let _mergeView = null;

  function init() {
    _el = DOM.$('[data-view="strategy-lab"]');
    if (!_el) return;
    _editorVisible = _loadEditorVisibilityPref();
    _render();
    load();
  }

  function _render() {
    DOM.setHTML(_el, `
      <div class="strategy-lab-page page-frame page-frame--compact" id="strategy-lab-page">
      <div class="page-header">
        <h1 class="page-header__title">Strategy Lab</h1>
        <p class="page-header__subtitle">Inspect strategy parameters and source in a dedicated editor workspace.</p>
        <div class="page-header__meta" id="sl-meta">Source .py, runtime sidecar values, and extracted parameter metadata stay aligned in one editor flow.</div>
      </div>
      <div class="split-layout split-layout--lab sl-layout">
        <div class="split-layout__sidebar">
          <div class="card card--fill card--panel sl-sidebar-card">
            <div class="card__meta">
              <span>Navigator</span>
              <span>Select a strategy to inspect and edit</span>
            </div>
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
          <div class="card card--fill card--hero" id="sl-detail">
            <div class="card__body">
              <div class="empty-state">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color:var(--text-disabled);margin-bottom:var(--space-3)">
                  <path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18"/>
                </svg>
                <p>Select a strategy to inspect its parameters and source code</p>
              </div>
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
      DOM.setText(DOM.$('#sl-meta', _el), `${_strategies.length} ${_strategies.length === 1 ? 'strategy' : 'strategies'} available for inspection and source edits.`);
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
    _teardownEditors();
    DOM.$$('.strategy-item', _el).forEach(i => i.classList.remove('active'));
    if (listItem) listItem.classList.add('active');

    const detail = DOM.$('#sl-detail', _el);
    detail.innerHTML = '<div class="card__body"><div class="empty-state">Loading strategy details…</div></div>';

    try {
      const [paramsRes, sourceRes] = await Promise.all([
        API.getStrategyParams(name),
        API.getStrategySource(name),
      ]);
      const params = paramsRes.parameters || [];
      _paramNames = params.map(p => String(p.name || '')).filter(Boolean);
      const source = String(sourceRes || '');
      _sourceOriginal = source;
      _dirty = false;
      _diffVisible = false;
      _renderDetail(detail, name, params, source);
      _mountEditor();
      _updateEditorUi();
    } catch (err) {
      detail.innerHTML = `<div class="card__body"><div class="empty-state text-red">Failed: ${_esc(err.message)}</div></div>`;
    }
  }

  function _renderDetail(el, name, params, source) {
    el.innerHTML = `
      <div class="card__header">
        <span class="card__title">${_esc(name)}</span>
        <div class="sl-header-badges">
          <span class="badge sl-count-badge">${params.length} parameters</span>
          <span class="badge badge--${_dirty ? 'amber' : 'green'}" id="sl-dirty-badge">${_dirty ? 'Unsaved' : 'Saved'}</span>
        </div>
      </div>
      <div class="card__body sl-detail-body">
        <section class="sl-inspector-strip">
          <article class="sl-inspector-metric">
            <span class="sl-inspector-metric__label">Parameters</span>
            <span class="sl-inspector-metric__value">${params.length}</span>
          </article>
          <article class="sl-inspector-metric">
            <span class="sl-inspector-metric__label">Editor Mode</span>
            <span class="sl-inspector-metric__value" id="sl-editor-mode-metric">${_diffVisible ? 'Diff' : 'Source'}</span>
          </article>
          <article class="sl-inspector-metric">
            <span class="sl-inspector-metric__label">Source Lines</span>
            <span class="sl-inspector-metric__value">${String(source.split('\n').length)}</span>
          </article>
        </section>

        ${params.length ? `
          <section class="sl-panel">
            <div class="sl-panel__head">
              <h3 class="section-heading sl-panel__title">Parameter Inspector</h3>
              <span class="sl-panel__meta">Defaults and extracted metadata</span>
            </div>
            <div class="sl-params-table-wrap">
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
            </table>
            </div>
          </section>` : '<div class="empty-state">No configurable parameters found.</div>'}

        <section class="sl-source-card">
          <div class="sl-source-toolbar">
            <div class="sl-source-toolbar__left">
              <h3 class="section-heading sl-source-heading">Source</h3>
              <span class="badge badge--muted" id="sl-editor-mode">Editor</span>
            </div>
            <div class="sl-source-toolbar__actions">
              <button class="btn btn--ghost btn--sm" id="sl-toggle-editor-btn" type="button">
                ${_editorVisible ? 'Hide Editor' : 'Show Editor'}
              </button>
              <button class="btn btn--secondary btn--sm" id="sl-toggle-diff-btn" type="button" ${_editorVisible ? '' : 'disabled'}>
                Show Diff
              </button>
              <button class="btn btn--ghost btn--sm" id="sl-reset-source-btn" type="button" ${_editorVisible ? '' : 'disabled'}>
                Reset
              </button>
              <button class="btn btn--primary btn--sm" id="sl-save-source-btn" type="button" ${_editorVisible ? '' : 'disabled'}>
                Save
              </button>
            </div>
          </div>

          <div class="sl-source-body ${_editorVisible ? '' : 'is-hidden'}" id="sl-source-body">
            <div class="sl-source-editor" id="sl-source-editor"></div>
          </div>

          <div class="sl-source-fallback ${_editorVisible ? '' : 'is-hidden'}" id="sl-source-fallback" style="display:none">
            <label class="text-xs text-muted" for="sl-source-textarea">Source editor (fallback)</label>
            <textarea id="sl-source-textarea" class="form-input sl-source-textarea">${_esc(source)}</textarea>
          </div>

          <div class="sl-source-collapsed ${_editorVisible ? 'is-hidden' : ''}" id="sl-source-collapsed">
            Editor is hidden. Click "Show Editor" to edit source.
          </div>

          <div class="sl-source-error text-red" id="sl-source-error" style="display:none"></div>
        </section>
      </div>`;

    _bindDetailEvents();
  }

  function _bindDetailEvents() {
    const detail = DOM.$('#sl-detail', _el);
    const toggleEditorBtn = DOM.$('#sl-toggle-editor-btn', detail);
    const toggleDiffBtn = DOM.$('#sl-toggle-diff-btn', detail);
    const resetBtn = DOM.$('#sl-reset-source-btn', detail);
    const saveBtn = DOM.$('#sl-save-source-btn', detail);

    DOM.on(toggleEditorBtn, 'click', () => {
      _editorVisible = !_editorVisible;
      _saveEditorVisibilityPref(_editorVisible);
      _updateEditorUi();
    });

    DOM.on(toggleDiffBtn, 'click', () => {
      _diffVisible = !_diffVisible;
      _mountEditor();
      _updateEditorUi();
    });

    DOM.on(resetBtn, 'click', () => {
      _hideSourceError();
      _setEditorSource(_sourceOriginal);
      _setDirty(false);
      _scheduleParamHighlights();
      Toast.info('Source reset to last saved version.');
    });

    DOM.on(saveBtn, 'click', async () => {
      if (!_selected || !_dirty) return;
      _hideSourceError();
      saveBtn.disabled = true;
      const originalLabel = saveBtn.textContent;
      saveBtn.textContent = 'Saving…';
      try {
        const source = _getEditorSource();
        await API.saveStrategySource(_selected, source);
        _sourceOriginal = source;
        _setDirty(false);
        Toast.success(`Saved ${_selected}.py`);
      } catch (err) {
        _showSourceError(err.message || 'Failed to save strategy source.');
        Toast.error('Save failed: ' + (err.message || 'Unknown error'));
      } finally {
        saveBtn.disabled = !_dirty || !_editorVisible;
        saveBtn.textContent = originalLabel;
      }
    });
  }

  function _mountEditor() {
    const detail = DOM.$('#sl-detail', _el);
    const host = DOM.$('#sl-source-editor', detail);
    const fallbackWrap = DOM.$('#sl-source-fallback', detail);
    const fallbackTextarea = DOM.$('#sl-source-textarea', detail);
    if (!host || !fallbackWrap || !fallbackTextarea) return;

    const current = _getEditorSource();
    _teardownEditors();

    if (!_editorVisible) return;

    if (typeof window.CodeMirror === 'undefined') {
      fallbackWrap.style.display = '';
      fallbackTextarea.value = current;
      DOM.on(fallbackTextarea, 'input', () => _setDirty(fallbackTextarea.value !== _sourceOriginal));
      return;
    }

    fallbackWrap.style.display = 'none';

    if (_diffVisible && typeof window.CodeMirror.MergeView === 'function') {
      _mergeView = window.CodeMirror.MergeView(host, {
        value: current,
        origLeft: _sourceOriginal,
        lineNumbers: true,
        mode: 'python',
        theme: '4tie',
        lineWrapping: true,
        matchBrackets: true,
        highlightDifferences: true,
        connect: null,
        collapseIdentical: false,
        revertButtons: false,
      });
      _mergeView.editor().on('change', _onEditorChanged);
      _scheduleParamHighlights();
      return;
    }

    _editor = window.CodeMirror(host, {
      value: current,
      mode: 'python',
      theme: '4tie',
      lineNumbers: true,
      lineWrapping: true,
      matchBrackets: true,
      indentUnit: 4,
      tabSize: 4,
      viewportMargin: Infinity,
    });
    _editor.on('change', _onEditorChanged);
    _scheduleParamHighlights();
  }

  function _teardownEditors() {
    _clearParamHighlights();
    if (_highlightTimer) {
      clearTimeout(_highlightTimer);
      _highlightTimer = null;
    }
    const detail = DOM.$('#sl-detail', _el);
    const host = DOM.$('#sl-source-editor', detail);
    if (host) host.innerHTML = '';
    _editor = null;
    _mergeView = null;
  }

  function _getEditorSource() {
    const detail = DOM.$('#sl-detail', _el);
    const fallbackTextarea = DOM.$('#sl-source-textarea', detail);
    if (_mergeView) return _mergeView.editor().getValue();
    if (_editor) return _editor.getValue();
    if (fallbackTextarea) return fallbackTextarea.value;
    return _sourceOriginal;
  }

  function _setEditorSource(source) {
    const detail = DOM.$('#sl-detail', _el);
    const fallbackTextarea = DOM.$('#sl-source-textarea', detail);
    if (_mergeView) {
      _mergeView.editor().setValue(source);
    } else if (_editor) {
      _editor.setValue(source);
    } else if (fallbackTextarea) {
      fallbackTextarea.value = source;
    }
  }

  function _setDirty(isDirty) {
    _dirty = Boolean(isDirty);
    _updateEditorUi();
  }

  function _updateEditorUi() {
    const detail = DOM.$('#sl-detail', _el);
    if (!detail) return;

    const badge = DOM.$('#sl-dirty-badge', detail);
    const editorMode = DOM.$('#sl-editor-mode', detail);
    const editorModeMetric = DOM.$('#sl-editor-mode-metric', detail);
    const toggleEditorBtn = DOM.$('#sl-toggle-editor-btn', detail);
    const toggleDiffBtn = DOM.$('#sl-toggle-diff-btn', detail);
    const resetBtn = DOM.$('#sl-reset-source-btn', detail);
    const saveBtn = DOM.$('#sl-save-source-btn', detail);
    const sourceBody = DOM.$('#sl-source-body', detail);
    const fallbackWrap = DOM.$('#sl-source-fallback', detail);
    const collapsed = DOM.$('#sl-source-collapsed', detail);

    if (badge) {
      badge.className = `badge badge--${_dirty ? 'amber' : 'green'}`;
      badge.textContent = _dirty ? 'Unsaved' : 'Saved';
    }

    if (editorMode) {
      editorMode.textContent = _diffVisible ? 'Diff' : 'Editor';
    }
    if (editorModeMetric) {
      editorModeMetric.textContent = _diffVisible ? 'Diff' : 'Source';
    }

    if (toggleEditorBtn) toggleEditorBtn.textContent = _editorVisible ? 'Hide Editor' : 'Show Editor';
    if (toggleDiffBtn) {
      toggleDiffBtn.textContent = _diffVisible ? 'Hide Diff' : 'Show Diff';
      toggleDiffBtn.disabled = !_editorVisible;
    }
    if (resetBtn) resetBtn.disabled = !_editorVisible;
    if (saveBtn) saveBtn.disabled = !_editorVisible || !_dirty;

    if (sourceBody) DOM.toggleClass(sourceBody, 'is-hidden', !_editorVisible);
    if (fallbackWrap) DOM.toggleClass(fallbackWrap, 'is-hidden', !_editorVisible);
    if (collapsed) DOM.toggleClass(collapsed, 'is-hidden', _editorVisible);

    if (_editorVisible && _editor) {
      setTimeout(() => _editor.refresh(), 0);
      _scheduleParamHighlights();
    }
    if (_editorVisible && _mergeView) {
      setTimeout(() => {
        _mergeView.editor().refresh();
        if (_mergeView.leftOriginal && typeof _mergeView.leftOriginal === 'function') {
          _mergeView.leftOriginal().refresh();
        }
        _scheduleParamHighlights();
      }, 0);
    }
  }

  function _onEditorChanged() {
    _setDirty(_getEditorSource() !== _sourceOriginal);
    _scheduleParamHighlights();
  }

  function _scheduleParamHighlights() {
    if (_highlightTimer) clearTimeout(_highlightTimer);
    _highlightTimer = setTimeout(_applyParamHighlights, 80);
  }

  function _applyParamHighlights() {
    _highlightTimer = null;
    _clearParamHighlights();
    const cm = _mergeView ? _mergeView.editor() : _editor;
    if (!cm || !_paramNames.length) return;
    const names = _paramNames
      .filter(name => /^[A-Za-z_][A-Za-z0-9_]*$/.test(name))
      .slice(0, 400);
    if (!names.length) return;
    const pattern = new RegExp(`\\b(?:${names.map(_escapeRegExp).join('|')})\\b`, 'g');
    const lineCount = cm.lineCount();
    for (let line = 0; line < lineCount; line += 1) {
      const text = cm.getLine(line);
      pattern.lastIndex = 0;
      let match = pattern.exec(text);
      while (match) {
        const from = { line, ch: match.index };
        const to = { line, ch: match.index + match[0].length };
        _paramMarkers.push(cm.markText(from, to, { className: 'sl-param-highlight' }));
        match = pattern.exec(text);
      }
    }
  }

  function _clearParamHighlights() {
    for (const marker of _paramMarkers) marker.clear();
    _paramMarkers = [];
  }

  function _escapeRegExp(value) {
    return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function _showSourceError(message) {
    const detail = DOM.$('#sl-detail', _el);
    const err = DOM.$('#sl-source-error', detail);
    if (!err) return;
    err.style.display = '';
    err.textContent = String(message || 'Unexpected error while saving source.');
  }

  function _hideSourceError() {
    const detail = DOM.$('#sl-detail', _el);
    const err = DOM.$('#sl-source-error', detail);
    if (!err) return;
    err.style.display = 'none';
    err.textContent = '';
  }

  function _loadEditorVisibilityPref() {
    try {
      const v = window.localStorage.getItem(_PREF_EDITOR_VISIBLE);
      if (v === null) return false;
      return v === '1';
    } catch {
      return false;
    }
  }

  function _saveEditorVisibilityPref(isVisible) {
    try {
      window.localStorage.setItem(_PREF_EDITOR_VISIBLE, isVisible ? '1' : '0');
    } catch {}
  }

  function _esc(str) {
    const d = document.createElement('div');
    d.textContent = String(str || '');
    return d.innerHTML;
  }

  function refresh() {
    load();
  }

  return { init, refresh };
})();
