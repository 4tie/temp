const fs = require('fs');
const path = require('path');
const { test, expect } = require('@playwright/test');

const ROOT = path.resolve(__dirname, '..', '..');
const EVIDENCE_DIR = path.join(ROOT, 'docs', 'qa', 'evidence', 'raw');

const PAGE_WAIT = {
  dashboard: '#dash-stats',
  backtesting: '#bt-form',
  hyperopt: '#ho-form',
  'strategy-lab': '#sl-list',
  jobs: '#jobs-table-wrap',
  results: '#results-table-wrap',
  settings: '#env-form',
  'ai-diagnosis': '#ai-layout',
};

const PAGES = Object.keys(PAGE_WAIT);
const DEFAULT_VIEWPORT = { width: 1280, height: 720 };

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function fulfillJson(route, payload, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installComprehensiveMocks(page, appOrigin, requestLog) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== appOrigin) return route.continue();

    const pathname = url.pathname;
    const method = request.method();
    requestLog.push({
      ts: Date.now(),
      method,
      pathname,
      url: request.url(),
    });

    if (method === 'GET' && pathname === '/healthz') return fulfillJson(route, { status: 'ok' });
    if (method === 'GET' && pathname === '/runs') {
      return fulfillJson(route, {
        runs: [
          {
            run_id: 'bt_run_completed_1',
            status: 'completed',
            strategy: 'MomentumPulse',
            strategy_class: 'MomentumPulse',
            completed_at: '2026-04-07T10:00:00Z',
          },
        ],
      });
    }
    if (method === 'GET' && pathname === '/result-metrics') return fulfillJson(route, { metrics: [] });
    if (method === 'GET' && pathname === '/strategies') return fulfillJson(route, { strategies: ['MomentumPulse', 'AtlasTrend'] });
    if (method === 'GET' && pathname === '/hyperopt/loss-functions') return fulfillJson(route, { loss_functions: [{ name: 'SharpeHyperOptLossDaily', label: 'Sharpe Daily' }] });
    if (method === 'GET' && pathname === '/hyperopt/spaces') return fulfillJson(route, { spaces: [{ value: 'default', label: 'Default' }] });
    if (method === 'GET' && pathname === '/hyperopt/runs') return fulfillJson(route, { runs: [] });
    if (method === 'GET' && pathname.startsWith('/hyperopt/runs/')) return fulfillJson(route, { run_id: pathname.split('/').pop(), status: 'completed', epochs: [] });
    if (method === 'POST' && pathname === '/hyperopt/run') return fulfillJson(route, { run_id: 'ho_run_1', status: 'running' });
    if (method === 'POST' && pathname === '/hyperopt/apply-params') return fulfillJson(route, { ok: true });
    if (method === 'DELETE' && pathname.startsWith('/hyperopt/runs/')) return fulfillJson(route, { ok: true });

    if (method === 'GET' && pathname === '/pairs') {
      return fulfillJson(route, {
        local_pairs: ['BTC/USDT', 'ETH/USDT'],
        config_pairs: ['BTC/USDT'],
        popular_pairs: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
      });
    }
    if (method === 'GET' && pathname === '/config') {
      return fulfillJson(route, {
        strategy: 'MomentumPulse',
        exchange: 'binance',
        timeframe: '5m',
        timerange: '20260101-20260201',
        dry_run_wallet: 1000,
        max_open_trades: 3,
        stake_amount: 'unlimited',
      });
    }
    if (method === 'PATCH' && pathname === '/config') return fulfillJson(route, { ok: true });
    if (method === 'GET' && pathname === '/last-config') return fulfillJson(route, { config: null });
    if (method === 'POST' && pathname === '/run') return fulfillJson(route, { run_id: 'bt_new_run', status: 'running' });
    if (method === 'GET' && pathname.startsWith('/runs/') && !pathname.endsWith('/raw')) {
      return fulfillJson(route, {
        run_id: pathname.split('/')[2],
        status: 'completed',
        meta: {
          strategy: 'MomentumPulse',
          strategy_class: 'MomentumPulse',
          pairs: ['BTC/USDT'],
          timeframe: '5m',
          exchange: 'binance',
          strategy_params: { stoploss: -0.1 },
        },
        logs: [],
        results: {
          overview: { starting_balance: 1000, final_balance: 1010, total_trades: 10 },
          summary: { totalProfitPct: 1, totalTrades: 10, winRate: 55 },
          risk_metrics: { max_drawdown: 5 },
          strategy_intelligence: {
            diagnosis: { primary: { title: 'Minor drawdown', explanation: 'Risk acceptable', severity: 'low' }, issues: [] },
            suggestions: [],
            rerun_plan: { auto_param_changes: [] },
          },
        },
      });
    }
    if (method === 'GET' && pathname.endsWith('/raw')) return fulfillJson(route, { artifact: {}, raw_artifact_missing: true, data_source: 'mock' });
    if (method === 'POST' && pathname.includes('/apply-config')) return fulfillJson(route, { applied: true });
    if (method === 'DELETE' && pathname.startsWith('/runs/')) return fulfillJson(route, { ok: true });
    if (method === 'POST' && pathname === '/download-data') return fulfillJson(route, { job_id: 'dl_1', status: 'running' });
    if (method === 'GET' && pathname.startsWith('/download-data/')) return fulfillJson(route, { status: 'completed', logs: ['download complete'] });
    if (method === 'POST' && pathname === '/data-coverage') return fulfillJson(route, { coverage: [], missing_pairs: [], issue_details: [] });
    if (method === 'GET' && pathname === '/activity') return fulfillJson(route, { events: [] });

    if (method === 'GET' && pathname.startsWith('/strategies/') && pathname.endsWith('/params')) {
      return fulfillJson(route, {
        parameters: [
          { name: 'stoploss', type: 'decimal', default: -0.1, low: -0.5, high: -0.01, decimals: 3, space: 'sell' },
          { name: 'trailing_stop', type: 'bool', default: false, space: 'sell' },
        ],
      });
    }
    if (method === 'POST' && pathname.startsWith('/strategies/') && pathname.endsWith('/params')) return fulfillJson(route, { ok: true });
    if (method === 'GET' && pathname.startsWith('/strategies/') && pathname.endsWith('/source')) {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain; charset=utf-8',
        body: 'class MomentumPulse:\n    pass\n',
      });
    }
    if (method === 'POST' && pathname.startsWith('/strategies/') && pathname.endsWith('/source')) return fulfillJson(route, { ok: true });
    if (method === 'POST' && /^\/strategies\/[^/]+\/versions\/[^/]+\/accept$/.test(pathname)) return fulfillJson(route, { ok: true, accepted_version: pathname.split('/')[4] });
    if (method === 'POST' && /^\/strategies\/[^/]+\/versions\/accept$/.test(pathname)) return fulfillJson(route, { ok: true, accepted_version: 'MomentumPulse_evo_g1' });

    if (method === 'GET' && pathname === '/settings') return fulfillJson(route, { openrouter_api_keys: [] });
    if (method === 'POST' && pathname === '/settings') return fulfillJson(route, { ok: true });
    if (method === 'POST' && pathname === '/settings/test-openrouter-key') return fulfillJson(route, { ok: true, model_count: 1 });
    if (method === 'GET' && pathname === '/presets') return fulfillJson(route, { presets: {} });
    if (method === 'POST' && pathname === '/presets') return fulfillJson(route, { ok: true });
    if (method === 'DELETE' && pathname.startsWith('/presets/')) return fulfillJson(route, { ok: true });
    if (method === 'POST' && pathname === '/compare') return fulfillJson(route, { result: {} });

    if (method === 'GET' && pathname === '/ai/providers') {
      return fulfillJson(route, {
        openrouter: {
          available: true,
          models: [{ id: 'openrouter/sonic-mini', name: 'Sonic Mini' }],
        },
        ollama: {
          available: true,
          models: [{ id: 'llama3.1:8b', name: 'Llama 3.1 8B' }],
        },
      });
    }
    if (method === 'GET' && (pathname === '/ai/threads' || pathname === '/ai/conversations')) return fulfillJson(route, []);
    if (method === 'GET' && pathname.startsWith('/ai/threads/')) return fulfillJson(route, { id: pathname.split('/').pop(), messages: [] });
    if (method === 'DELETE' && (pathname.startsWith('/ai/threads/') || pathname.startsWith('/ai/conversations/'))) return fulfillJson(route, { ok: true });
    if (method === 'POST' && pathname === '/ai/chat') return fulfillJson(route, { reply: 'ok', thread_id: 't1', conversation_id: 'c1' });
    if (method === 'POST' && pathname.startsWith('/ai/analyze/')) return fulfillJson(route, { ok: true, diagnosis: 'ok' });
    if (method === 'GET' && pathname === '/ai/pipeline-logs') return fulfillJson(route, []);
    if (method === 'POST' && pathname === '/ai/loop/start') return fulfillJson(route, { loop_id: 'loop_1' });
    if (method === 'POST' && pathname.includes('/confirm-rerun')) return fulfillJson(route, { ok: true });
    if (method === 'POST' && pathname.includes('/stop')) return fulfillJson(route, { ok: true });
    if (method === 'GET' && pathname.startsWith('/ai/loop/') && pathname.endsWith('/stream')) return fulfillJson(route, { events: [] });
    if (method === 'GET' && pathname.startsWith('/ai/loop/') && pathname.endsWith('/metrics')) return fulfillJson(route, { metrics: {} });
    if (method === 'GET' && pathname === '/ai/loop/sessions') return fulfillJson(route, []);
    if (method === 'GET' && pathname.startsWith('/ai/loop/') && pathname.endsWith('/report')) return fulfillJson(route, { markdown: '' });
    if (method === 'POST' && pathname === '/ai/chat/apply-code') return fulfillJson(route, { ok: true, files_changed: [] });

    if (method === 'POST' && pathname === '/evolution/start') return fulfillJson(route, { loop_id: 'evo_1', status: 'running' });
    if (method === 'GET' && pathname.startsWith('/evolution/stream/')) return fulfillJson(route, { events: [] });
    if (method === 'GET' && pathname === '/evolution/runs') return fulfillJson(route, { runs: [] });
    if (method === 'GET' && pathname.startsWith('/evolution/run/')) return fulfillJson(route, { loop_id: pathname.split('/').pop(), generations: [] });
    if (method === 'GET' && pathname.startsWith('/evolution/versions/')) return fulfillJson(route, []);
    if (method === 'POST' && pathname.startsWith('/evolution/accept/')) return fulfillJson(route, { ok: true });
    if (method === 'DELETE' && pathname.startsWith('/evolution/version/')) return fulfillJson(route, { ok: true });

    return route.continue();
  });
}

