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
      background: '#07131b',
    },
    {
      id: 'ember',
      name: 'Ember',
      description: 'Amber and coral',
      swatches: ['#f97316', '#fb923c', '#facc15'],
      background: '#190c05',
    },
    {
      id: 'aurora',
      name: 'Aurora',
      description: 'Green and mint',
      swatches: ['#22c55e', '#4ade80', '#14b8a6'],
      background: '#09120a',
    },
    {
      id: 'cobalt',
      name: 'Cobalt',
      description: 'Blue and ice',
      swatches: ['#3b82f6', '#60a5fa', '#22d3ee'],
      background: '#081124',
    },
    {
      id: 'ruby',
      name: 'Ruby',
      description: 'Rose and magenta',
      swatches: ['#e11d48', '#fb7185', '#f472b6'],
      background: '#22060d',
    },
    {
      id: 'amethyst',
      name: 'Amethyst',
      description: 'Purple and lavender',
      swatches: ['#8b5cf6', '#a78bfa', '#c084fc'],
      background: '#120e26',
    },
    {
      id: 'sunset',
      name: 'Sunset',
      description: 'Orange and peach',
      swatches: ['#ea580c', '#fb923c', '#fdba74'],
      background: '#25130b',
    },
    {
      id: 'forest',
      name: 'Forest',
      description: 'Deep green and moss',
      swatches: ['#166534', '#16a34a', '#84cc16'],
      background: '#08160d',
    },
    {
      id: 'sakura',
      name: 'Sakura',
      description: 'Pink and cherry blossom',
      swatches: ['#db2777', '#f472b6', '#fb7185'],
      background: '#241023',
    },
    {
      id: 'midnight',
      name: 'Midnight',
      description: 'Dark blue and slate',
      swatches: ['#475569', '#64748b', '#334155'],
      background: '#031024',
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
