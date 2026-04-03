/* =================================================================
   AI DIAGNOSIS PAGE — placeholder
   Exposes: window.AIDiagPage
   ================================================================= */

window.AIDiagPage = (() => {
  function init() {
    const el = DOM.$('[data-view="ai-diagnosis"]');
    if (!el) return;
    DOM.setHTML(el, `
      <div class="page-header">
        <h1 class="page-header__title">AI Diagnosis</h1>
        <p class="page-header__subtitle">Intelligent analysis and recommendations for your strategies.</p>
      </div>
      <div class="card">
        <div class="card__body">
          <div class="empty-state" style="padding:var(--space-12) 0">
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color:var(--violet);margin-bottom:var(--space-4)">
              <path d="M12 2a6 6 0 0 1 6 6c0 2.5-1.5 4.5-3.5 5.5V17H9.5v-3.5C7.5 12.5 6 10.5 6 8a6 6 0 0 1 6-6z"/>
              <line x1="9.5" y1="17" x2="14.5" y2="17"/>
              <line x1="9.5" y1="19" x2="14.5" y2="19"/>
              <line x1="10" y1="8" x2="14" y2="8"/>
              <line x1="12" y1="6" x2="12" y2="10"/>
            </svg>
            <p class="text-secondary" style="font-size:var(--text-md)">AI Diagnosis coming soon</p>
            <p class="text-muted" style="max-width:420px;margin:var(--space-2) auto 0">
              This module will analyze your backtest results, identify weaknesses in your strategies,
              and provide actionable optimization recommendations.
            </p>
          </div>
        </div>
      </div>
    `);
  }

  return { init };
})();
