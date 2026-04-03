/* =================================================================
   SIDEBAR — collapse toggle, active link, jobs badge
   Exposes: window.Sidebar
   Requires: window.DOM, window.AppState
   ================================================================= */

window.Sidebar = (() => {
  const STORAGE_KEY = '4tie_sidebar_collapsed';

  function init() {
    const shell  = DOM.$('[data-app-shell]');
    const toggle = DOM.$('[data-sidebar-toggle]');

    if (!shell || !toggle) return;

    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'true') shell.classList.add('sidebar-collapsed');

    DOM.on(toggle, 'click', () => {
      const collapsed = shell.classList.toggle('sidebar-collapsed');
      localStorage.setItem(STORAGE_KEY, collapsed ? 'true' : 'false');
    });

    AppState.subscribe('activePage', page => _setActiveLink(page));
    AppState.subscribe('activeJobs', count => _updateBadge(count));
  }

  function _setActiveLink(page) {
    DOM.$$('[data-nav-link]').forEach(link => {
      const isActive = link.dataset.page === page;
      link.classList.toggle('active', isActive);
    });
  }

  function _updateBadge(count) {
    const badge = DOM.$('[data-jobs-badge]');
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count;
      DOM.show(badge);
    } else {
      DOM.hide(badge);
    }
  }

  return { init };
})();
