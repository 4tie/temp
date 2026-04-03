/* =================================================================
   TOAST — notification system
   Exposes: window.Toast
   ================================================================= */

window.Toast = (() => {
  let _container = null;

  function _getContainer() {
    if (_container) return _container;
    _container = document.createElement('div');
    _container.className = 'toast-container';
    _container.setAttribute('aria-live', 'polite');
    _container.setAttribute('aria-atomic', 'false');
    document.body.appendChild(_container);
    return _container;
  }

  function show(message, type = 'info', duration = 4000) {
    const container = _getContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;

    const icon = _icon(type);
    toast.innerHTML = `
      <span class="toast__icon">${icon}</span>
      <span class="toast__msg">${_esc(message)}</span>
      <button class="toast__close" aria-label="Dismiss">
        <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/>
        </svg>
      </button>`;

    const close = toast.querySelector('.toast__close');
    close.addEventListener('click', () => dismiss(toast));

    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast--visible'));

    if (duration > 0) {
      setTimeout(() => dismiss(toast), duration);
    }

    return toast;
  }

  function dismiss(toast) {
    if (!toast || !toast.parentNode) return;
    toast.classList.remove('toast--visible');
    toast.classList.add('toast--hiding');
    setTimeout(() => toast.parentNode && toast.parentNode.removeChild(toast), 300);
  }

  function success(msg, dur) { return show(msg, 'success', dur); }
  function error(msg, dur)   { return show(msg, 'error',   dur); }
  function warning(msg, dur) { return show(msg, 'warning', dur); }
  function info(msg, dur)    { return show(msg, 'info',    dur); }

  function _esc(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  function _icon(type) {
    const icons = {
      success: '<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8l4 4 8-8"/></svg>',
      error:   '<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>',
      warning: '<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1l7 14H1L8 1z"/><line x1="8" y1="6" x2="8" y2="10"/><circle cx="8" cy="12.5" r="0.5" fill="currentColor"/></svg>',
      info:    '<svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="8" cy="8" r="7"/><line x1="8" y1="7" x2="8" y2="11"/><circle cx="8" cy="5" r="0.5" fill="currentColor"/></svg>',
    };
    return icons[type] || icons.info;
  }

  return { show, dismiss, success, error, warning, info };
})();