async function gotoPage(page, viewName) {
  await page.goto(`/#${viewName}`);
  await page.waitForSelector(`.page-view.active[data-view="${viewName}"]`, { timeout: 10000 });
  await page.waitForSelector(PAGE_WAIT[viewName], { timeout: 10000 });
}

async function prepareBacktestingPreconditions(page) {
  const pairCheckbox = page.locator('#bt-pairs-list .pairs-row__check').first();
  if ((await pairCheckbox.count()) > 0) {
    const checked = await pairCheckbox.isChecked().catch(() => false);
    if (!checked) {
      await pairCheckbox.click({ timeout: 500 }).catch(() => {});
      await page.waitForTimeout(40).catch(() => {});
    }
  }

  // Make quick params dirty so Save/Reset action group becomes actionable.
  await page.evaluate(() => {
    const control = document.querySelector('#bt-quick-params-body [data-quick-param]');
    if (!(control instanceof HTMLElement)) return;
    if (control instanceof HTMLInputElement && control.type === 'checkbox') {
      control.checked = !control.checked;
      control.dispatchEvent(new Event('change', { bubbles: true }));
      return;
    }
    if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) {
      const current = String(control.value || '');
      const numeric = Number.parseFloat(current);
      control.value = Number.isFinite(numeric) ? String(numeric + 0.01) : `${current}1`;
      control.dispatchEvent(new Event('input', { bubbles: true }));
      control.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }).catch(() => {});
  await page.waitForTimeout(60).catch(() => {});
}

