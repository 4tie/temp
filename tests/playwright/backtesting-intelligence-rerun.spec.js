const { test, expect } = require('@playwright/test');

const APP_ORIGIN = 'http://127.0.0.1:8000';
const LOADED_RUN_ID = 'run_prev_1';
const RERUN_ID = 'run_rerun_1';

function fulfillJson(route, payload, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function buildCompletedRunPayload() {
  return {
    run_id: LOADED_RUN_ID,
    status: 'completed',
    meta: {
      strategy: 'Test Strategy Label',
      strategy_class: 'TestStrategy',
      pairs: ['BTC/USDT'],
      timeframe: '5m',
      timerange: '20250101-20250131',
      exchange: 'binance',
      strategy_path: null,
      strategy_params: {
        stoploss: -0.15,
        trailing_stop: false,
      },
      dry_run_wallet: 1000,
      max_open_trades: 3,
      stake_amount: 'unlimited',
    },
    logs: [],
    results: {
      overview: {
        starting_balance: 1000,
        final_balance: 920,
        total_trades: 40,
      },
      summary: {
        startingBalance: 1000,
        finalBalance: 920,
        totalProfit: -80,
        totalProfitPct: -8,
        totalTrades: 40,
        winRate: 42.5,
        maxDrawdown: 18,
      },
      risk_metrics: {
        max_drawdown: 18,
      },
      strategy_intelligence: {
        summary: {
          net_profit_pct: -8,
          total_trades: 40,
          win_rate: 42.5,
          max_drawdown: 18,
        },
        diagnosis: {
          primary: {
            id: 'high_loss_rate',
            title: 'High Loss Rate',
            explanation: 'Entries are poorly timed.',
            severity: 'critical',
            evidence: 'Win rate is below breakeven threshold.',
            confidence: 'high',
            confidence_note: 'Based on 40 trade(s) — high statistical confidence',
            metric_snapshot: {
              total_trades: 40,
              win_rate_pct: 42.5,
              profit_factor: 0.92,
              total_profit_pct: -8,
            },
          },
          issues: [
            {
              id: 'high_loss_rate',
              title: 'High Loss Rate',
              severity: 'critical',
              explanation: 'Primary issue',
            },
          ],
        },
        suggestions: [
          {
            id: 'param-1',
            title: 'Tighten stoploss',
            action_type: 'quick_param',
            auto_applicable: true,
            parameter: 'stoploss',
            suggested_value: -0.08,
            apply_action: {
              suggestion_id: 'param-1',
              action_type: 'quick_param',
              label: 'Apply',
              target: { parameter: 'stoploss', value: -0.08 },
            },
          },
          {
            id: 'param-2',
            title: 'Enable trailing stop',
            action_type: 'quick_param',
            auto_applicable: true,
            parameter: 'trailing_stop',
            suggested_value: true,
            apply_action: {
              suggestion_id: 'param-2',
              action_type: 'quick_param',
              label: 'Apply',
              target: { parameter: 'trailing_stop', value: true },
            },
          },
          {
            id: 'fix-1',
            title: 'Manual follow-up',
            action_type: 'manual_guidance',
            auto_applicable: false,
            description: 'Refine entry conditions.',
            apply_action: {
              suggestion_id: 'fix-1',
              action_type: 'manual_guidance',
              label: 'Apply',
              ai_apply_payload: { title: 'Manual follow-up' },
            },
          },
        ],
        rerun_plan: {
          auto_param_changes: [
            { name: 'stoploss', value: -0.08 },
            { name: 'trailing_stop', value: true },
          ],
          manual_actions: ['Refine entry conditions'],
        },
      },
    },
  };
}

async function installBacktestingMocks(page, { strategyParamsDelayMs = 0, dataCoverageDelayMs = 0, includeActiveRun = false } = {}) {
  const startBacktestBodies = [];
  const applySuggestionBodies = [];
  const completedRun = buildCompletedRunPayload();

  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== APP_ORIGIN) return route.continue();

    const { pathname } = url;
    const method = request.method();

    if (method === 'GET' && pathname === '/runs') {
      const runs = [
        {
          run_id: LOADED_RUN_ID,
          status: 'completed',
          completed_at: '2026-04-06T10:00:00Z',
        },
      ];
      if (includeActiveRun) {
        runs.push({
          run_id: RERUN_ID,
          status: 'running',
          started_at: '2026-04-06T10:05:00Z',
        });
      }
      return fulfillJson(route, { runs });
    }

    if (method === 'GET' && pathname === `/runs/${LOADED_RUN_ID}`) {
      return fulfillJson(route, completedRun);
    }

    if (method === 'GET' && pathname === `/runs/${RERUN_ID}`) {
      return fulfillJson(route, {
        run_id: RERUN_ID,
        status: 'running',
        meta: { strategy: 'TestStrategy' },
        logs: [],
      });
    }

    if (method === 'GET' && pathname === '/result-metrics') {
      return fulfillJson(route, { metrics: [] });
    }

    if (method === 'GET' && pathname === '/strategies') {
      return fulfillJson(route, { strategies: ['TestStrategy'] });
    }

    if (method === 'GET' && pathname === '/last-config') {
      return fulfillJson(route, { config: null });
    }

    if (method === 'GET' && pathname === '/config') {
      return fulfillJson(route, {
        strategy: 'TestStrategy',
        max_open_trades: 3,
        dry_run_wallet: 1000,
        stake_amount: 'unlimited',
        timeframe: '5m',
      });
    }

    if (method === 'GET' && pathname === '/pairs') {
      return fulfillJson(route, {
        local_pairs: ['BTC/USDT'],
        config_pairs: ['BTC/USDT'],
        popular_pairs: ['BTC/USDT'],
      });
    }

    if (method === 'GET' && pathname === '/hyperopt/runs') {
      return fulfillJson(route, { runs: [] });
    }

    if (method === 'GET' && pathname === '/activity') {
      return fulfillJson(route, { events: [] });
    }

    if (method === 'GET' && pathname === '/strategies/TestStrategy/params') {
      if (strategyParamsDelayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, strategyParamsDelayMs));
      }
      return fulfillJson(route, {
        parameters: [
          {
            name: 'stoploss',
            type: 'decimal',
            default: -0.15,
            low: -0.5,
            high: -0.01,
            decimals: 3,
            space: 'sell',
          },
          {
            name: 'trailing_stop',
            type: 'bool',
            default: false,
            space: 'sell',
          },
        ],
      });
    }

    if (method === 'POST' && pathname === '/data-coverage') {
      if (dataCoverageDelayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, dataCoverageDelayMs));
      }
      return fulfillJson(route, {
        coverage: [],
        missing_pairs: [],
        issue_details: [],
      });
    }

    if (method === 'POST' && pathname === `/runs/${LOADED_RUN_ID}/apply-suggestion`) {
      const body = request.postDataJSON();
      applySuggestionBodies.push(body);
      const suggestionId = body.suggestion_id;
      if (suggestionId === 'param-1') {
        return fulfillJson(route, {
          ok: true,
          suggestion_id: 'param-1',
          action_type: 'quick_param',
          applied_changes: ['stoploss: -0.15 -> -0.08'],
          diff_summary: { preview: ['-  "stoploss": -0.15', '+  "stoploss": -0.08'] },
          warnings: [],
          strategy_name: 'TestStrategy',
          strategy_params: { stoploss: -0.08, trailing_stop: false },
          source_changed: false,
          retest_payload: {
            strategy: 'TestStrategy',
            pairs: ['BTC/USDT'],
            timeframe: '5m',
            timerange: '20250101-20250131',
            exchange: 'binance',
            parent_run_id: LOADED_RUN_ID,
            improvement_source: 'strategy_intelligence_apply',
            improvement_items: ['Tighten stoploss'],
            improvement_applied: ['Tighten stoploss'],
            improvement_skipped: [],
            improvement_brief: 'Reduce loss size',
            strategy_params: { stoploss: -0.08, trailing_stop: false },
          },
        });
      }
      return fulfillJson(route, {
        ok: true,
        suggestion_id: suggestionId,
        action_type: 'manual_guidance',
        applied_changes: ['Updated TestStrategy.py from AI guidance.'],
        diff_summary: { preview: ['-    enter_tag = "base"', '+    enter_tag = "refined"'] },
        warnings: [],
        strategy_name: 'TestStrategy',
        strategy_params: { stoploss: -0.15, trailing_stop: false },
        source_changed: true,
        retest_payload: {
          strategy: 'TestStrategy',
          pairs: ['BTC/USDT'],
          timeframe: '5m',
          timerange: '20250101-20250131',
          exchange: 'binance',
          parent_run_id: LOADED_RUN_ID,
          improvement_source: 'strategy_intelligence_apply',
          improvement_items: ['Manual follow-up'],
          improvement_applied: ['Manual follow-up'],
          improvement_skipped: [],
          improvement_brief: 'Refine entry conditions.',
          strategy_params: { stoploss: -0.15, trailing_stop: false },
        },
      });
    }

    if (method === 'POST' && pathname === '/run') {
      startBacktestBodies.push(request.postDataJSON());
      return fulfillJson(route, { run_id: RERUN_ID, status: 'running' });
    }

    return route.continue();
  });

  return {
    getStartBacktestBodies: () => startBacktestBodies,
    getApplySuggestionBodies: () => applySuggestionBodies,
  };
}

