/* =================================================================
   MODAL — open / close with keyboard trap and backdrop
   Exposes: window.Modal
   ================================================================= */

window.Modal = (() => {
  let _active = null;

  function open(idOrEl) {
    const modal = typeof idOrEl === 'string'
      ? document.getElementById(idOrEl)
      : idOrEl;
    if (!modal) return;

    close();
    modal.classList.add('modal--open');
    document.body.classList.add('modal-open');
    _active = modal;

    const focusable = modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (focusable.length) focusable[0].focus();

    modal.addEventListener('keydown', _onKey);
    const backdrop = modal.querySelector('.modal__backdrop');
    if (backdrop) backdrop.addEventListener('click', close);
  }

  function close() {
    if (!_active) return;
    _active.classList.remove('modal--open');
    _active.removeEventListener('keydown', _onKey);
    document.body.classList.remove('modal-open');
    _active = null;
  }

  function _onKey(e) {
    if (e.key === 'Escape') { close(); return; }
    if (e.key === 'Tab') {
      const modal = _active;
      const focusable = [...modal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )].filter(el => !el.disabled);
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

  function make({ id, title, body, actions = [] }) {
    const el = document.createElement('div');
    el.className = 'modal';
    el.id = id || '';
    el.innerHTML = `
      <div class="modal__backdrop"></div>
      <div class="modal__dialog" role="dialog" aria-modal="true" aria-labelledby="${id}-title">
        <div class="modal__header">
          <h2 class="modal__title" id="${id}-title">${title || ''}</h2>
          <button class="modal__close" aria-label="Close">
            <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/>
            </svg>
          </button>
        </div>
        <div class="modal__body">${body || ''}</div>
        ${actions.length ? `<div class="modal__footer">${actions.map(a => `<button class="btn ${a.class || 'btn--secondary'}" data-modal-action="${a.action || ''}">${a.label}</button>`).join('')}</div>` : ''}
      </div>`;

    el.querySelector('.modal__close').addEventListener('click', close);
    document.body.appendChild(el);
    return el;
  }

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && _active) close();
  });

  return { open, close, make };
})();