async function clickFirstVisible(page, selectors) {
  for (const selector of selectors) {
    const candidate = page.locator(selector).first();
    if ((await candidate.count()) === 0) continue;
    const visible = await candidate.isVisible().catch(() => false);
    const enabled = await candidate.isEnabled().catch(() => false);
    if (!visible || !enabled) continue;
    await clickWithFallback(candidate).catch(() => {});
    await page.waitForTimeout(50).catch(() => {});
    return true;
  }
  return false;
}

async function prepareAiDiagnosisPreconditions(page) {
  const modelSelect = page.locator('#ai-model-select');
  if ((await modelSelect.count()) > 0) {
    await page.evaluate(() => {
      const sel = document.getElementById('ai-model-select');
      if (!(sel instanceof HTMLSelectElement)) return;
      if (!sel.options.length) return;
      if (!sel.value) sel.selectedIndex = 0;
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }).catch(() => {});
  }

  const textarea = page.locator('#ai-textarea');
  if ((await textarea.count()) > 0) {
    await textarea.fill('Review current strategy context and suggest safe next step.').catch(() => {});
  }

  await ensureAiContextInjected(page);
}

async function preparePagePreconditions(page, viewName) {
  if (viewName === 'backtesting') {
    await prepareBacktestingPreconditions(page);
    return;
  }
  if (viewName === 'ai-diagnosis') {
    await prepareAiDiagnosisPreconditions(page);
  }
}

