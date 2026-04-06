/* =================================================================
   APP — page router, bootstrap
   Exposes: window.App
   Requires: DOM, AppState, Auth, Sidebar, Tabs
   ================================================================= */

window.App = (() => {
  const PAGE_TITLES = {
    'dashboard':    'Dashboard',
    'backtesting':  'Backtesting',
    'hyperopt':     'Hyperopt',
    'strategy-lab': 'Strategy Lab',
    'ai-diagnosis': 'AI Diagnosis',
    'jobs':         'Jobs',
    'results':      'Results',
    'settings':     'Settings',
  };

  const PAGE_MODULES = {
    'dashboard':    () => window.DashboardPage,
    'backtesting':  () => window.BacktestPage,
    'hyperopt':     () => window.HyperoptPage,
    'strategy-lab': () => window.StrategyLabPage,
    'ai-diagnosis': () => window.AIDiagPage,
    'jobs':         () => window.JobsPage,
    'results':      () => window.ResultsPage,
    'settings':     () => window.SettingsPage,
  };

  const _visited = new Set();
  let _current = null;

  function _pageFromHash() {
    const h = (location.hash || '').replace('#', '').trim().toLowerCase();
    return PAGE_TITLES[h] ? h : 'dashboard';
  }

  function navigate(page) {
    if (!PAGE_TITLES[page]) page = 'dashboard';
    if (page === _current) return;
    _current = page;

    DOM.$$('.page-view').forEach(v => v.classList.remove('active'));
    const view = DOM.$(`[data-view="${page}"]`);
    if (view) view.classList.add('active');

    const pageContent = DOM.$('[data-page-content]');
    if (pageContent) pageContent.scrollTop = 0;

    const title = DOM.$('[data-page-title]');
    if (title) title.textContent = PAGE_TITLES[page] || page;

    AppState.set('activePage', page);
    location.hash = page;

    const mod = PAGE_MODULES[page]?.();
    if (mod) {
      if (!_visited.has(page) && typeof mod.init === 'function') {
        _visited.add(page);
        mod.init();
      } else if (_visited.has(page) && typeof mod.refresh === 'function') {
        mod.refresh();
      }
    }
  }

  function _bindNavLinks() {
    DOM.$$('[data-nav-link]').forEach(link => {
      DOM.on(link, 'click', e => {
        e.preventDefault();
        navigate(link.dataset.page);
      });
    });
  }

  function _bindClock() {
    const el = DOM.$('[data-clock]');
    if (!el) return;
    const update = () => {
      const now = new Date();
      el.textContent = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    };
    update();
    setInterval(update, 30000);
  }

  function _bindStream() {
    AppState.subscribe('stream', msg => {
      const el = DOM.$('[data-stream]');
      if (el && msg) el.textContent = msg;
    });
  }

  function init() {
    ThemeManager?.init?.();
    Sidebar.init();
    Tabs.initAll();
    Auth.startPolling();

    _bindNavLinks();
    _bindClock();
    _bindStream();

    window.addEventListener('hashchange', () => navigate(_pageFromHash()));
    navigate(_pageFromHash());
  }

  document.addEventListener('DOMContentLoaded', init);

  return { navigate, refresh: () => navigate(_current) };
})();
