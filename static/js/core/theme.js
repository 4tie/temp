/* =================================================================
   THEME — app-wide color preset management
   Exposes: window.ThemeManager
   ================================================================= */

window.ThemeManager = (() => {
  const STORAGE_KEY = '4tie_theme_preset';
  const DEFAULT_PRESET = 'ocean';
  const PRESETS = [
    {
      id: 'ocean',
      name: 'Ocean',
      description: 'Teal and cyan',
      swatches: ['#2ab7c7', '#77d7de', '#22c55e'],
    },
    {
      id: 'ember',
      name: 'Ember',
      description: 'Amber and coral',
      swatches: ['#f97316', '#fb923c', '#facc15'],
    },
    {
      id: 'aurora',
      name: 'Aurora',
      description: 'Green and mint',
      swatches: ['#22c55e', '#4ade80', '#14b8a6'],
    },
    {
      id: 'cobalt',
      name: 'Cobalt',
      description: 'Blue and ice',
      swatches: ['#3b82f6', '#60a5fa', '#22d3ee'],
    },
    {
      id: 'ruby',
      name: 'Ruby',
      description: 'Rose and magenta',
      swatches: ['#e11d48', '#fb7185', '#f472b6'],
    },
  ];

  function getPresets() {
    return PRESETS.slice();
  }

  function isValidPreset(presetId) {
    return PRESETS.some(preset => preset.id === presetId);
  }

  function getStoredPreset() {
    try {
      const value = localStorage.getItem(STORAGE_KEY) || '';
      return isValidPreset(value) ? value : DEFAULT_PRESET;
    } catch {
      return DEFAULT_PRESET;
    }
  }

  function applyPreset(presetId, options = {}) {
    const nextPreset = isValidPreset(presetId) ? presetId : DEFAULT_PRESET;
    document.documentElement.setAttribute('data-theme-preset', nextPreset);
    if (options.persist !== false) {
      try {
        localStorage.setItem(STORAGE_KEY, nextPreset);
      } catch {}
    }
    return nextPreset;
  }

  function init() {
    applyPreset(getStoredPreset(), { persist: false });
  }

  return {
    DEFAULT_PRESET,
    STORAGE_KEY,
    getPresets,
    getStoredPreset,
    applyPreset,
    init,
  };
})();
