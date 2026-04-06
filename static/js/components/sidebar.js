/* =================================================================
   SIDEBAR — collapse toggle, active link, jobs badge
   Exposes: window.Sidebar
   Requires: window.DOM, window.AppState
   ================================================================= */

window.Sidebar = (() => {
  const STORAGE_KEY = '4tie_sidebar_collapsed';

  function init() {
    const shell = DOM.$('[data-app-shell]');
    const toggle = DOM.$('[data-sidebar-toggle]');
    const openBtn = DOM.$('[data-sidebar-open]');
    const overlay = DOM.$('[data-sidebar-overlay]');
    const mobileQuery = window.matchMedia('(max-width: 768px)');

    if (!shell || !toggle) return;

    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'true' && !mobileQuery.matches) shell.classList.add('sidebar-collapsed');

    DOM.on(toggle, 'click', () => {
      if (mobileQuery.matches) {
        shell.classList.remove('sidebar-open');
        return;
      }
      const collapsed = shell.classList.toggle('sidebar-collapsed');
      localStorage.setItem(STORAGE_KEY, collapsed ? 'true' : 'false');
    });

    if (openBtn) {
      DOM.on(openBtn, 'click', () => {
        if (mobileQuery.matches) {
          shell.classList.add('sidebar-open');
        }
      });
    }

    if (overlay) {
      DOM.on(overlay, 'click', () => shell.classList.remove('sidebar-open'));
    }

    DOM.$$('[data-nav-link]').forEach(link => {
      DOM.on(link, 'click', () => {
        if (mobileQuery.matches) {
          shell.classList.remove('sidebar-open');
        }
      });
    });

    const syncResponsiveState = event => {
      if (event.matches) {
        shell.classList.remove('sidebar-collapsed');
      } else {
        shell.classList.remove('sidebar-open');
        if (localStorage.getItem(STORAGE_KEY) === 'true') {
          shell.classList.add('sidebar-collapsed');
        }
      }
    };

    if (typeof mobileQuery.addEventListener === 'function') {
      mobileQuery.addEventListener('change', syncResponsiveState);
    } else if (typeof mobileQuery.addListener === 'function') {
      mobileQuery.addListener(syncResponsiveState);
    }

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
