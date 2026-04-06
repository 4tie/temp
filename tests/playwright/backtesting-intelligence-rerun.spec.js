const { test, expect } = require('@playwright/test');

const APP_ORIGIN = 'http://127.0.0.1:5000';
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
            title: 'Tighten stoploss',
            action_type: 'quick_param',
            auto_applicable: true,
            parameter: 'stoploss',
            suggested_value: -0.08,
          },
          {
            title: 'Enable trailing stop',
            action_type: 'quick_param',
            auto_applicable: true,
            parameter: 'trailing_stop',
            suggested_value: true,
          },
          {
            title: 'Manual follow-up',
            action_type: 'manual_guidance',
            auto_applicable: false,
            description: 'Refine entry conditions.',
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

    if (method === 'POST' && pathname === '/run') {
      startBacktestBodies.push(request.postDataJSON());
      return fulfillJson(route, { run_id: RERUN_ID, status: 'running' });
    }

    return route.continue();
  });

  return {
    getStartBacktestBodies: () => startBacktestBodies,
  };
}

test.describe('Backtesting Strategy Intelligence rerun', () => {
  test('Improve & Run submits rerun payload with intelligence metadata and auto-applied params', async ({ page }) => {
    const mocks = await installBacktestingMocks(page);

    await page.goto('/#backtesting');
    await page.waitForSelector('[data-intelligence-action="rerun"]');
    await page.waitForSelector('[data-quick-param="stoploss"]');

    await page.click('[data-intelligence-action="rerun"]');

    await expect.poll(() => mocks.getStartBacktestBodies().length).toBe(1);
    const body = mocks.getStartBacktestBodies()[0];

    expect(body.parent_run_id).toBe(LOADED_RUN_ID);
    expect(body.improvement_source).toBe('strategy_intelligence');
    expect(body.improvement_items).toEqual([
      'Tighten stoploss',
      'Enable trailing stop',
      'Manual follow-up',
    ]);
    expect(body.strategy_params.stoploss).toBe(-0.08);
    expect(body.strategy_params.trailing_stop).toBe(true);
  });

  test('Improve & Run still applies auto-changes when quick params are still loading', async ({ page }) => {
    const mocks = await installBacktestingMocks(page, { strategyParamsDelayMs: 1250 });

    await page.goto('/#backtesting');
    await page.waitForSelector('[data-intelligence-action="rerun"]');

    // Click before strategy params finish loading to validate race-safety.
    await page.click('[data-intelligence-action="rerun"]');

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

  test('Improve & Run ignores rapid repeat clicks while preparing rerun', async ({ page }) => {
    const mocks = await installBacktestingMocks(page, { dataCoverageDelayMs: 1200 });

    await page.goto('/#backtesting');
    const rerunBtn = page.locator('[data-intelligence-action="rerun"]');
    await rerunBtn.waitFor();

    await rerunBtn.dblclick();

    await expect.poll(() => mocks.getStartBacktestBodies().length).toBe(1);
  });
});


