const fs = require('fs');
const path = require('path');
const { test } = require('@playwright/test');

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

    if (method === 'GET' && pathname === '/settings') return fulfillJson(route, { openrouter_api_keys: [] });
    if (method === 'POST' && pathname === '/settings') return fulfillJson(route, { ok: true });
    if (method === 'POST' && pathname === '/settings/test-openrouter-key') return fulfillJson(route, { ok: true, model_count: 1 });
    if (method === 'GET' && pathname === '/presets') return fulfillJson(route, { presets: {} });
    if (method === 'POST' && pathname === '/presets') return fulfillJson(route, { ok: true });
    if (method === 'DELETE' && pathname.startsWith('/presets/')) return fulfillJson(route, { ok: true });
    if (method === 'POST' && pathname === '/compare') return fulfillJson(route, { result: {} });

    if (method === 'GET' && pathname === '/ai/providers') {
      return fulfillJson(route, { openrouter: { available: true }, ollama: { available: true } });
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

test.describe('UI workflow validation matrix', () => {
  test.setTimeout(180000);
  test('all actionable controls trigger an observable workflow outcome', async ({ page, baseURL, browserName }) => {
    const appOrigin = new URL(baseURL || 'http://127.0.0.1:5000').origin;
    const requestLog = [];
    const evidence = [];

    page.on('dialog', async (dialog) => {
      try { await dialog.accept(); } catch {}
    });

    await installComprehensiveMocks(page, appOrigin, requestLog);

    for (const viewName of PAGES) {
      await gotoPage(page, viewName);
      const controls = await collectControls(page);
      if (!controls.length) {
        evidence.push({
          browser: browserName,
          page: viewName,
          selector: '(none)',
          label: '(no controls found)',
          status: 'MISSING',
          reason: 'No actionable controls were discovered in active view.',
          observed_requests: [],
          observed_effects: [],
          timestamp: new Date().toISOString(),
        });
        continue;
      }

      for (const control of controls) {
        const locator = page.locator(control.selector).first();
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

        const exists = (await locator.count()) > 0;
        if (!exists) {
          row.status = 'MISSING';
          row.reason = 'Control selector resolved to no element at execution time.';
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
        const hashBefore = await page.evaluate(() => location.hash);
        const startedAt = Date.now();

        try {
          await locator.scrollIntoViewIfNeeded();
          await locator.click({ timeout: 1200 });
          await page.waitForTimeout(120);

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
          if (modalOpened) row.observed_effects.push('modal-open');

          if (row.observed_effects.length) {
            row.status = 'PASS';
            row.reason = 'Trigger-to-end observable effect detected.';
          } else {
            row.status = 'MISSING';
            row.reason = 'No observable request/navigation/state/modal effect after click.';
          }
        } catch (err) {
          row.status = 'FAIL';
          row.reason = 'Unhandled click execution error.';
          row.error = err?.message || String(err);
        }

        evidence.push(row);
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
});