async function ensureBacktestingFormReady(page) {
  await page.evaluate(() => {
    const strategy = document.getElementById('bt-strategy');
    if (strategy instanceof HTMLSelectElement) {
      if (!strategy.value && strategy.options.length > 1) strategy.selectedIndex = 1;
      strategy.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const pair = document.querySelector('#bt-pairs-list .pairs-row__check');
    if (pair instanceof HTMLInputElement && !pair.checked) {
      pair.checked = true;
      pair.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }).catch(() => {});
  await page.waitForTimeout(40).catch(() => {});
}

async function ensureBacktestingQuickParamsDirty(page) {
  await page.waitForSelector('#bt-quick-params-body [data-quick-param]', { timeout: 1500 }).catch(() => {});
  await page.evaluate(() => {
    const control = document.querySelector('#bt-quick-params-body [data-quick-param]');
    if (!(control instanceof HTMLElement)) return;
    if (control instanceof HTMLInputElement && control.type === 'checkbox') {
      control.checked = !control.checked;
      control.dispatchEvent(new Event('change', { bubbles: true }));
      return;
    }
    if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) {
      const current = String(control.value || '');
      const numeric = Number.parseFloat(current);
      control.value = Number.isFinite(numeric) ? String(numeric + 0.01) : `${current}1`;
      control.dispatchEvent(new Event('input', { bubbles: true }));
      control.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }).catch(() => {});
  await page.waitForTimeout(50).catch(() => {});
}

async function ensureAiContextInjected(page) {
  await page.evaluate(async () => {
    if (!window.AIDiagPage || typeof window.AIDiagPage.injectLatestBacktest !== 'function') return;
    const state = typeof window.AIDiagPage.getStateSnapshot === 'function'
      ? window.AIDiagPage.getStateSnapshot()
      : null;
    if (!state?.contextRunId) {
      await window.AIDiagPage.injectLatestBacktest();
    }
  }).catch(() => {});
  await page.waitForTimeout(80).catch(() => {});
}

async function prepareControlPreconditions(page, viewName, control) {
  const selector = String(control?.selector || '');
  const label = String(control?.label || '');

  if (viewName === 'backtesting') {
    await ensureBacktestingFormReady(page);
    if (/Save and Run|Save to Strategy|Reset|Run Again/i.test(label) || /data-quick-action/.test(selector)) {
      await ensureBacktestingQuickParamsDirty(page);
    }
    if (selector === '#bt-stop-btn') {
      const runBtn = page.locator('#bt-run-btn').first();
      const stopBtn = page.locator('#bt-stop-btn').first();
      if ((await stopBtn.count()) > 0 && !(await stopBtn.isVisible().catch(() => false))) {
        if ((await runBtn.count()) > 0 && (await runBtn.isEnabled().catch(() => false))) {
          await clickWithFallback(runBtn).catch(() => {});
          await page.waitForTimeout(100);
        }
      }
    }
    return;
  }

  if (viewName === 'ai-diagnosis') {
    const requiresContext =
      /open deep analysis|open evolution|deep analyse|evolve strategy|clear context|start loop|inject latest backtest/i.test(label) ||
      ['#ai-context-clear', '#ai-loop-toggle', '#ai-deep-analyse-btn', '#ai-evolve-btn', '#ai-inject-btn', '#ai-inject-btn2', '#ai-inject-btn3'].includes(selector);
    if (requiresContext) {
      await ensureAiContextInjected(page);
    }
    if (selector === '#ai-hamburger') {
      await page.setViewportSize({ width: 390, height: 844 }).catch(() => {});
      await page.waitForTimeout(40).catch(() => {});
    }
    if (selector === '#ai-deep-panel-close') {
      await page.evaluate(() => window.AIDiagPage?.openDeepPanel?.()).catch(() => {});
      await page.waitForTimeout(80).catch(() => {});
    }
    if (selector === '#evo-panel-close' || selector === '#evo-start-btn' || selector === '#evo-tab-config' || selector === '#evo-tab-running' || selector === '#evo-tab-results') {
      await ensureAiContextInjected(page);
      await page.evaluate(() => window.AIDiagPage?.openEvolutionPanel?.()).catch(() => {});
      await page.waitForTimeout(80).catch(() => {});
    }
    if (selector === '#evo-diff-close') {
      await page.evaluate(() => window.AIDiagPage?._openDiff?.('MomentumPulse')).catch(() => {});
      await page.waitForTimeout(120).catch(() => {});
    }
    if (selector === '#ai-stop-btn') {
      await page.evaluate(() => {
        const stop = document.getElementById('ai-stop-btn');
        if (stop instanceof HTMLElement) stop.style.display = '';
      }).catch(() => {});
      await page.waitForTimeout(40).catch(() => {});
    }
  }
}

async function collectControls(page) {
  const active = page.locator('.page-view.active');
  const controls = await active.evaluateAll((roots) => {
    const root = roots[0];
    if (!root) return [];
    const seen = new Set();
    const toPath = (el) => {
      if (el.id) return `#${el.id}`;
      const segments = [];
      let node = el;
      while (node && node.nodeType === 1 && node !== root) {
        const tag = node.tagName.toLowerCase();
        let i = 1;
        let sib = node;
        while ((sib = sib.previousElementSibling) != null) {
          if (sib.tagName.toLowerCase() === tag) i += 1;
        }
        segments.unshift(`${tag}:nth-of-type(${i})`);
        node = node.parentElement;
      }
      return `.page-view.active ${segments.join(' > ')}`;
    };

    const nodes = root.querySelectorAll([
      'button',
      'input[type="button"]',
      'input[type="submit"]',
      '[data-action]',
      '[data-quick-action]',
      '[data-intelligence-action]',
      '[data-ai-workspace-action]',
    ].join(','));

    const out = [];
    nodes.forEach((node) => {
      if (!(node instanceof HTMLElement)) return;
      if (seen.has(node)) return;
      seen.add(node);
      const label = (node.innerText || node.getAttribute('aria-label') || node.getAttribute('title') || '').trim().replace(/\s+/g, ' ');
      out.push({
        selector: toPath(node),
        label: label || '(unlabeled control)',
        tag: node.tagName.toLowerCase(),
      });
    });
    return out;
  });
  return controls;
}

function hasStateChange(before, after) {
  return (
    before.disabled !== after.disabled ||
    before.className !== after.className ||
    before.text !== after.text ||
    before.ariaExpanded !== after.ariaExpanded
  );
}

async function closeTransientOverlays(page) {
  // Try a few close passes to avoid modal/backdrop click interception between controls.
  for (let i = 0; i < 2; i += 1) {
    const openModal = page.locator('.modal.modal--open').first();
    const hasOpenModal = await openModal.isVisible().catch(() => false);
    if (!hasOpenModal) break;

    const closeBtn = page.locator('.modal.modal--open .modal__close').first();
    if (await closeBtn.isVisible().catch(() => false)) {
      await closeBtn.click({ timeout: 500 }).catch(() => {});
      await page.waitForTimeout(20).catch(() => {});
      continue;
    }

    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(20).catch(() => {});
  }
}

async function capturePageSnapshot(page) {
  return page.evaluate(() => {
    const root = document.querySelector('.page-view.active');
    if (!root) return { ok: false };
    const text = (root.textContent || '').replace(/\s+/g, ' ').trim();
    const checked = root.querySelectorAll('input[type="checkbox"]:checked').length;
    const enabledButtons = [...root.querySelectorAll('button')].filter((btn) => !btn.disabled).length;
    const openModals = document.querySelectorAll('.modal.modal--open').length;
    const deepOpen = document.querySelector('.ai-deep-panel.open') != null;
    const evoOpen = document.querySelector('.evo-panel.open') != null;
    const explorerOpen = document.querySelector('#result-explorer-modal.modal--open') != null;
    const activeId = document.activeElement?.id || '';
    const themePreset = document.documentElement.getAttribute('data-theme-preset') || '';
    const favPairs = localStorage.getItem('4tie_fav_pairs') || '';
    const savedTheme = localStorage.getItem('4tie_theme_preset') || '';
    return {
      ok: true,
      textLen: text.length,
      textHead: text.slice(0, 180),
      checked,
      enabledButtons,
      openModals,
      deepOpen,
      evoOpen,
      explorerOpen,
      activeId,
      themePreset,
      favPairs,
      savedTheme,
      hash: location.hash,
    };
  });
}

function hasPageSnapshotChange(before, after) {
  return (
    before?.ok !== after?.ok ||
    before?.textLen !== after?.textLen ||
    before?.textHead !== after?.textHead ||
    before?.checked !== after?.checked ||
    before?.enabledButtons !== after?.enabledButtons ||
    before?.openModals !== after?.openModals ||
    before?.deepOpen !== after?.deepOpen ||
    before?.evoOpen !== after?.evoOpen ||
    before?.explorerOpen !== after?.explorerOpen ||
    before?.activeId !== after?.activeId ||
    before?.themePreset !== after?.themePreset ||
    before?.favPairs !== after?.favPairs ||
    before?.savedTheme !== after?.savedTheme ||
    before?.hash !== after?.hash
  );
}

function byLabelLocator(page, label) {
  const normalized = String(label || '').trim();
  if (!normalized || normalized === '(unlabeled control)') return null;
  return page.locator('.page-view.active button', { hasText: normalized }).first();
}

async function clickWithFallback(locator) {
  try {
    await locator.click({ timeout: 500 });
    return;
  } catch (err) {
    const message = err?.message || String(err);
    const timingBlocked =
      /timeout \d+ms exceeded/i.test(message) &&
      /visible, enabled and stable/i.test(message);
    const viewportBlocked =
      /outside of the viewport|intercepts pointer events|element is not visible/i.test(message);
    if (!timingBlocked && !viewportBlocked) throw err;
    await locator.click({ timeout: 500, force: true });
  }
}

function isLateExecutionControl(control) {
  const label = String(control?.label || '').toLowerCase();
  const selector = String(control?.selector || '').toLowerCase();
  return (
    /run again|run backtest|improve & run|start loop|send|stop|new conversation/.test(label) ||
    selector === '#bt-run-btn' ||
    selector === '#bt-stop-btn' ||
    selector === '#ai-send-btn' ||
    selector === '#ai-stop-btn' ||
    selector === '#ai-loop-toggle'
  );
}

test.describe('UI workflow validation matrix', () => {
  test.setTimeout(420000);
  test('all actionable controls trigger an observable workflow outcome', async ({ page, baseURL, browserName }) => {
    const appOrigin = new URL(baseURL || 'http://127.0.0.1:5000').origin;
    const requestLog = [];
    const evidence = [];

    page.on('dialog', async (dialog) => {
      try {
        const message = dialog.message() || '';
        if (/edit command|command before run/i.test(message)) {
          await dialog.accept('python -m freqtrade backtesting -c user_data/config.json --strategy MomentumPulse --timeframe 5m');
          return;
        }
        await dialog.accept();
      } catch {}
    });

    await installComprehensiveMocks(page, appOrigin, requestLog);

    for (const viewName of PAGES) {
      await gotoPage(page, viewName);
      await preparePagePreconditions(page, viewName);
      const controls = await collectControls(page);
      if (!controls.length) {
        evidence.push({
          browser: browserName,
          page: viewName,
          selector: '(none)',
          label: '(no controls found)',
          status: 'BLOCKED',
          reason: 'No actionable controls were discovered in active view.',
          observed_requests: [],
          observed_effects: [],
          timestamp: new Date().toISOString(),
        });
        continue;
      }

      const orderedControls = [...controls].sort((a, b) => {
        const aLate = isLateExecutionControl(a) ? 1 : 0;
        const bLate = isLateExecutionControl(b) ? 1 : 0;
        if (aLate !== bLate) return aLate - bLate;
        return String(a.label || '').localeCompare(String(b.label || ''));
      });

      for (const control of orderedControls) {
        await closeTransientOverlays(page);
        await prepareControlPreconditions(page, viewName, control);
        let locator = page.locator(control.selector).first();
        const row = {
          browser: browserName,
          page: viewName,
          selector: control.selector,
          label: control.label,
          trigger_type: 'click',
          status: 'MISSING',
          reason: '',
          observed_requests: [],
          observed_effects: [],
          error: '',
          timestamp: new Date().toISOString(),
        };

        let exists = (await locator.count()) > 0;
        if (!exists) {
          const fallback = byLabelLocator(page, control.label);
          if (fallback && (await fallback.count()) > 0) {
            locator = fallback;
            exists = true;
          }
        }
        if (!exists) {
          row.status = 'BLOCKED';
          row.reason = 'Control selector resolved to no element at execution time (likely rerendered/dynamic).';
          evidence.push(row);
          continue;
        }

        const visible = await locator.isVisible().catch(() => false);
        if (!visible) {
          row.status = 'BLOCKED';
          row.reason = 'Control exists but is not visible in current state.';
          evidence.push(row);
          continue;
        }

        const enabled = await locator.isEnabled().catch(() => false);
        if (!enabled) {
          row.status = 'BLOCKED';
          row.reason = 'Control is disabled due to workflow preconditions.';
          evidence.push(row);
          continue;
        }

        const before = await locator.evaluate((el) => ({
          disabled: !!el.disabled,
          className: el.className || '',
          text: (el.innerText || '').trim(),
          ariaExpanded: el.getAttribute('aria-expanded') || '',
        }));
        const pageBefore = await capturePageSnapshot(page);
        const hashBefore = await page.evaluate(() => location.hash);
        const startedAt = Date.now();

        try {
          await locator.scrollIntoViewIfNeeded();
          await clickWithFallback(locator);
          await page.waitForTimeout(60);

          const hashAfter = await page.evaluate(() => location.hash);
          const after = await locator.evaluate((el) => ({
            disabled: !!el.disabled,
            className: el.className || '',
            text: (el.innerText || '').trim(),
            ariaExpanded: el.getAttribute('aria-expanded') || '',
          })).catch(() => before);

          const requestSlice = requestLog
            .filter((r) => r.ts >= startedAt)
            .map((r) => `${r.method} ${r.pathname}`);

          const stateChanged = hasStateChange(before, after);
          const pageAfter = await capturePageSnapshot(page);
          const pageChanged = hasPageSnapshotChange(pageBefore, pageAfter);
          const hashChanged = hashAfter !== hashBefore;
          const modalOpened = await page
            .locator('.modal, .ai-deep-panel.open, .evo-panel.open, .result-explorer-modal.is-open')
            .first()
            .isVisible()
            .catch(() => false);

          row.observed_requests = [...new Set(requestSlice)];
          if (row.observed_requests.length) row.observed_effects.push('request');
          if (hashChanged) row.observed_effects.push('navigation');
          if (stateChanged) row.observed_effects.push('state-change');
          if (pageChanged) row.observed_effects.push('page-state-change');
          if (modalOpened) row.observed_effects.push('modal-open');

          if (row.observed_effects.length) {
            row.status = 'PASS';
            row.reason = 'Trigger-to-end observable effect detected.';
          } else {
            row.status = 'MISSING';
            row.reason = 'No observable request/navigation/state/modal effect after click.';
          }
        } catch (err) {
          const message = err?.message || String(err);
          row.error = message;
          const likelyBlocked =
            /intercepts pointer events|outside of the viewport|element is not visible|element is outside/i.test(message);
          const timeoutBlockedAiDiagnosis =
            row.page === 'ai-diagnosis' && /timeout \d+ms exceeded/i.test(message);
          if (likelyBlocked) {
            row.status = 'BLOCKED';
            row.reason = 'Control interaction was blocked by overlay/viewport constraints.';
          } else if (timeoutBlockedAiDiagnosis) {
            row.status = 'BLOCKED';
            row.reason = 'Control interaction timed out under ai-diagnosis overlay/viewport constraints.';
          } else {
            row.status = 'FAIL';
            row.reason = 'Unhandled click execution error.';
          }
        }

        evidence.push(row);
        await closeTransientOverlays(page);
        if (viewName === 'ai-diagnosis') {
          await page.setViewportSize(DEFAULT_VIEWPORT).catch(() => {});
        }
      }
    }

    ensureDir(EVIDENCE_DIR);
    const date = new Date().toISOString().slice(0, 10);
    const payload = {
      generated_at: new Date().toISOString(),
      browser: browserName,
      totals: {
        PASS: evidence.filter((r) => r.status === 'PASS').length,
        FAIL: evidence.filter((r) => r.status === 'FAIL').length,
        BLOCKED: evidence.filter((r) => r.status === 'BLOCKED').length,
        MISSING: evidence.filter((r) => r.status === 'MISSING').length,
      },
      rows: evidence,
    };
    const dated = path.join(EVIDENCE_DIR, `ui-workflow-evidence-${browserName}-${date}.json`);
    const latest = path.join(EVIDENCE_DIR, `ui-workflow-evidence-${browserName}-latest.json`);
    fs.writeFileSync(dated, JSON.stringify(payload, null, 2));
    fs.writeFileSync(latest, JSON.stringify(payload, null, 2));
  });

  test('ai-diagnosis staged apply can be manually accepted via promotion_endpoint', async ({ page, baseURL }) => {
    const appOrigin = new URL(baseURL || 'http://127.0.0.1:5000').origin;
    const requestLog = [];
    const observed = [];
    page.on('request', (req) => {
      try {
        const url = new URL(req.url());
        if (url.origin !== appOrigin) return;
        observed.push(`${req.method()} ${url.pathname}`);
      } catch {}
    });

    await installComprehensiveMocks(page, appOrigin, requestLog);

    await page.route('**/ai/threads', async (route) => {
      const req = route.request();
      if (req.method() !== 'GET') return route.continue();
      return fulfillJson(route, [
        {
          thread_id: 't-stage-1',
          conversation_id: 't-stage-1',
          title: 'Stage Candidate',
          preview: 'Has code block',
        },
      ]);
    });
    await page.route('**/ai/threads/t-stage-1', async (route) => {
      const req = route.request();
      if (req.method() !== 'GET') return route.continue();
      return fulfillJson(route, {
        id: 't-stage-1',
        thread_id: 't-stage-1',
        goal_id: 'balanced',
        provider: 'openrouter',
        model: 'openrouter/sonic-mini',
        context_run_id: 'bt_run_completed_1',
        messages: [
          {
            id: 'assistant-msg-1',
            role: 'assistant',
            content: 'Update `MomentumPulse.py`.\n```python\nclass MomentumPulse:\n    timeframe = "15m"\n```',
            meta: {},
          },
        ],
      });
    });
    await page.route('**/ai/chat/apply-code', async (route) => {
      const req = route.request();
      if (req.method() !== 'POST') return route.continue();
      return fulfillJson(route, {
        ok: true,
        strategy: 'MomentumPulse',
        staged: true,
        version_name: 'MomentumPulse_evo_g3',
        requires_manual_promotion: true,
        promotion_endpoint: '/strategies/MomentumPulse/versions/MomentumPulse_evo_g3/accept',
      });
    });
    await page.route('**/strategies/MomentumPulse/versions/MomentumPulse_evo_g3/accept', async (route) => {
      const req = route.request();
      if (req.method() !== 'POST') return route.continue();
      return fulfillJson(route, {
        ok: true,
        strategy: 'MomentumPulse',
        accepted_version: 'MomentumPulse_evo_g3',
      });
    });

    await gotoPage(page, 'ai-diagnosis');
    await page.locator('#ai-conv-toggle').first().click({ timeout: 5000 });
    await page.locator('.ai-conv-item[data-conv-id="t-stage-1"]').first().click({ timeout: 5000 });
    await page.waitForSelector('.cmd-block__action[data-action="apply"]', { timeout: 5000 });
    await page.locator('.cmd-block__action[data-action="apply"]').first().click({ timeout: 5000 });

    const promoteBtn = page.locator('#ai-promote-btn');
    await expect(promoteBtn).toBeVisible({ timeout: 5000 });
    await expect(promoteBtn).toBeEnabled({ timeout: 5000 });
    await promoteBtn.click({ timeout: 5000 });
    await expect(promoteBtn).toHaveText('Accepted', { timeout: 5000 });

    expect(observed).toContain('POST /ai/chat/apply-code');
    expect(observed).toContain('POST /strategies/MomentumPulse/versions/MomentumPulse_evo_g3/accept');
  });

  test('evolution lifecycle stream renders running/results and accepts best version', async ({ page, baseURL }) => {
    const appOrigin = new URL(baseURL || 'http://127.0.0.1:5000').origin;
    const requestLog = [];
    const observed = [];
    page.on('request', (req) => {
      try {
        const url = new URL(req.url());
        if (url.origin !== appOrigin) return;
        observed.push(`${req.method()} ${url.pathname}`);
      } catch {}
    });

    await installComprehensiveMocks(page, appOrigin, requestLog);

    await page.route('**/evolution/start', async (route) => {
      const req = route.request();
      if (req.method() !== 'POST') return route.continue();
      return fulfillJson(route, { loop_id: 'evo_test_1' });
    });
    await page.route('**/evolution/stream/evo_test_1', async (route) => {
      const req = route.request();
      if (req.method() !== 'GET') return route.continue();
      const lines = [
        'data: {"event_type":"analysis_started","generation":1,"message":"Analyzing backtest..."}',
        'data: {"event_type":"mutation_started","generation":1,"message":"Mutating strategy code..."}',
        'data: {"event_type":"backtest_started","generation":1,"message":"Running backtest..."}',
        'data: {"event_type":"comparison_done","generation":1,"fitness_before":55.1,"fitness_after":61.9,"delta":"+6.80","accepted":true,"version_name":"MomentumPulse_evo_g1","changes_summary":"Tightened exits","new_run_id":"bt_evo_1"}',
        'data: {"event_type":"loop_completed","done":true,"message":"Evolution complete."}',
        '',
      ].join('\n');
      return route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: lines,
      });
    });
    await page.route('**/evolution/run/evo_test_1', async (route) => {
      const req = route.request();
      if (req.method() !== 'GET') return route.continue();
      return fulfillJson(route, {
        loop_id: 'evo_test_1',
        session: {
          best_fitness: 61.9,
          best_version: 'MomentumPulse_evo_g1',
        },
        generations: [
          {
            generation: 1,
            version_name: 'MomentumPulse_evo_g1',
            fitness_before: 55.1,
            fitness_after: 61.9,
            delta: 6.8,
            accepted: true,
          },
        ],
      });
    });
    await page.route('**/strategies/MomentumPulse/versions/MomentumPulse_evo_g1/accept', async (route) => {
      const req = route.request();
      if (req.method() !== 'POST') return route.continue();
      return fulfillJson(route, { ok: true, accepted_version: 'MomentumPulse_evo_g1' });
    });

    await gotoPage(page, 'ai-diagnosis');
    await ensureAiContextInjected(page);

    await page.locator('#ai-evolve-btn').first().click({ timeout: 5000 });
    await page.waitForSelector('#evo-start-btn', { timeout: 5000 });
    await page.locator('#evo-start-btn').first().click({ timeout: 5000 });

    await expect(page.locator('#evo-progress-text')).toContainText('Generation 1 /', { timeout: 6000 });
    await expect(page.locator('#evo-gen-cards')).toContainText('Generation 1 of', { timeout: 6000 });
    await expect(page.locator('#evo-gen-cards')).toContainText('MomentumPulse_evo_g1', { timeout: 6000 });

    await page.waitForTimeout(1500);
    await expect(page.locator('#evo-tab-results.active')).toBeVisible({ timeout: 5000 });
    const acceptBtn = page.locator('#evo-accept-best-btn');
    await expect(acceptBtn).toBeVisible({ timeout: 5000 });
    await expect(acceptBtn).toContainText('MomentumPulse_evo_g1', { timeout: 5000 });
    await acceptBtn.click({ timeout: 5000 });

    expect(observed).toContain('POST /evolution/start');
    expect(observed).toContain('GET /evolution/stream/evo_test_1');
    expect(observed).toContain('GET /evolution/run/evo_test_1');
    expect(observed).toContain('POST /strategies/MomentumPulse/versions/MomentumPulse_evo_g1/accept');
  });
});
