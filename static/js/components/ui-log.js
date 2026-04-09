/* =================================================================
   UI LOG - in-app runtime log drawer
   Exposes: window.UILog
   ================================================================= */

window.UILog = (() => {
  const STORAGE_KEY = '4tie_ui_logs';
  const MAX_LOGS = 400;
  const MAX_RENDER = 200;

  let _logs = [];
  let _mounted = false;
  let _refs = {};

  function _fmtTs(ts) {
    try {
      return new Date(ts).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return '';
    }
  }

  function _safeJson(value) {
    if (value === undefined || value === null) return '';
    try {
      return typeof value === 'string' ? value : JSON.stringify(value);
    } catch {
      return String(value);
    }
  }

  function _save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(_logs.slice(-MAX_LOGS)));
    } catch {}
  }

  function _load() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      if (Array.isArray(parsed)) _logs = parsed.slice(-MAX_LOGS);
    } catch {
      _logs = [];
    }
  }

  function _mount() {
    if (_mounted) return;
    const root = document.createElement('div');
    root.className = 'ui-log';
    root.innerHTML = `
      <button class="ui-log__overlay" type="button" data-ui-log-close aria-label="Close log panel"></button>
      <section class="ui-log__panel" aria-label="Application logs">
        <header class="ui-log__header">
          <div class="ui-log__title-wrap">
            <h3 class="ui-log__title">App Logs</h3>
            <span class="ui-log__meta" data-ui-log-meta>0 entries</span>
          </div>
          <div class="ui-log__actions">
            <button class="btn btn--ghost btn--sm" type="button" data-ui-log-download>Download</button>
            <button class="btn btn--ghost btn--sm" type="button" data-ui-log-clear>Clear</button>
            <button class="btn btn--secondary btn--sm" type="button" data-ui-log-close>Close</button>
          </div>
        </header>
        <div class="ui-log__list" data-ui-log-list></div>
      </section>
    `;
    document.body.appendChild(root);

    _refs = {
      root,
      list: root.querySelector('[data-ui-log-list]'),
      meta: root.querySelector('[data-ui-log-meta]'),
      count: document.querySelector('[data-ui-log-count]'),
      openBtn: document.querySelector('[data-ui-log-open]'),
    };

    root.querySelectorAll('[data-ui-log-close]').forEach((el) => {
      el.addEventListener('click', close);
    });
    root.querySelector('[data-ui-log-clear]')?.addEventListener('click', clear);
    root.querySelector('[data-ui-log-download]')?.addEventListener('click', download);
    _refs.openBtn?.addEventListener('click', toggle);

    _mounted = true;
    _render();
  }

  function _render() {
    if (!_mounted) return;
    const items = _logs.slice(-MAX_RENDER);
    const html = items.map((entry) => {
      const details = entry.details ? `<div class="ui-log__details">${_safeJson(entry.details)}</div>` : '';
      return `
        <article class="ui-log__entry ui-log__entry--${entry.level}">
          <div class="ui-log__entry-head">
            <span class="ui-log__time">${_fmtTs(entry.ts)}</span>
            <span class="ui-log__level">${entry.level.toUpperCase()}</span>
          </div>
          <div class="ui-log__msg">${entry.message || ''}</div>
          ${details}
        </article>
      `;
    }).join('');
    _refs.list.innerHTML = html || '<div class="ui-log__empty">No logs yet.</div>';
    _refs.meta.textContent = `${_logs.length} ${_logs.length === 1 ? 'entry' : 'entries'}`;
    if (_refs.count) {
      _refs.count.textContent = String(_logs.length);
      _refs.count.style.display = _logs.length ? '' : 'none';
    }
    _refs.list.scrollTop = _refs.list.scrollHeight;
  }

  function push(level, message, details = null) {
    _logs.push({
      ts: Date.now(),
      level: String(level || 'info').toLowerCase(),
      message: String(message || ''),
      details,
    });
    if (_logs.length > MAX_LOGS) _logs = _logs.slice(-MAX_LOGS);
    _save();
    _render();
  }

  function info(message, details = null) { push('info', message, details); }
  function warn(message, details = null) { push('warn', message, details); }
  function error(message, details = null) { push('error', message, details); }
  function debug(message, details = null) { push('debug', message, details); }

  function open() {
    if (!_mounted) return;
    _refs.root.classList.add('ui-log--open');
  }

  function close() {
    if (!_mounted) return;
    _refs.root.classList.remove('ui-log--open');
  }

  function toggle() {
    if (!_mounted) return;
    _refs.root.classList.toggle('ui-log--open');
  }

  function clear() {
    _logs = [];
    _save();
    _render();
  }

  function download() {
    const content = _logs
      .map((entry) => `[${new Date(entry.ts).toISOString()}] ${entry.level.toUpperCase()} ${entry.message}${entry.details ? ` | ${_safeJson(entry.details)}` : ''}`)
      .join('\n');
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `4tie-ui-logs-${Date.now()}.log`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function _wireGlobalCapture() {
    window.addEventListener('error', (evt) => {
      error(evt.message || 'Unhandled error', {
        source: evt.filename || '',
        line: evt.lineno || 0,
        col: evt.colno || 0,
      });
    });

    window.addEventListener('unhandledrejection', (evt) => {
      error('Unhandled promise rejection', _safeJson(evt.reason));
    });
  }

  function init() {
    if (_mounted) return;
    _load();
    _mount();
    _wireGlobalCapture();
  }

  return {
    init,
    push,
    info,
    warn,
    error,
    debug,
    open,
    close,
    toggle,
    clear,
    download,
  };
})();