test.describe('Backtesting Strategy Intelligence rerun', () => {
  test('core app + AI pipeline endpoints are healthy', async ({ request }) => {
    const health = await request.get('/healthz');
    expect(health.ok()).toBeTruthy();

    const threads = await request.get('/ai/threads');
    expect(threads.ok()).toBeTruthy();
    const threadPayload = await threads.json();
    expect(Array.isArray(threadPayload)).toBeTruthy();

    const logs = await request.get('/ai/pipeline-logs');
    expect(logs.ok()).toBeTruthy();
    const logsPayload = await logs.json();
    expect(Array.isArray(logsPayload)).toBeTruthy();
    if (logsPayload.length > 0) {
      const first = logsPayload[0];
      expect(typeof first).toBe('object');
      expect(first).toHaveProperty('pipeline_type');
      expect(first).toHaveProperty('steps');
      expect(first).toHaveProperty('trace');
    }
  });

  test('Improve & Run opens review first and submits reviewed rerun payload with metadata', async ({ page }) => {
    const mocks = await installBacktestingMocks(page);

    await page.goto('/#backtesting');
    await page.waitForSelector('[data-intelligence-action="rerun"]');
    await page.waitForSelector('[data-quick-param="stoploss"]');

    await page.click('[data-intelligence-action="rerun"]');
    await expect.poll(() => mocks.getStartBacktestBodies().length).toBe(0);
    await page.waitForSelector('[data-intelligence-review-action="run"]');
    await page.uncheck('[data-review-toggle="trailing_stop"]');
    await page.click('[data-intelligence-review-action="run"]');

    await expect.poll(() => mocks.getStartBacktestBodies().length).toBe(1);
    const body = mocks.getStartBacktestBodies()[0];

    expect(body.parent_run_id).toBe(LOADED_RUN_ID);
    expect(body.improvement_source).toBe('strategy_intelligence');
    expect(body.improvement_items).toEqual([
      'Tighten stoploss',
      'Enable trailing stop',
      'Manual follow-up',
    ]);
    expect(body.improvement_applied).toEqual(['Tighten stoploss']);
    expect(body.improvement_skipped).toContain('Enable trailing stop');
    expect(body.improvement_brief).toBe('Entries are poorly timed.');
    expect(body.strategy_params.stoploss).toBe(-0.08);
    expect(body.strategy_params.trailing_stop).toBe(false);
  });

  test('Strategy Intelligence panel shows diagnosis and next-move summary counts', async ({ page }) => {
    await installBacktestingMocks(page);

    await page.goto('/#backtesting');
    const panel = page.locator('.bt-intelligence');
    await expect(panel).toBeVisible();
    await expect(panel.locator('.bt-intelligence__panel-title', { hasText: 'Primary Diagnosis' })).toBeVisible();
    await expect(panel.locator('.bt-intelligence__panel-title', { hasText: 'Detected Issues' })).toBeVisible();
    await expect(panel.locator('.bt-intelligence__panel-title', { hasText: 'Next Moves' })).toBeVisible();

    const chips = panel.locator('.bt-intelligence__meta-chip');
    await expect(chips).toHaveCount(2);
    await expect(chips.nth(0)).toHaveText('2 quick actions');
    await expect(chips.nth(1)).toHaveText('1 manual item');
    await expect(panel.locator('[data-intelligence-primary]')).toBeVisible();
    await expect(panel.locator('[data-intelligence-stats] [data-intelligence-stat]')).toHaveCount(4);
    await expect(panel.locator('[data-intelligence-confidence-note]')).toContainText('high statistical confidence');
    await expect(panel.locator('[data-intelligence-action-group="quick"] [data-intelligence-action-card="quick"]')).toHaveCount(2);
    await expect(panel.locator('[data-intelligence-action-group="manual"] [data-intelligence-action-card="manual"]')).toHaveCount(1);
  });


  test('Per-suggestion Apply shows diff and Retest starts a rerun', async ({ page }) => {
    const mocks = await installBacktestingMocks(page);

    await page.goto('/#backtesting');
    await page.click('[data-intelligence-suggestion-apply="param-1"]');

    await expect.poll(() => mocks.getApplySuggestionBodies().length).toBe(1);
    await expect(page.locator('[data-intelligence-suggestion-retest="param-1"]')).toBeVisible();
    await expect(page.locator('.si-action-card__diff').first()).toContainText('stoploss');

    await page.evaluate(() => {
      document.querySelector('[data-intelligence-suggestion-retest="param-1"]')?.click();
    });
    await expect.poll(() => mocks.getStartBacktestBodies().length).toBe(1);
    const body = mocks.getStartBacktestBodies()[0];
    expect(body.improvement_source).toBe('strategy_intelligence_apply');
    expect(body.strategy_params.stoploss).toBe(-0.08);
  });

  test('Result explorer intelligence tab can apply manual guidance and expose Retest', async ({ page }) => {
    const mocks = await installBacktestingMocks(page);

    await page.goto('/#backtesting');
    await page.click('[data-intelligence-action="explore"]');
    await page.click('[data-tab="intelligence"]');
    await page.click('#result-explorer-modal [data-intelligence-suggestion-apply="fix-1"]');

    await expect.poll(() => mocks.getApplySuggestionBodies().length).toBe(1);
    await expect(page.locator('#result-explorer-modal [data-intelligence-suggestion-retest="fix-1"]')).toBeVisible();
    await expect(page.locator('#result-explorer-modal .si-action-card__diff').first()).toContainText('refined');
  });


  test('Result explorer intelligence tab uses guided summary layout', async ({ page }) => {
    await installBacktestingMocks(page);

    await page.goto('/#backtesting');
    await page.click('[data-intelligence-action="explore"]');
    await page.click('[data-tab="intelligence"]');

    const modal = page.locator('#result-explorer-modal');
    await expect(modal.locator('[data-intelligence-primary]')).toBeVisible();
    await expect(modal.locator('[data-intelligence-stats] [data-intelligence-stat]')).toHaveCount(4);
    await expect(modal.locator('[data-intelligence-confidence-note]')).toContainText('high statistical confidence');
    await expect(modal.locator('[data-intelligence-action-group="quick"] [data-intelligence-action-card="quick"]')).toHaveCount(2);
    await expect(modal.locator('[data-intelligence-action-group="manual"] [data-intelligence-action-card="manual"]')).toHaveCount(1);
  });

  test('Improve & Run still prepares review when quick params are still loading', async ({ page }) => {
    const mocks = await installBacktestingMocks(page, { strategyParamsDelayMs: 1250 });

    await page.goto('/#backtesting');
    const rerunBtn = page.locator('[data-intelligence-action="rerun"]');
    await rerunBtn.waitFor();

    await rerunBtn.click();
    await expect(rerunBtn).toHaveAttribute('data-state', 'preparing');
    await expect(rerunBtn).toHaveText('Preparing...');
    await page.waitForSelector('[data-intelligence-review-action="run"]');
    await page.click('[data-intelligence-review-action="run"]');

    await expect.poll(() => mocks.getStartBacktestBodies().length).toBe(1);
    const body = mocks.getStartBacktestBodies()[0];

    expect(body.strategy_params.stoploss).toBe(-0.08);
    expect(body.strategy_params.trailing_stop).toBe(true);
  });
  test('Improve & Run stays blocked while another backtest is active', async ({ page }) => {
    const mocks = await installBacktestingMocks(page, { includeActiveRun: true });

    await page.goto('/#backtesting');
    const rerunBtn = page.locator('[data-intelligence-action="rerun"]');
    await rerunBtn.waitFor();

    await expect(rerunBtn).toBeDisabled();
    await rerunBtn.click({ force: true });

    await page.waitForTimeout(300);
    expect(mocks.getStartBacktestBodies().length).toBe(0);
  });

  test('Improve & Run ignores rapid repeat clicks while preparing review', async ({ page }) => {
    const mocks = await installBacktestingMocks(page, { dataCoverageDelayMs: 1200 });

    await page.goto('/#backtesting');
    const rerunBtn = page.locator('[data-intelligence-action="rerun"]');
    await rerunBtn.waitFor();

    await rerunBtn.dblclick();

    await expect.poll(() => mocks.getStartBacktestBodies().length).toBe(0);
    await page.waitForSelector('[data-intelligence-review-action="run"]');
  });
});

