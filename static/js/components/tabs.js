/* =================================================================
   TABS — tab group switching via data attributes
   Usage: data-tab-group / data-tab="id" / data-tab-panel="id"
   Exposes: window.Tabs
   ================================================================= */

window.Tabs = (() => {

  function init(container) {
    if (!container) return;
    const tabs   = [...container.querySelectorAll('[data-tab]')];
    const panels = [...container.querySelectorAll('[data-tab-panel]')];

    function activate(id) {
      tabs.forEach(t => {
        const active = t.dataset.tab === id;
        t.classList.toggle('tab--active', active);
        t.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      panels.forEach(p => {
        const active = p.dataset.tabPanel === id;
        p.classList.toggle('tab-panel--active', active);
        p.hidden = !active;
      });
    }

    tabs.forEach(tab => {
      tab.setAttribute('role', 'tab');
      tab.setAttribute('tabindex', tab.dataset.tab === tabs[0]?.dataset.tab ? '0' : '-1');
      tab.addEventListener('click', () => activate(tab.dataset.tab));
      tab.addEventListener('keydown', e => {
        const idx = tabs.indexOf(tab);
        if (e.key === 'ArrowRight') { e.preventDefault(); const next = tabs[(idx + 1) % tabs.length]; next.focus(); activate(next.dataset.tab); }
        if (e.key === 'ArrowLeft')  { e.preventDefault(); const prev = tabs[(idx - 1 + tabs.length) % tabs.length]; prev.focus(); activate(prev.dataset.tab); }
      });
    });

    if (tabs.length) activate(tabs[0].dataset.tab);
  }

  function initAll() {
    document.querySelectorAll('[data-tab-group]').forEach(init);
  }

  return { init, initAll };
})();
