/* =================================================================
   STATE — lightweight reactive key-value store
   Exposes: window.AppState
   ================================================================= */

window.AppState = (() => {
  const _data = {};
  const _subs = {};

  function get(key) {
    return _data[key];
  }

  function set(key, value) {
    _data[key] = value;
    (_subs[key] || []).forEach(fn => {
      try { fn(value); } catch (e) { console.error('[AppState] subscriber error', e); }
    });
  }

  function subscribe(key, fn) {
    if (!_subs[key]) _subs[key] = [];
    _subs[key].push(fn);
    return () => {
      _subs[key] = _subs[key].filter(f => f !== fn);
    };
  }

  function update(key, fn) {
    set(key, fn(get(key)));
  }

  return { get, set, subscribe, update };
})();
