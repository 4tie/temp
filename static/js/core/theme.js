/* =================================================================
   THEME - app-wide theme mode + accent management
   Exposes: window.ThemeManager
   ================================================================= */

window.ThemeManager = (() => {
  const MODE_KEY = '4tie_theme_mode';
  const ACCENT_KEY = '4tie_theme_accent';
  const LEGACY_PRESET_KEY = '4tie_theme_preset';
  const DEFAULT_MODE = 'dark';
  const DEFAULT_ACCENT = 'indigo';

  const MODES = [
    { id: 'dark', name: 'Dark', description: 'Low-glare workspace with high contrast surfaces.' },
    { id: 'light', name: 'Light', description: 'Bright product UI with softer chrome and cleaner content framing.' },
  ];

  const ACCENTS = [
    { id: 'indigo', name: 'Indigo', description: 'Default product blue.', swatches: ['#4f46e5', '#818cf8', '#0f172a'] },
    { id: 'teal', name: 'Teal', description: 'Cool productivity accent.', swatches: ['#0f766e', '#14b8a6', '#0f172a'] },
    { id: 'rose', name: 'Rose', description: 'Warmer contrast accent.', swatches: ['#e11d48', '#fb7185', '#111827'] },
    { id: 'amber', name: 'Amber', description: 'Brighter editorial accent.', swatches: ['#d97706', '#f59e0b', '#111827'] },
    { id: 'emerald', name: 'Emerald', description: 'Balanced green accent.', swatches: ['#059669', '#34d399', '#0f172a'] },
    { id: 'slate', name: 'Slate', description: 'Muted neutral accent.', swatches: ['#475569', '#94a3b8', '#0f172a'] },
  ];

  const LEGACY_PRESET_MAP = {
    ocean: { mode: 'dark', accent: 'teal' },
    ember: { mode: 'dark', accent: 'amber' },
    aurora: { mode: 'dark', accent: 'emerald' },
    cobalt: { mode: 'dark', accent: 'indigo' },
    ruby: { mode: 'dark', accent: 'rose' },
    amethyst: { mode: 'dark', accent: 'indigo' },
    sunset: { mode: 'light', accent: 'amber' },
    forest: { mode: 'dark', accent: 'emerald' },
    sakura: { mode: 'light', accent: 'rose' },
    midnight: { mode: 'dark', accent: 'slate' },
  };

  function _isValidMode(mode) {
    return MODES.some(item => item.id === mode);
  }

  function _isValidAccent(accent) {
    return ACCENTS.some(item => item.id === accent);
  }

  function _readLegacyPreset() {
    try {
      return localStorage.getItem(LEGACY_PRESET_KEY) || '';
    } catch {
      return '';
    }
  }

  function _getLegacyDefaults() {
    return LEGACY_PRESET_MAP[_readLegacyPreset()] || {};
  }

  function getStoredMode() {
    const legacy = _getLegacyDefaults();
    try {
      const value = localStorage.getItem(MODE_KEY) || '';
      return _isValidMode(value) ? value : (legacy.mode || DEFAULT_MODE);
    } catch {
      return legacy.mode || DEFAULT_MODE;
    }
  }

  function getStoredAccent() {
    const legacy = _getLegacyDefaults();
    try {
      const value = localStorage.getItem(ACCENT_KEY) || '';
      return _isValidAccent(value) ? value : (legacy.accent || DEFAULT_ACCENT);
    } catch {
      return legacy.accent || DEFAULT_ACCENT;
    }
  }

  function applyTheme({ mode, accent, persist = true } = {}) {
    const nextMode = _isValidMode(mode) ? mode : getStoredMode();
    const nextAccent = _isValidAccent(accent) ? accent : getStoredAccent();
    document.documentElement.setAttribute('data-theme', nextMode);
    document.documentElement.setAttribute('data-theme-accent', nextAccent);
    const themePill = document.getElementById('statusbar-theme-pill');
    if (themePill) {
      themePill.textContent = `${nextMode} / ${nextAccent}`;
      themePill.setAttribute('data-theme-mode', nextMode);
    }
    if (persist) {
      try {
        localStorage.setItem(MODE_KEY, nextMode);
        localStorage.setItem(ACCENT_KEY, nextAccent);
      } catch {}
    }
    return { mode: nextMode, accent: nextAccent };
  }

  function applyMode(mode, options = {}) {
    return applyTheme({ mode, accent: options.accent, persist: options.persist !== false });
  }

  function applyAccent(accent, options = {}) {
    return applyTheme({ mode: options.mode, accent, persist: options.persist !== false });
  }

  function init() {
    applyTheme({ persist: false });
  }

  return {
    MODE_KEY,
    ACCENT_KEY,
    LEGACY_PRESET_KEY,
    DEFAULT_MODE,
    DEFAULT_ACCENT,
    getModes: () => MODES.slice(),
    getAccents: () => ACCENTS.slice(),
    getStoredMode,
    getStoredAccent,
    applyTheme,
    applyMode,
    applyAccent,
    init,

    // Compatibility aliases while the frontend transitions away from preset-first calls.
    getPresets: () => ACCENTS.slice(),
    getStoredPreset: getStoredAccent,
    applyPreset: (accent, options = {}) => applyAccent(accent, options),
  };
})();
