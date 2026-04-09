/* =================================================================
   SHELL MENU - shared shell actions + custom context menu
   Exposes: window.ShellMenu
   ================================================================= */

window.ShellMenu = (() => {
  const PRESERVED_LOCAL_STORAGE_KEYS = new Set([
    '4tie_theme_mode',
    '4tie_theme_accent',
    '4tie_theme_preset',
    '4tie_sidebar_collapsed',
  ]);

  const ITEM_LABELS = {
    'undo': 'Undo',
    'redo': 'Redo',
    'cut': 'Cut',
    'copy': 'Copy',
    'paste': 'Paste',
    'select-all': 'Select All',
    'refresh-view': 'Refresh View',
    'reload-app': 'Reload App',
    'hard-reload': 'Hard Reload',
    'empty-cache-hard-reload': 'Empty Cache + Hard Reload',
  };

  const SHELL_ACTION_IDS = [
    'refresh-view',
    'reload-app',
    'hard-reload',
    'empty-cache-hard-reload',
  ];

  let _mounted = false;
  let _refs = {};
  let _state = {
    open: false,
    activeIndex: -1,
    items: [],
    descriptor: null,
    invocation: null,
    lastFocused: null,
    openToken: 0,
  };

  function init() {
    if (_mounted) return;
    _mount();
    _bindGlobalEvents();
    _bindTopbar();
    _mounted = true;
  }

  async function run(actionId, ctx = null) {
    const descriptor = ctx?.descriptor || _state.descriptor;
    const action = ACTIONS[actionId];
    if (!action) return false;
    if (descriptor && typeof action.isEnabled === 'function' && !action.isEnabled(descriptor)) {
      return false;
    }

    close({ restoreFocus: false });
    await action.run({ descriptor, invocation: ctx?.invocation || _state.invocation || null });
    return true;
  }

  function close(options = {}) {
    if (!_mounted || !_state.open) return;

    const focusTarget = _toFocusable(_state.lastFocused);
    _state.open = false;
    _state.activeIndex = -1;
    _state.items = [];
    _state.descriptor = null;
    _state.invocation = null;

    _refs.panel.innerHTML = '';
    _refs.panel.style.left = '';
    _refs.panel.style.top = '';
    _refs.panel.style.visibility = '';
    _refs.root.classList.remove('shell-menu--open');
    _refs.root.hidden = true;

    if (options.restoreFocus === false || !focusTarget) return;
    try {
      focusTarget.focus({ preventScroll: true });
    } catch {
      focusTarget.focus();
    }
  }

  function _mount() {
    const root = document.createElement('div');
    root.className = 'shell-menu';
    root.hidden = true;
    root.innerHTML = `
      <div class="shell-menu__panel" role="menu" aria-label="Context menu" aria-orientation="vertical"></div>
    `;
    document.body.appendChild(root);

    const panel = root.querySelector('.shell-menu__panel');
    panel.addEventListener('contextmenu', (event) => event.preventDefault());
    panel.addEventListener('mousedown', (event) => {
      if (event.target.closest('[data-shell-menu-action]')) {
        event.preventDefault();
      }
    });
    panel.addEventListener('click', (event) => {
      const button = event.target.closest('[data-shell-menu-action]');
      if (!button || button.disabled) return;
      void run(button.dataset.shellMenuAction);
    });

    _refs = { root, panel };
  }

  function _bindGlobalEvents() {
    document.addEventListener('contextmenu', _onContextMenu);
    document.addEventListener('keydown', _onDocumentKeyDown, true);
    document.addEventListener('pointerdown', _onPointerDown, true);
    window.addEventListener('scroll', _onViewportChanged, true);
    window.addEventListener('resize', _onViewportChanged);
    window.addEventListener('blur', _onWindowBlur);
    window.addEventListener('hashchange', _onHashChange);
  }

  function _bindTopbar() {
    const refreshBtn = document.querySelector('#topbar-refresh-btn');
    if (!refreshBtn || refreshBtn.dataset.shellMenuBound === 'true') return;
    refreshBtn.dataset.shellMenuBound = 'true';
    refreshBtn.addEventListener('click', (event) => {
      event.preventDefault();
      void run('refresh-view', {
        descriptor: _describeContext(refreshBtn, 'keyboard', { canPaste: false }),
      });
    });
  }

  function _onContextMenu(event) {
    if (_refs.root?.contains(event.target)) {
      event.preventDefault();
      return;
    }
    if (event.shiftKey) {
      close({ restoreFocus: false });
      return;
    }

    event.preventDefault();
    void _openMenu({
      mode: 'mouse',
      target: event.target,
      clientX: event.clientX,
      clientY: event.clientY,
    });
  }

  function _onDocumentKeyDown(event) {
    if (_state.open && _handleMenuKeydown(event)) return;
    if (!_isOpenTrigger(event)) return;

    event.preventDefault();
    void _openMenu({
      mode: 'keyboard',
      target: document.activeElement || event.target,
      keyboardEvent: event,
    });
  }

  function _onPointerDown(event) {
    if (!_state.open) return;
    if (_refs.root.contains(event.target)) return;
    close({ restoreFocus: false });
  }

  function _onViewportChanged() {
    if (_state.open) close({ restoreFocus: false });
  }

  function _onWindowBlur() {
    if (_state.open) close({ restoreFocus: false });
  }

  function _onHashChange() {
    if (_state.open) close({ restoreFocus: false });
  }

  function _isOpenTrigger(event) {
    return event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10');
  }

  function _handleMenuKeydown(event) {
    if (event.key === 'Escape') {
      event.preventDefault();
      close();
      return true;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      _focusNext(1);
      return true;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      _focusNext(-1);
      return true;
    }
    if (event.key === 'Home') {
      event.preventDefault();
      _focusBoundary(1);
      return true;
    }
    if (event.key === 'End') {
      event.preventDefault();
      _focusBoundary(-1);
      return true;
    }
    if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar') {
      event.preventDefault();
      const item = _state.items[_state.activeIndex];
      if (item && item.kind === 'item' && !item.disabled) {
        void run(item.id);
      }
      return true;
    }
    return false;
  }

  async function _openMenu(invocation) {
    const openToken = ++_state.openToken;
    close({ restoreFocus: false });

    const clipboardState = await _getClipboardState();
    if (openToken !== _state.openToken) return;

    const target = _toElement(invocation.target) || document.body;
    const descriptor = _describeContext(target, invocation.mode, clipboardState);
    const items = _buildItems(descriptor);
    if (!items.some((item) => item.kind === 'item')) return;

    _state.invocation = { ...invocation, target };
    _state.descriptor = descriptor;
    _state.lastFocused = _toFocusable(document.activeElement) || _toFocusable(target);
    _state.items = items;

    _renderItems(items);
    _refs.root.hidden = false;
    _refs.root.classList.add('shell-menu--open');
    _positionPanel(_resolveMenuPoint(invocation, descriptor));

    _state.open = true;
    if (invocation.mode === 'keyboard') {
      _focusBoundary(1);
    } else {
      _setActiveIndex(_findEnabledIndex(0, 1, false));
    }
  }

  function _renderItems(items) {
    const fragment = document.createDocumentFragment();
    items.forEach((item, index) => {
      if (item.kind === 'separator') {
        const separator = document.createElement('div');
        separator.className = 'shell-menu__separator';
        separator.setAttribute('role', 'separator');
        fragment.appendChild(separator);
        return;
      }

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'shell-menu__item';
      button.setAttribute('role', 'menuitem');
      button.dataset.shellMenuAction = item.id;
      button.dataset.shellMenuIndex = String(index);
      button.tabIndex = -1;
      button.textContent = item.label;
      button.disabled = !!item.disabled;
      button.setAttribute('aria-disabled', item.disabled ? 'true' : 'false');
      button.addEventListener('mouseenter', () => _setActiveIndex(index));
      button.addEventListener('focus', () => _setActiveIndex(index));
      fragment.appendChild(button);
    });

    _refs.panel.innerHTML = '';
    _refs.panel.appendChild(fragment);
  }

  function _positionPanel(point) {
    _refs.panel.style.visibility = 'hidden';
    _refs.panel.style.left = '0px';
    _refs.panel.style.top = '0px';

    const rect = _refs.panel.getBoundingClientRect();
    const maxLeft = Math.max(8, window.innerWidth - rect.width - 8);
    const maxTop = Math.max(8, window.innerHeight - rect.height - 8);
    const left = Math.min(Math.max(point.x, 8), maxLeft);
    const top = Math.min(Math.max(point.y, 8), maxTop);

    _refs.panel.style.left = `${Math.round(left)}px`;
    _refs.panel.style.top = `${Math.round(top)}px`;
    _refs.panel.style.visibility = '';
  }

  function _resolveMenuPoint(invocation, descriptor) {
    if (invocation.mode === 'mouse') {
      return { x: invocation.clientX, y: invocation.clientY };
    }

    if (descriptor.primaryRect && (descriptor.primaryRect.width || descriptor.primaryRect.height)) {
      return {
        x: descriptor.primaryRect.left,
        y: descriptor.primaryRect.bottom,
      };
    }

    if (descriptor.targetRect && (descriptor.targetRect.width || descriptor.targetRect.height)) {
      return {
        x: descriptor.targetRect.left + Math.min(24, Math.max(8, descriptor.targetRect.width / 2)),
        y: descriptor.targetRect.top + Math.min(24, Math.max(8, descriptor.targetRect.height / 2)),
      };
    }

    const pageContent = document.querySelector('[data-page-content]');
    const pageRect = pageContent?.getBoundingClientRect();
    if (pageRect) {
      return {
        x: pageRect.left + 24,
        y: pageRect.top + 24,
      };
    }

    return { x: 24, y: 24 };
  }

  function _buildItems(descriptor) {
    const sections = [];

    if (descriptor.type === 'editable') {
      sections.push([
        _buildActionItem('undo', descriptor),
        _buildActionItem('redo', descriptor),
        _buildActionItem('cut', descriptor),
        _buildActionItem('copy', descriptor),
        _buildActionItem('paste', descriptor),
        _buildActionItem('select-all', descriptor),
      ]);
    } else if (descriptor.type === 'selection') {
      sections.push([
        _buildActionItem('copy', descriptor),
        _buildActionItem('select-all', descriptor),
      ]);
    }

    sections.push(SHELL_ACTION_IDS.map((id) => _buildActionItem(id, descriptor)));

    const items = [];
    sections.forEach((section) => {
      const cleaned = section.filter(Boolean);
      if (!cleaned.length) return;
      if (items.length) items.push({ kind: 'separator' });
      items.push(...cleaned);
    });
    return items;
  }

  function _buildActionItem(actionId, descriptor) {
    const action = ACTIONS[actionId];
    if (!action) return null;
    return {
      kind: 'item',
      id: actionId,
      label: ITEM_LABELS[actionId] || actionId,
      disabled: descriptor && typeof action.isEnabled === 'function'
        ? !action.isEnabled(descriptor)
        : false,
    };
  }

  function _setActiveIndex(index) {
    _state.activeIndex = index;
    _refs.panel.querySelectorAll('[data-shell-menu-index]').forEach((button) => {
      const isActive = Number(button.dataset.shellMenuIndex) === index;
      button.classList.toggle('is-active', isActive);
      button.tabIndex = isActive ? 0 : -1;
    });
  }

  function _focusBoundary(direction) {
    const start = direction > 0 ? 0 : _state.items.length - 1;
    const nextIndex = _findEnabledIndex(start, direction, false);
    if (nextIndex >= 0) _focusItem(nextIndex);
  }

  function _focusNext(direction) {
    if (!_state.items.length) return;
    const current = _state.activeIndex >= 0
      ? _state.activeIndex + direction
      : (direction > 0 ? 0 : _state.items.length - 1);
    const nextIndex = _findEnabledIndex(current, direction, true);
    if (nextIndex >= 0) _focusItem(nextIndex);
  }

  function _focusItem(index) {
    const button = _refs.panel.querySelector(`[data-shell-menu-index="${index}"]`);
    if (!button || button.disabled) return;
    _setActiveIndex(index);
    button.focus();
  }

  function _findEnabledIndex(start, direction, wrap) {
    if (!_state.items.length) return -1;

    let index = start;
    let attempts = 0;
    while (attempts < _state.items.length) {
      if (index < 0 || index >= _state.items.length) {
        if (!wrap) return -1;
        index = index < 0 ? _state.items.length - 1 : 0;
      }
      const item = _state.items[index];
      if (item?.kind === 'item' && !item.disabled) return index;
      index += direction;
      attempts += 1;
    }
    return -1;
  }

  function _describeContext(target, mode, clipboardState) {
    const editable = _resolveEditableContext(target, clipboardState);
    if (editable) return editable;

    const selection = _resolveSelectionContext(target, mode);
    if (selection) return selection;

    return {
      type: 'shell',
      kind: 'shell',
      target,
      container: _resolveSelectAllContainer(target),
      canSelectAll: false,
      primaryRect: null,
      targetRect: _safeRect(target),
    };
  }

  function _resolveEditableContext(target, clipboardState) {
    const element = _toElement(target);
    if (!element) return null;

    const codeMirrorRoot = element.closest('.CodeMirror');
    if (codeMirrorRoot?.CodeMirror) {
      const editor = codeMirrorRoot.CodeMirror;
      const history = typeof editor.historySize === 'function' ? editor.historySize() : { undo: 0, redo: 0 };
      const selectionSnapshot = _snapshotCodeMirrorSelection(editor);
      const hasSelection = typeof editor.somethingSelected === 'function' ? editor.somethingSelected() : false;
      return {
        type: 'editable',
        kind: 'codemirror',
        target: codeMirrorRoot,
        editor,
        canUndo: (history.undo || 0) > 0,
        canRedo: (history.redo || 0) > 0,
        canCut: hasSelection,
        canCopy: hasSelection,
        canPaste: _canPasteIntoCodeMirror(editor, clipboardState),
        canSelectAll: true,
        restoreSelection: () => _restoreCodeMirrorSelection(editor, selectionSnapshot),
        primaryRect: _selectionRect(),
        targetRect: _safeRect(codeMirrorRoot),
      };
    }

    if (_isTextInput(element) || element.tagName === 'TEXTAREA') {
      const selectionStart = typeof element.selectionStart === 'number' ? element.selectionStart : 0;
      const selectionEnd = typeof element.selectionEnd === 'number' ? element.selectionEnd : 0;
      const snapshot = {
        start: selectionStart,
        end: selectionEnd,
        direction: element.selectionDirection || 'none',
      };
      return {
        type: 'editable',
        kind: 'native-input',
        target: element,
        canUndo: !_isElementReadOnly(element),
        canRedo: !_isElementReadOnly(element),
        canCut: !_isElementReadOnly(element) && selectionEnd > selectionStart,
        canCopy: selectionEnd > selectionStart,
        canPaste: !_isElementReadOnly(element) && clipboardState.canPaste,
        canSelectAll: true,
        restoreSelection: () => _restoreInputSelection(element, snapshot),
        primaryRect: _safeRect(element),
        targetRect: _safeRect(element),
      };
    }

    const editableRoot = element.closest('[contenteditable]:not([contenteditable="false"])');
    if (editableRoot && editableRoot.isContentEditable) {
      const ranges = _cloneSelectionRanges();
      const text = _currentSelectionText();
      return {
        type: 'editable',
        kind: 'contenteditable',
        target: editableRoot,
        canUndo: true,
        canRedo: true,
        canCut: text.length > 0,
        canCopy: text.length > 0,
        canPaste: clipboardState.canPaste,
        canSelectAll: true,
        restoreSelection: () => _restoreDomSelection(editableRoot, ranges),
        primaryRect: _selectionRect(),
        targetRect: _safeRect(editableRoot),
      };
    }

    return null;
  }

  function _resolveSelectionContext(target, mode) {
    const text = _currentSelectionText();
    if (!text) return null;

    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return null;

    const range = selection.getRangeAt(0);
    const selectionRoot = _toElement(range.commonAncestorContainer);
    if (!selectionRoot || !_isElementVisible(selectionRoot)) return null;
    if (selectionRoot.closest('.page-view') && !selectionRoot.closest('.page-view.active')) return null;
    if (selectionRoot.closest('.CodeMirror, textarea, input, [contenteditable]:not([contenteditable="false"])')) return null;

    const targetElement = _toElement(target);
    if (mode === 'keyboard' && targetElement?.matches?.('button, [role="button"], a, select')) {
      return null;
    }
    if (targetElement && !_sharesSelectionContainer(targetElement, selectionRoot)) {
      const tagName = targetElement.tagName;
      if (tagName !== 'BODY' && tagName !== 'HTML') {
        return null;
      }
    }

    const ranges = _cloneSelectionRanges();
    return {
      type: 'selection',
      kind: 'selection',
      target: selectionRoot,
      container: _resolveSelectAllContainer(selectionRoot),
      canCopy: text.length > 0,
      canSelectAll: true,
      restoreSelection: () => _restoreDomSelection(selectionRoot, ranges),
      primaryRect: _safeRect(range),
      targetRect: _safeRect(targetElement || selectionRoot),
    };
  }

  function _sharesSelectionContainer(target, selectionRoot) {
    if (selectionRoot.contains(target) || target.contains(selectionRoot)) return true;
    return _resolveSelectAllContainer(target) === _resolveSelectAllContainer(selectionRoot);
  }

  function _resolveSelectAllContainer(target) {
    const element = _toElement(target);
    const selectors = [
      '.modal.modal--open .modal__dialog',
      '.ui-log.ui-log--open .ui-log__panel',
      '.page-view.active',
      '[data-topbar]',
      '[data-statusbar]',
      '[data-app-shell]',
    ];

    if (element) {
      const dock = element.closest('#app-ai-dock');
      if (dock && document.querySelector('[data-app-shell]')?.classList.contains('ai-dock-open')) {
        return dock;
      }
      for (const selector of selectors) {
        const match = element.closest(selector);
        if (match && _isElementVisible(match)) return match;
      }
    }

    const openDock = document.querySelector('[data-app-shell].ai-dock-open #app-ai-dock');
    if (openDock && _isElementVisible(openDock)) return openDock;

    for (const selector of selectors) {
      const candidate = document.querySelector(selector);
      if (candidate && _isElementVisible(candidate)) return candidate;
    }
    return document.querySelector('[data-app-shell]') || document.body;
  }

  function _isTextInput(element) {
    if (!(element instanceof HTMLInputElement)) return false;
    const type = (element.type || 'text').toLowerCase();
    return ![
      'button', 'checkbox', 'color', 'file', 'hidden', 'image',
      'radio', 'range', 'reset', 'submit',
    ].includes(type) && typeof element.selectionStart === 'number';
  }

  function _isElementReadOnly(element) {
    return !!(element.disabled || element.readOnly);
  }

  function _canPasteIntoCodeMirror(editor, clipboardState) {
    if (!clipboardState.canPaste) return false;
    if (typeof editor.getOption === 'function') {
      return editor.getOption('readOnly') !== true && editor.getOption('readOnly') !== 'nocursor';
    }
    return true;
  }

  function _restoreInputSelection(element, snapshot) {
    if (!element) return;
    try {
      element.focus({ preventScroll: true });
    } catch {
      element.focus();
    }
    if (typeof element.setSelectionRange === 'function') {
      element.setSelectionRange(snapshot.start, snapshot.end, snapshot.direction || 'none');
    }
  }

  function _snapshotCodeMirrorSelection(editor) {
    if (!editor) return null;
    if (typeof editor.listSelections === 'function') {
      return editor.listSelections().map((item) => ({ anchor: item.anchor, head: item.head }));
    }
    if (typeof editor.getCursor === 'function') {
      const anchor = editor.getCursor('from');
      const head = editor.getCursor('to');
      return [{ anchor, head }];
    }
    return null;
  }

  function _restoreCodeMirrorSelection(editor, snapshot) {
    if (!editor) return;
    editor.focus?.();
    if (snapshot && typeof editor.setSelections === 'function') {
      editor.setSelections(snapshot);
      return;
    }
    if (snapshot?.[0] && typeof editor.setSelection === 'function') {
      editor.setSelection(snapshot[0].anchor, snapshot[0].head);
    }
  }

  function _cloneSelectionRanges() {
    const selection = window.getSelection();
    if (!selection) return [];
    const ranges = [];
    for (let index = 0; index < selection.rangeCount; index += 1) {
      ranges.push(selection.getRangeAt(index).cloneRange());
    }
    return ranges;
  }

  function _restoreDomSelection(target, ranges) {
    const focusTarget = _toFocusable(target);
    if (focusTarget) {
      try {
        focusTarget.focus({ preventScroll: true });
      } catch {
        focusTarget.focus();
      }
    }
    const selection = window.getSelection();
    if (!selection) return;
    selection.removeAllRanges();
    ranges.forEach((range) => {
      try {
        selection.addRange(range.cloneRange());
      } catch {}
    });
  }

  function _selectionRect() {
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return null;
    return _safeRect(selection.getRangeAt(0));
  }

  function _currentSelectionText() {
    try {
      return String(window.getSelection()?.toString() || '').trim();
    } catch {
      return '';
    }
  }

  function _safeRect(target) {
    if (!target || typeof target.getBoundingClientRect !== 'function') return null;
    return target.getBoundingClientRect();
  }

  function _isElementVisible(element) {
    if (!(element instanceof Element) || !element.isConnected) return false;
    if (element.closest('.page-view') && !element.closest('.page-view.active')) return false;
    const style = window.getComputedStyle(element);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    return element.getClientRects().length > 0;
  }

  function _toElement(node) {
    if (node instanceof Element) return node;
    if (node?.nodeType === Node.TEXT_NODE) return node.parentElement;
    return null;
  }

  function _toFocusable(node) {
    return node instanceof HTMLElement && typeof node.focus === 'function' ? node : null;
  }

  async function _getClipboardState() {
    const state = { canPaste: !!navigator.clipboard?.readText };
    if (!navigator.clipboard?.readText || !navigator.permissions?.query) return state;
    try {
      const result = await navigator.permissions.query({ name: 'clipboard-read' });
      state.canPaste = result.state !== 'denied';
    } catch {}
    return state;
  }

  async function _writeClipboardText(text) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const input = document.createElement('textarea');
    input.value = text;
    input.setAttribute('readonly', 'true');
    input.style.position = 'fixed';
    input.style.left = '-9999px';
    document.body.appendChild(input);
    input.select();
    document.execCommand('copy');
    input.remove();
  }

  async function _readClipboardText() {
    if (!navigator.clipboard?.readText) {
      throw new Error('Clipboard read is not available.');
    }
    return navigator.clipboard.readText();
  }

  function _dispatchInput(target, inputType, data = null) {
    try {
      target.dispatchEvent(new InputEvent('input', {
        bubbles: true,
        data,
        inputType,
      }));
    } catch {
      target.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  async function _copyFromSelection(descriptor) {
    descriptor.restoreSelection?.();
    const text = _currentSelectionText();
    if (!text) return;
    await _writeClipboardText(text);
  }

  async function _copyFromInput(descriptor) {
    descriptor.restoreSelection?.();
    const start = descriptor.target.selectionStart ?? 0;
    const end = descriptor.target.selectionEnd ?? 0;
    if (end <= start) return;
    await _writeClipboardText(descriptor.target.value.slice(start, end));
  }

  async function _cutFromInput(descriptor) {
    descriptor.restoreSelection?.();
    const start = descriptor.target.selectionStart ?? 0;
    const end = descriptor.target.selectionEnd ?? 0;
    if (end <= start) return;
    const text = descriptor.target.value.slice(start, end);
    await _writeClipboardText(text);
    descriptor.target.setRangeText('', start, end, 'start');
    _dispatchInput(descriptor.target, 'deleteByCut');
  }

  async function _pasteIntoInput(descriptor) {
    descriptor.restoreSelection?.();
    const text = await _readClipboardText();
    const start = descriptor.target.selectionStart ?? 0;
    const end = descriptor.target.selectionEnd ?? 0;
    descriptor.target.setRangeText(text, start, end, 'end');
    _dispatchInput(descriptor.target, 'insertFromPaste', text);
  }

  async function _copyFromCodeMirror(descriptor) {
    descriptor.restoreSelection?.();
    const text = descriptor.editor?.getSelection?.() || '';
    if (!text) return;
    await _writeClipboardText(text);
  }

  async function _cutFromCodeMirror(descriptor) {
    descriptor.restoreSelection?.();
    const text = descriptor.editor?.getSelection?.() || '';
    if (!text) return;
    await _writeClipboardText(text);
    descriptor.editor?.replaceSelection?.('', 'around');
  }

  async function _pasteIntoCodeMirror(descriptor) {
    descriptor.restoreSelection?.();
    const text = await _readClipboardText();
    descriptor.editor?.replaceSelection?.(text, 'end');
  }

  async function _copyFromContenteditable(descriptor) {
    descriptor.restoreSelection?.();
    const text = _currentSelectionText();
    if (!text) return;
    await _writeClipboardText(text);
  }

  async function _cutFromContenteditable(descriptor) {
    descriptor.restoreSelection?.();
    const text = _currentSelectionText();
    if (!text) return;
    await _writeClipboardText(text);
    window.getSelection()?.deleteFromDocument?.();
    _dispatchInput(descriptor.target, 'deleteByCut');
  }

  async function _pasteIntoContenteditable(descriptor) {
    descriptor.restoreSelection?.();
    const text = await _readClipboardText();
    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    range.deleteContents();
    const node = document.createTextNode(text);
    range.insertNode(node);
    range.setStartAfter(node);
    range.setEndAfter(node);
    selection.removeAllRanges();
    selection.addRange(range);
    _dispatchInput(descriptor.target, 'insertFromPaste', text);
  }

  function _selectAllInInput(descriptor) {
    descriptor.target.focus?.();
    descriptor.target.select?.();
  }

  function _selectAllInCodeMirror(descriptor) {
    descriptor.editor?.execCommand?.('selectAll');
  }

  function _selectAllInContenteditable(descriptor) {
    const selection = window.getSelection();
    if (!selection) return;
    const range = document.createRange();
    range.selectNodeContents(descriptor.target);
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function _selectAllInContainer(descriptor) {
    if (!descriptor.container) return;
    const selection = window.getSelection();
    if (!selection) return;
    const range = document.createRange();
    range.selectNodeContents(descriptor.container);
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function _hardReload() {
    const url = new URL(window.location.href);
    url.pathname = '/';
    url.searchParams.set('__4tie_hr', String(Date.now()));
    window.location.replace(`${url.pathname}${url.search}${url.hash}`);
  }

  async function _emptyCacheAndHardReload() {
    const preserved = {};
    PRESERVED_LOCAL_STORAGE_KEYS.forEach((key) => {
      const value = window.localStorage.getItem(key);
      if (value !== null) preserved[key] = value;
    });

    try { window.sessionStorage.clear(); } catch {}
    try { window.localStorage.clear(); } catch {}
    Object.entries(preserved).forEach(([key, value]) => {
      try { window.localStorage.setItem(key, value); } catch {}
    });

    if (window.caches?.keys) {
      try {
        const names = await window.caches.keys();
        await Promise.allSettled(names.map((name) => window.caches.delete(name)));
      } catch {}
    }

    if (window.indexedDB?.databases) {
      try {
        const dbs = await window.indexedDB.databases();
        await Promise.allSettled(
          dbs
            .map((db) => db?.name)
            .filter(Boolean)
            .map((name) => new Promise((resolve) => {
              const request = window.indexedDB.deleteDatabase(name);
              request.onsuccess = () => resolve(true);
              request.onerror = () => resolve(false);
              request.onblocked = () => resolve(false);
            }))
        );
      } catch {}
    }

    if (navigator.serviceWorker?.getRegistrations) {
      try {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.allSettled(registrations.map((registration) => registration.unregister()));
      } catch {}
    }

    _hardReload();
  }

  const ACTIONS = {
    'undo': {
      isEnabled: (descriptor) => !!descriptor?.canUndo,
      run: ({ descriptor }) => {
        if (descriptor.kind === 'codemirror') return descriptor.editor?.undo?.();
        descriptor.restoreSelection?.();
        document.execCommand?.('undo');
      },
    },
    'redo': {
      isEnabled: (descriptor) => !!descriptor?.canRedo,
      run: ({ descriptor }) => {
        if (descriptor.kind === 'codemirror') return descriptor.editor?.redo?.();
        descriptor.restoreSelection?.();
        document.execCommand?.('redo');
      },
    },
    'cut': {
      isEnabled: (descriptor) => !!descriptor?.canCut,
      run: ({ descriptor }) => {
        if (descriptor.kind === 'native-input') return _cutFromInput(descriptor);
        if (descriptor.kind === 'codemirror') return _cutFromCodeMirror(descriptor);
        if (descriptor.kind === 'contenteditable') return _cutFromContenteditable(descriptor);
      },
    },
    'copy': {
      isEnabled: (descriptor) => !!descriptor?.canCopy,
      run: ({ descriptor }) => {
        if (descriptor.kind === 'native-input') return _copyFromInput(descriptor);
        if (descriptor.kind === 'codemirror') return _copyFromCodeMirror(descriptor);
        if (descriptor.kind === 'contenteditable') return _copyFromContenteditable(descriptor);
        if (descriptor.kind === 'selection') return _copyFromSelection(descriptor);
      },
    },
    'paste': {
      isEnabled: (descriptor) => !!descriptor?.canPaste,
      run: ({ descriptor }) => {
        if (descriptor.kind === 'native-input') return _pasteIntoInput(descriptor);
        if (descriptor.kind === 'codemirror') return _pasteIntoCodeMirror(descriptor);
        if (descriptor.kind === 'contenteditable') return _pasteIntoContenteditable(descriptor);
      },
    },
    'select-all': {
      isEnabled: (descriptor) => !!descriptor?.canSelectAll,
      run: ({ descriptor }) => {
        if (descriptor.kind === 'native-input') return _selectAllInInput(descriptor);
        if (descriptor.kind === 'codemirror') return _selectAllInCodeMirror(descriptor);
        if (descriptor.kind === 'contenteditable') return _selectAllInContenteditable(descriptor);
        if (descriptor.kind === 'selection') return _selectAllInContainer(descriptor);
      },
    },
    'refresh-view': {
      isEnabled: () => true,
      run: () => window.App?.refresh?.(),
    },
    'reload-app': {
      isEnabled: () => true,
      run: () => window.location.reload(),
    },
    'hard-reload': {
      isEnabled: () => true,
      run: () => _hardReload(),
    },
    'empty-cache-hard-reload': {
      isEnabled: () => true,
      run: () => _emptyCacheAndHardReload(),
    },
  };

  return { init, run, close };
})();


