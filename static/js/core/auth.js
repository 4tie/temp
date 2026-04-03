/* =================================================================
   AUTH — backend health check and connection status
   Exposes: window.Auth
   Requires: window.API, window.DOM
   ================================================================= */

window.Auth = (() => {
  const POLL_INTERVAL = 5000;
  let _timer = null;
  let _online = null;

  function _applyStatus(online) {
    if (_online === online) return;
    _online = online;

    const dot   = DOM.$('[data-conn-dot]');
    const label = DOM.$('[data-conn-label]');
    const pill  = DOM.$('[data-ft-status]');
    const pillLabel = DOM.$('[data-ft-status-label]');

    if (online) {
      if (dot)   { dot.className   = 'statusbar__conn-dot statusbar__conn-dot--online'; }
      if (label) { label.textContent = 'Connected'; }
      if (pill)  { pill.className  = 'status-pill status-pill--connected'; }
      if (pillLabel) { pillLabel.textContent = 'Online'; }
    } else {
      if (dot)   { dot.className   = 'statusbar__conn-dot statusbar__conn-dot--offline'; }
      if (label) { label.textContent = 'Offline'; }
      if (pill)  { pill.className  = 'status-pill status-pill--disconnected'; }
      if (pillLabel) { pillLabel.textContent = 'Offline'; }
    }

    AppState.set('online', online);
  }

  async function check() {
    try {
      await API.health();
      _applyStatus(true);
    } catch {
      _applyStatus(false);
    }
  }

  function startPolling() {
    check();
    _timer = setInterval(check, POLL_INTERVAL);
  }

  function stopPolling() {
    if (_timer) { clearInterval(_timer); _timer = null; }
  }

  function setRunning(isRunning) {
    const pill      = DOM.$('[data-ft-status]');
    const pillLabel = DOM.$('[data-ft-status-label]');
    if (!pill) return;
    if (isRunning) {
      pill.className = 'status-pill status-pill--running';
      if (pillLabel) pillLabel.textContent = 'Running';
    } else {
      _online = null;
      check();
    }
  }

  return { startPolling, stopPolling, check, setRunning };
})();
