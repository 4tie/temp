/* =================================================================
   CUSTOM SELECT - themed single-select replacement
   Exposes: window.CustomSelect
   ================================================================= */

window.CustomSelect = (() => {
  const INSTANCES = new WeakMap();
  const TRACKED_SELECTS = new Set();
  const MONOSPACE_IDS = new Set([
    'bt-strategy',
    'ho-strategy',
    'ai-model-select',
    'evo-model-select',
  ]);

  let _mounted = false;
  let _accessorsPatched = false;
  let _layer = null;
  let _panel = null;
  let _searchWrap = null;
  let _searchInput = null;
  let _meta = null;
  let _list = null;
  let _empty = null;
  let _idCounter = 0;
  let _openInstance = null;
  let _refreshQueue = new Set();
  let _refreshScheduled = false;
  let _typeaheadBuffer = '';
  let _typeaheadTimer = null;

  function _ensureMounted() {
    if (_mounted) return;

    _layer = document.createElement('div');
    _layer.className = 'custom-select-layer';
    _layer.hidden = true;
    _layer.innerHTML = `
      <div class="custom-select__panel">
        <div class="custom-select__search-wrap" hidden>
          <input
            class="custom-select__search form-input"
            type="search"
            autocomplete="off"
            spellcheck="false"
            placeholder="Search options"
          >
          <div class="custom-select__meta" hidden></div>
        </div>
        <div class="custom-select__empty" hidden>No matches found.</div>
        <div class="custom-select__list" role="listbox"></div>
      </div>
    `;
    document.body.appendChild(_layer);

    _panel = _layer.querySelector('.custom-select__panel');
    _searchWrap = _layer.querySelector('.custom-select__search-wrap');
    _searchInput = _layer.querySelector('.custom-select__search');
    _meta = _layer.querySelector('.custom-select__meta');
    _list = _layer.querySelector('.custom-select__list');
    _empty = _layer.querySelector('.custom-select__empty');

    _searchInput.addEventListener('input', _onSearchInput);
    _searchInput.addEventListener('keydown', _onSearchKeyDown);
    _list.addEventListener('mousedown', (event) => {
      if (event.target.closest('[data-custom-select-option-index]')) {
        event.preventDefault();
      }
    });
    _list.addEventListener('mousemove', _onListPointerMove);
    _list.addEventListener('click', _onListClick);

    document.addEventListener('pointerdown', _onDocumentPointerDown, true);
    document.addEventListener('keydown', _onDocumentKeyDown, true);
    window.addEventListener('scroll', _onViewportChange, true);
    window.addEventListener('resize', _onViewportChange);
    window.addEventListener('blur', _onWindowBlur);
    window.addEventListener('hashchange', _onHashChange);

    _patchSelectAccessors();
    _mounted = true;
  }

  function _patchSelectAccessors() {
    if (_accessorsPatched || !window.HTMLSelectElement) return;
    _patchSelectAccessor(window.HTMLSelectElement.prototype, 'value');
    _patchSelectAccessor(window.HTMLSelectElement.prototype, 'selectedIndex');
    _patchSelectAccessor(window.HTMLSelectElement.prototype, 'disabled');
    _patchSelectAccessor(window.HTMLSelectElement.prototype, 'required');
    _accessorsPatched = true;
  }

  function _patchSelectAccessor(proto, prop) {
    const descriptor = Object.getOwnPropertyDescriptor(proto, prop);
    if (!descriptor || typeof descriptor.get !== 'function' || typeof descriptor.set !== 'function' || !descriptor.configurable) {
      return;
    }

    Object.defineProperty(proto, prop, {
      configurable: true,
      enumerable: descriptor.enumerable,
      get() {
        return descriptor.get.call(this);
      },
      set(value) {
        descriptor.set.call(this, value);
        _queueRefresh(this);
      },
    });
  }

  function _upgrade(select) {
    _ensureMounted();
    if (!(select instanceof HTMLSelectElement)) return null;
    if (select.multiple || select.dataset.uiSelect !== 'true') return null;

    const existing = INSTANCES.get(select);
    if (existing) {
      _syncInstance(existing);
      return existing;
    }

    const id = ++_idCounter;
    const host = document.createElement('div');
    host.className = `custom-select ${select.className || ''}`.trim();
    host.dataset.customSelectHost = 'true';

    if (MONOSPACE_IDS.has(select.id)) {
      host.classList.add('custom-select--monospace');
    }

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = `custom-select__trigger ${select.className || ''}`.trim();
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.innerHTML = `
      <span class="custom-select__label" data-custom-select-label></span>
      <span class="custom-select__chevron" aria-hidden="true">
        <svg viewBox="0 0 12 12" xmlns="http://www.w3.org/2000/svg" fill="none">
          <path d="M2 4l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </span>
    `;
    host.appendChild(trigger);

    select.insertAdjacentElement('afterend', host);
    select.classList.add('custom-select__native');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');

    const label = _findAssociatedLabel(select);
    const instance = {
      id,
      select,
      host,
      trigger,
      labelEl: trigger.querySelector('[data-custom-select-label]'),
      label,
      listId: `custom-select-list-${id}`,
      optionPrefix: `custom-select-option-${id}`,
      options: [],
      filteredOptions: [],
      activeIndex: -1,
      query: '',
      searchable: false,
      observer: null,
      onTriggerClick: null,
      onTriggerKeyDown: null,
      onSelectInput: null,
      onSelectChange: null,
      onLabelClick: null,
    };

    instance.onTriggerClick = () => {
      if (instance.select.disabled) return;
      if (_openInstance === instance) {
        _close();
        return;
      }
      _open(instance, { focusSearch: instance.searchable });
    };
    instance.onTriggerKeyDown = (event) => _onTriggerKeyDown(instance, event);
    instance.onSelectInput = () => _queueRefresh(instance.select);
    instance.onSelectChange = () => _queueRefresh(instance.select);
    instance.onLabelClick = (event) => {
      event.preventDefault();
      if (instance.select.disabled) return;
      instance.trigger.focus({ preventScroll: true });
    };

    trigger.addEventListener('click', instance.onTriggerClick);
    trigger.addEventListener('keydown', instance.onTriggerKeyDown);
    select.addEventListener('input', instance.onSelectInput);
    select.addEventListener('change', instance.onSelectChange);
    if (label) label.addEventListener('click', instance.onLabelClick);

    instance.observer = new MutationObserver(() => _queueRefresh(select));
    instance.observer.observe(select, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['disabled', 'label', 'selected', 'value'],
    });

    INSTANCES.set(select, instance);
    TRACKED_SELECTS.add(select);
    _syncInstance(instance);
    return instance;
  }

  function _upgradeWithin(root = document) {
    _ensureMounted();
    const container = root || document;
    const selects = [];

    if (container instanceof HTMLSelectElement) {
      selects.push(container);
    } else {
      if (container.matches?.('select[data-ui-select="true"]')) {
        selects.push(container);
      }
      selects.push(...container.querySelectorAll('select[data-ui-select="true"]'));
    }

    selects.forEach((select) => _upgrade(select));
  }

  function _refresh(select) {
    const instance = INSTANCES.get(select);
    if (!instance) return;
    _syncInstance(instance);
  }

  function _destroyWithin(root = document) {
    const container = root || document;
    const selects = [];

    if (container instanceof HTMLSelectElement) {
      selects.push(container);
    } else {
      if (container.matches?.('select')) {
        selects.push(container);
      }
      selects.push(...container.querySelectorAll('select'));
    }

    selects.forEach((select) => {
      const instance = INSTANCES.get(select);
      if (instance) _destroyInstance(instance);
    });
  }

  function _destroyInstance(instance) {
    if (!instance) return;
    if (_openInstance === instance) {
      _close({ restoreFocus: false });
    }

    instance.observer?.disconnect();
    instance.trigger.removeEventListener('click', instance.onTriggerClick);
    instance.trigger.removeEventListener('keydown', instance.onTriggerKeyDown);
    instance.select.removeEventListener('input', instance.onSelectInput);
    instance.select.removeEventListener('change', instance.onSelectChange);
    if (instance.label) {
      instance.label.removeEventListener('click', instance.onLabelClick);
    }

    instance.select.classList.remove('custom-select__native');
    instance.select.removeAttribute('aria-hidden');
    instance.select.removeAttribute('tabindex');
    instance.host.remove();

    TRACKED_SELECTS.delete(instance.select);
    INSTANCES.delete(instance.select);
  }

  function _syncInstance(instance, options = {}) {
    if (!instance.select.isConnected || !instance.host.isConnected) {
      _destroyInstance(instance);
      return;
    }

    instance.options = _readOptions(instance.select);
    instance.searchable = _resolveSearchMode(instance.select, instance.options.length);
    if (_openInstance === instance && instance.select.disabled) {
      _close({ restoreFocus: false });
    }

    instance.host.classList.toggle('custom-select--disabled', instance.select.disabled);
    instance.host.classList.toggle('custom-select--required', instance.select.required);
    instance.host.classList.toggle('custom-select--searchable', instance.searchable);

    _updateTrigger(instance);

    if (_openInstance === instance) {
      _renderPanel(instance, {
        preserveQuery: options.preserveQuery !== false,
      });
      _positionPanel(instance);
    }
  }

  function _updateTrigger(instance) {
    const selected = _selectedOption(instance.options);
    const label = selected?.label || instance.select.getAttribute('placeholder') || 'Select option';
    instance.labelEl.textContent = label;
    instance.labelEl.title = label;
    instance.trigger.title = label;
    instance.trigger.disabled = instance.select.disabled;
    instance.trigger.setAttribute('aria-expanded', _openInstance === instance ? 'true' : 'false');
    instance.trigger.setAttribute('aria-controls', instance.listId);
    instance.trigger.setAttribute('aria-required', instance.select.required ? 'true' : 'false');
    instance.trigger.setAttribute('aria-label', _ariaLabel(instance));

    if (instance.searchable) {
      instance.trigger.setAttribute('role', 'combobox');
      instance.trigger.setAttribute('aria-autocomplete', 'list');
    } else {
      instance.trigger.removeAttribute('role');
      instance.trigger.removeAttribute('aria-autocomplete');
      instance.trigger.removeAttribute('aria-activedescendant');
    }
  }

  function _open(instance, opts = {}) {
    if (!instance || instance.select.disabled) return;
    _ensureMounted();
    if (_openInstance && _openInstance !== instance) {
      _close({ restoreFocus: false });
    }

    _openInstance = instance;
    instance.query = '';
    instance.activeIndex = -1;
    instance.host.classList.add('custom-select--open');
    _layer.hidden = false;
    _layer.classList.add('is-open');

    _renderPanel(instance, { preserveQuery: false, preferredActive: opts.preferredActive ?? null });
    _positionPanel(instance);
    _updateTrigger(instance);

    requestAnimationFrame(() => {
      if (_openInstance !== instance) return;
      _positionPanel(instance);
      if (instance.searchable && opts.focusSearch !== false) {
        _searchInput.focus({ preventScroll: true });
        _searchInput.select();
      } else {
        instance.trigger.focus({ preventScroll: true });
      }
    });
  }

  function _close(options = {}) {
    if (!_openInstance) return;

    const instance = _openInstance;
    _openInstance = null;
    instance.query = '';
    instance.activeIndex = -1;
    instance.host.classList.remove('custom-select--open');

    _layer.hidden = true;
    _layer.classList.remove('is-open');
    _panel.style.left = '';
    _panel.style.top = '';
    _panel.style.width = '';
    _panel.style.maxHeight = '';
    _list.innerHTML = '';
    _list.removeAttribute('aria-labelledby');
    _searchInput.value = '';
    _searchInput.removeAttribute('aria-controls');
    _searchInput.removeAttribute('aria-activedescendant');
    _searchWrap.hidden = true;
    _meta.hidden = true;
    _meta.textContent = '';
    _empty.hidden = true;

    _updateTrigger(instance);

    if (options.restoreFocus === false) return;
    if (instance.trigger.isConnected) {
      instance.trigger.focus({ preventScroll: true });
    }
  }

  function _renderPanel(instance, opts = {}) {
    const preserveQuery = opts.preserveQuery !== false;
    if (!preserveQuery) instance.query = '';

    const options = _filterOptions(instance.options, instance.query);
    instance.filteredOptions = options;
    const selectedIndex = options.findIndex((option) => option.selected && !option.disabled);
    const preferredActive = Number.isInteger(opts.preferredActive) ? opts.preferredActive : null;

    if (preferredActive != null && options[preferredActive] && !options[preferredActive].disabled) {
      instance.activeIndex = preferredActive;
    } else if (instance.activeIndex < 0 || !options[instance.activeIndex] || options[instance.activeIndex].disabled) {
      instance.activeIndex = selectedIndex >= 0 ? selectedIndex : _findEnabledOption(options, 0, 1, true);
    }

    _searchWrap.hidden = !instance.searchable;
    _meta.hidden = !instance.searchable;
    _searchInput.value = instance.query;
    _searchInput.setAttribute('aria-controls', instance.listId);

    if (instance.searchable) {
      _meta.textContent = instance.query
        ? `${options.length} match${options.length === 1 ? '' : 'es'}`
        : `${instance.options.length} option${instance.options.length === 1 ? '' : 's'}`;
    }

    _list.id = instance.listId;
    _list.setAttribute('aria-label', _ariaLabel(instance));

    if (!options.length) {
      _list.innerHTML = '';
      _empty.hidden = false;
      _empty.textContent = instance.query
        ? `No matches for "${instance.query}".`
        : 'No options available.';
      _setActiveDescendant(instance, null);
      return;
    }

    _empty.hidden = true;
    _list.innerHTML = options.map((option, index) => {
      const active = index === instance.activeIndex;
      const selected = option.selected;
      return `
        <button
          type="button"
          class="custom-select__option${active ? ' is-active' : ''}${selected ? ' is-selected' : ''}"
          id="${_optionDomId(instance, option.index)}"
          role="option"
          aria-selected="${selected ? 'true' : 'false'}"
          data-custom-select-option-index="${index}"
          data-custom-select-option-value="${_escapeAttribute(option.value)}"
          ${option.disabled ? 'disabled aria-disabled="true"' : ''}
        >
          <span class="custom-select__option-label">${_escapeHtml(option.label)}</span>
          <span class="custom-select__option-check" aria-hidden="true">${selected ? '&#10003;' : ''}</span>
        </button>
      `;
    }).join('');

    _setActiveDescendant(instance, instance.activeIndex >= 0 ? _optionDomId(instance, options[instance.activeIndex].index) : null);
    _scrollActiveIntoView();
  }

  function _positionPanel(instance) {
    if (_openInstance !== instance) return;
    const rect = instance.trigger.getBoundingClientRect();
    const viewportPadding = 10;
    const width = Math.min(Math.max(rect.width, instance.searchable ? 300 : 220), window.innerWidth - (viewportPadding * 2));
    const below = window.innerHeight - rect.bottom - viewportPadding;
    const above = rect.top - viewportPadding;
    const renderAbove = below < 220 && above > below;
    const maxHeight = Math.max(Math.min(renderAbove ? above : below, 380), 160);

    _panel.style.width = `${width}px`;
    _panel.style.maxHeight = `${maxHeight}px`;

    const top = renderAbove
      ? Math.max(viewportPadding, rect.top - maxHeight)
      : Math.min(window.innerHeight - viewportPadding - maxHeight, rect.bottom + 6);
    const left = Math.min(Math.max(viewportPadding, rect.left), window.innerWidth - viewportPadding - width);

    _panel.style.left = `${left}px`;
    _panel.style.top = `${top}px`;
  }

  function _selectActive() {
    if (!_openInstance) return;
    _selectOption(_openInstance, _openInstance.activeIndex);
  }

  function _selectOption(instance, filteredIndex) {
    const option = instance.filteredOptions[filteredIndex];
    if (!option || option.disabled) return;

    instance.select.selectedIndex = option.index;
    instance.select.dispatchEvent(new Event('input', { bubbles: true }));
    instance.select.dispatchEvent(new Event('change', { bubbles: true }));
    _close();
  }

  function _moveActive(delta) {
    if (!_openInstance || !_openInstance.filteredOptions.length) return;
    const nextIndex = _findEnabledOption(
      _openInstance.filteredOptions,
      _openInstance.activeIndex + delta,
      delta >= 0 ? 1 : -1,
      false,
    );
    if (nextIndex < 0) return;
    _openInstance.activeIndex = nextIndex;
    _highlightActiveOption();
  }

  function _moveBoundary(direction) {
    if (!_openInstance || !_openInstance.filteredOptions.length) return;
    const start = direction > 0 ? 0 : _openInstance.filteredOptions.length - 1;
    const nextIndex = _findEnabledOption(_openInstance.filteredOptions, start, direction, true);
    if (nextIndex < 0) return;
    _openInstance.activeIndex = nextIndex;
    _highlightActiveOption();
  }

  function _highlightActiveOption() {
    if (!_openInstance) return;
    _list.querySelectorAll('[data-custom-select-option-index]').forEach((node) => {
      const active = Number(node.dataset.customSelectOptionIndex) === _openInstance.activeIndex;
      node.classList.toggle('is-active', active);
    });
    const option = _openInstance.filteredOptions[_openInstance.activeIndex];
    _setActiveDescendant(_openInstance, option ? _optionDomId(_openInstance, option.index) : null);
    _scrollActiveIntoView();
  }

  function _scrollActiveIntoView() {
    if (!_openInstance) return;
    const active = _list.querySelector('.custom-select__option.is-active');
    if (!active) return;
    active.scrollIntoView({ block: 'nearest' });
  }

  function _queueRefresh(select) {
    const instance = INSTANCES.get(select);
    if (!instance) return;

    _refreshQueue.add(select);
    if (_refreshScheduled) return;

    _refreshScheduled = true;
    queueMicrotask(() => {
      _refreshScheduled = false;
      const pending = [..._refreshQueue];
      _refreshQueue.clear();
      pending.forEach((pendingSelect) => {
        const pendingInstance = INSTANCES.get(pendingSelect);
        if (!pendingInstance) return;
        _syncInstance(pendingInstance, {
          preserveQuery: _openInstance === pendingInstance,
        });
      });
    });
  }

  function _onTriggerKeyDown(instance, event) {
    if (instance.select.disabled) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (_openInstance !== instance) {
        _open(instance, { focusSearch: false });
      }
      _moveActive(1);
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (_openInstance !== instance) {
        _open(instance, { focusSearch: false });
      }
      _moveActive(-1);
      return;
    }

    if (event.key === 'Home') {
      event.preventDefault();
      if (_openInstance !== instance) {
        _open(instance, { focusSearch: false });
      }
      _moveBoundary(1);
      return;
    }

    if (event.key === 'End') {
      event.preventDefault();
      if (_openInstance !== instance) {
        _open(instance, { focusSearch: false });
      }
      _moveBoundary(-1);
      return;
    }

    if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar') {
      event.preventDefault();
      if (_openInstance === instance && !instance.searchable) {
        _selectActive();
      } else {
        _open(instance, { focusSearch: instance.searchable });
      }
      return;
    }

    if (event.key === 'Escape' && _openInstance === instance) {
      event.preventDefault();
      _close();
      return;
    }

    if (!instance.searchable && _isPrintableKey(event)) {
      event.preventDefault();
      if (_openInstance !== instance) {
        _open(instance, { focusSearch: false });
      }
      _handleTypeahead(instance, event.key);
    }
  }

  function _onSearchInput() {
    if (!_openInstance) return;
    _openInstance.query = _searchInput.value.trim();
    _renderPanel(_openInstance, { preserveQuery: true });
    _positionPanel(_openInstance);
  }

  function _onSearchKeyDown(event) {
    if (!_openInstance) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      _moveActive(1);
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      _moveActive(-1);
      return;
    }

    if (event.key === 'Home') {
      event.preventDefault();
      _moveBoundary(1);
      return;
    }

    if (event.key === 'End') {
      event.preventDefault();
      _moveBoundary(-1);
      return;
    }

    if (event.key === 'Enter') {
      event.preventDefault();
      _selectActive();
      return;
    }

    if (event.key === 'Escape') {
      event.preventDefault();
      _close();
      return;
    }

    if (event.key === 'Tab') {
      _close({ restoreFocus: false });
    }
  }

  function _onListPointerMove(event) {
    if (!_openInstance) return;
    const option = event.target.closest('[data-custom-select-option-index]');
    if (!option) return;
    const index = Number(option.dataset.customSelectOptionIndex);
    if (!Number.isInteger(index) || index === _openInstance.activeIndex) return;
    _openInstance.activeIndex = index;
    _highlightActiveOption();
  }

  function _onListClick(event) {
    if (!_openInstance) return;
    const option = event.target.closest('[data-custom-select-option-index]');
    if (!option) return;
    const index = Number(option.dataset.customSelectOptionIndex);
    if (!Number.isInteger(index)) return;
    _selectOption(_openInstance, index);
  }

  function _onDocumentPointerDown(event) {
    if (!_openInstance) return;
    if (_layer.contains(event.target) || _openInstance.host.contains(event.target)) return;
    _close({ restoreFocus: false });
  }

  function _onDocumentKeyDown(event) {
    if (!_openInstance) return;

    if (event.key === 'Escape') {
      event.preventDefault();
      _close();
      return;
    }

    if (event.key === 'Tab') {
      _close({ restoreFocus: false });
      return;
    }

    if (!_openInstance.searchable && _isPrintableKey(event)) {
      if (document.activeElement === _openInstance.trigger) {
        event.preventDefault();
        _handleTypeahead(_openInstance, event.key);
      }
    }
  }

  function _onViewportChange() {
    if (_openInstance) {
      _close({ restoreFocus: false });
    }
  }

  function _onWindowBlur() {
    if (_openInstance) {
      _close({ restoreFocus: false });
    }
  }

  function _onHashChange() {
    if (_openInstance) {
      _close({ restoreFocus: false });
    }
  }

  function _handleTypeahead(instance, key) {
    const char = String(key || '').toLowerCase();
    if (!char) return;

    _typeaheadBuffer += char;
    clearTimeout(_typeaheadTimer);
    _typeaheadTimer = setTimeout(() => {
      _typeaheadBuffer = '';
    }, 700);

    const labels = instance.filteredOptions;
    if (!labels.length) return;
    const startIndex = Math.max(instance.activeIndex, 0);
    const match = _findTypeaheadMatch(labels, _typeaheadBuffer, startIndex + 1);
    const fallback = match >= 0 ? match : _findTypeaheadMatch(labels, _typeaheadBuffer, 0);
    if (fallback < 0) return;
    instance.activeIndex = fallback;
    _highlightActiveOption();
  }

  function _findTypeaheadMatch(options, query, startIndex) {
    const total = options.length;
    for (let offset = 0; offset < total; offset += 1) {
      const index = (startIndex + offset) % total;
      const option = options[index];
      if (option.disabled) continue;
      if (option.label.toLowerCase().startsWith(query)) {
        return index;
      }
    }
    return -1;
  }

  function _readOptions(select) {
    return [...select.options]
      .filter((option) => !option.hidden)
      .map((option, index) => ({
        index,
        value: option.value,
        label: (option.textContent || option.label || option.value || '').trim() || '\u00A0',
        disabled: option.disabled,
        selected: option.selected,
      }));
  }

  function _filterOptions(options, query) {
    const normalized = String(query || '').trim().toLowerCase();
    if (!normalized) return options.slice();
    return options.filter((option) => option.label.toLowerCase().includes(normalized));
  }

  function _resolveSearchMode(select, optionCount) {
    const mode = String(select.dataset.selectSearch || 'auto').toLowerCase();
    if (mode === 'always') return true;
    if (mode === 'never') return false;
    return optionCount >= 10;
  }

  function _selectedOption(options) {
    return options.find((option) => option.selected) || options[0] || null;
  }

  function _findEnabledOption(options, start, direction, clamp) {
    if (!options.length) return -1;
    const delta = direction >= 0 ? 1 : -1;
    let index = start;

    if (clamp) {
      index = Math.min(Math.max(index, 0), options.length - 1);
    }

    while (index >= 0 && index < options.length) {
      if (!options[index].disabled) return index;
      index += delta;
    }
    return clamp ? -1 : _findEnabledOption(options, delta > 0 ? 0 : options.length - 1, delta, true);
  }

  function _setActiveDescendant(instance, optionId) {
    if (instance.searchable) {
      if (optionId) {
        instance.trigger.setAttribute('aria-activedescendant', optionId);
        _searchInput.setAttribute('aria-activedescendant', optionId);
      } else {
        instance.trigger.removeAttribute('aria-activedescendant');
        _searchInput.removeAttribute('aria-activedescendant');
      }
      return;
    }

    if (optionId) {
      instance.trigger.setAttribute('aria-activedescendant', optionId);
    } else {
      instance.trigger.removeAttribute('aria-activedescendant');
    }
  }

  function _findAssociatedLabel(select) {
    if (!select.id) return null;
    return document.querySelector(`label[for="${_escapeAttribute(select.id)}"]`);
  }

  function _ariaLabel(instance) {
    const labelText = instance.label?.textContent?.trim();
    if (labelText) return labelText;
    return instance.select.getAttribute('aria-label') || instance.select.name || instance.select.id || 'Select option';
  }

  function _optionDomId(instance, index) {
    return `${instance.optionPrefix}-${index}`;
  }

  function _escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function _escapeAttribute(value) {
    return _escapeHtml(value).replace(/"/g, '&quot;');
  }

  function _isPrintableKey(event) {
    return event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey;
  }

  return {
    upgrade: _upgrade,
    upgradeWithin: _upgradeWithin,
    refresh: _refresh,
    destroyWithin: _destroyWithin,
  };
})();
