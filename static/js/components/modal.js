/* =================================================================
   MODAL — open / close with keyboard trap and backdrop
   Exposes: window.Modal
   ================================================================= */

window.Modal = (() => {
  let _active = null;

  function _focusable(modal) {
    return [...modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )].filter(el => !el.disabled);
  }

  function _escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = String(value ?? '');
    return div.innerHTML;
  }

  function _onBackdropClick() {
    close();
  }

  function open(idOrEl) {
    const modal = typeof idOrEl === 'string'
      ? document.getElementById(idOrEl)
      : idOrEl;
    if (!modal) return;

    close();
    modal.classList.add('modal--open');
    document.body.classList.add('modal-open');
    _active = modal;

    const autoFocus = modal.querySelector('[data-modal-autofocus]');
    const focusable = _focusable(modal);
    const target = autoFocus && !autoFocus.disabled ? autoFocus : focusable[0];
    if (target) target.focus();

    modal.addEventListener('keydown', _onKey);
    const backdrop = modal.querySelector('.modal__backdrop');
    if (backdrop) backdrop.addEventListener('click', _onBackdropClick);
  }

  function close(result = null) {
    if (!_active) return;
    const modal = _active;
    const backdrop = modal.querySelector('.modal__backdrop');
    if (backdrop) backdrop.removeEventListener('click', _onBackdropClick);
    modal.classList.remove('modal--open');
    modal.removeEventListener('keydown', _onKey);
    document.body.classList.remove('modal-open');
    _active = null;

    if (typeof modal._onModalClose === 'function') {
      const onClose = modal._onModalClose;
      delete modal._onModalClose;
      onClose(result);
    }
  }

  function _onKey(e) {
    if (e.key === 'Escape') { close(); return; }
    if (e.key === 'Tab') {
      const modal = _active;
      const focusable = _focusable(modal);
      if (!focusable.length) { e.preventDefault(); return; }
      const first = focusable[0];
      const last  = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
    }
  }

  function make({ id, title, body, actions = [], className = '', dialogClass = '', bodyClass = '' }) {
    const el = document.createElement('div');
    el.className = `modal ${className}`.trim();
    el.id = id || '';
    el.innerHTML = `
      <div class="modal__backdrop"></div>
      <div class="modal__dialog ${dialogClass || ''}" role="dialog" aria-modal="true" aria-labelledby="${id}-title">
        <div class="modal__header">
          <h2 class="modal__title" id="${id}-title">${title || ''}</h2>
          <button class="modal__close" aria-label="Close">
            <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/>
            </svg>
          </button>
        </div>
        <div class="modal__body ${bodyClass || ''}">${body || ''}</div>
        ${actions.length ? `<div class="modal__footer">${actions.map(a => `<button type="button" class="btn ${a.class || 'btn--secondary'}" data-modal-action="${a.action || ''}"${a.autoFocus ? ' data-modal-autofocus="true"' : ''}>${_escapeHtml(a.label || '')}</button>`).join('')}</div>` : ''}
      </div>`;

    el.querySelector('.modal__close').addEventListener('click', close);
    document.body.appendChild(el);
    return el;
  }

  function confirm({
    title = 'Confirm Action',
    message = 'Are you sure you want to continue?',
    confirmLabel = 'Confirm',
    cancelLabel = 'Cancel',
    confirmClass = 'btn--danger',
  } = {}) {
    return new Promise(resolve => {
      const modal = make({
        id: `modal-confirm-${Date.now()}`,
        title: _escapeHtml(title),
        body: `<p class="modal__text">${_escapeHtml(message)}</p>`,
        actions: [
          { label: cancelLabel, action: 'cancel', class: 'btn--secondary', autoFocus: true },
          { label: confirmLabel, action: 'confirm', class: confirmClass },
        ],
      });

      modal._onModalClose = (result) => {
        resolve(result === true);
        modal.remove();
      };

      modal.querySelector('[data-modal-action="cancel"]')?.addEventListener('click', () => close(false));
      modal.querySelector('[data-modal-action="confirm"]')?.addEventListener('click', () => close(true));

      open(modal);
    });
  }

  function prompt({
    title = 'Input Required',
    message = '',
    label = 'Value',
    placeholder = '',
    value = '',
    confirmLabel = 'Save',
    cancelLabel = 'Cancel',
  } = {}) {
    return new Promise(resolve => {
      const inputId = `modal-input-${Date.now()}`;
      const messageHtml = message ? `<p class="modal__text">${_escapeHtml(message)}</p>` : '';
      const modal = make({
        id: `modal-prompt-${Date.now()}`,
        title: _escapeHtml(title),
        body: `
          ${messageHtml}
          <label class="modal__field" for="${inputId}">${_escapeHtml(label)}</label>
          <input
            id="${inputId}"
            class="form-input modal__input"
            type="text"
            value="${_escapeHtml(value)}"
            placeholder="${_escapeHtml(placeholder)}"
            data-modal-autofocus
          >
        `,
        actions: [
          { label: cancelLabel, action: 'cancel', class: 'btn--secondary' },
          { label: confirmLabel, action: 'confirm', class: 'btn--primary' },
        ],
      });

      const input = modal.querySelector(`#${inputId}`);
      const submit = () => close({ action: 'submit', value: input?.value ?? '' });

      modal._onModalClose = (result) => {
        resolve(result?.action === 'submit' ? result.value : null);
        modal.remove();
      };

      modal.querySelector('[data-modal-action="cancel"]')?.addEventListener('click', () => close({ action: 'cancel' }));
      modal.querySelector('[data-modal-action="confirm"]')?.addEventListener('click', submit);
      input?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          submit();
        }
      });

      open(modal);
      input?.select();
    });
  }

  function codePrompt({
    title = 'Edit Command',
    message = '',
    label = 'Command',
    value = '',
    confirmLabel = 'Run',
    cancelLabel = 'Cancel',
  } = {}) {
    return new Promise(resolve => {
      const textareaId = `modal-code-${Date.now()}`;
      const messageHtml = message ? `<p class="modal__text">${_escapeHtml(message)}</p>` : '';
      const modal = make({
        id: `modal-code-prompt-${Date.now()}`,
        title: _escapeHtml(title),
        body: `
          ${messageHtml}
          <label class="modal__field" for="${textareaId}">${_escapeHtml(label)}</label>
          <textarea
            id="${textareaId}"
            class="form-input modal__input modal__textarea"
            rows="8"
            spellcheck="false"
            data-modal-autofocus
          >${_escapeHtml(value)}</textarea>
        `,
        actions: [
          { label: cancelLabel, action: 'cancel', class: 'btn--secondary' },
          { label: confirmLabel, action: 'confirm', class: 'btn--primary' },
        ],
      });

      const textarea = modal.querySelector(`#${textareaId}`);
      const submit = () => close({ action: 'submit', value: textarea?.value ?? '' });

      modal._onModalClose = (result) => {
        resolve(result?.action === 'submit' ? result.value : null);
        modal.remove();
      };

      modal.querySelector('[data-modal-action="cancel"]')?.addEventListener('click', () => close({ action: 'cancel' }));
      modal.querySelector('[data-modal-action="confirm"]')?.addEventListener('click', submit);
      textarea?.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault();
          submit();
        }
      });

      open(modal);
      textarea?.focus();
      textarea?.setSelectionRange(0, textarea.value.length);
    });
  }

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && _active) close();
  });

  return { open, close, make, confirm, prompt, codePrompt };
})();
