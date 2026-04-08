const { test, expect } = require('@playwright/test');

function fulfillJson(route, payload) {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

const RESULTS_RUNS = [
  {
    run_id: 'run_latest_alpha',
    status: 'completed',
    strategy: 'MomentumPulse',
    display_strategy: 'MomentumPulse',
    strategy_class: 'MomentumPulse',
    started_at: '2026-04-08T10:00:00Z',
    completed_at: '2026-04-08T10:20:00Z',
    result_metrics: {
      profit_percent: 12.4,
      win_rate: 61.2,
      max_drawdown: 6.1,
      profit_factor: 1.88,
      sharpe_ratio: 1.41,
      total_trades: 88,
    },
  },
  {
    run_id: 'run_beta_compare',
    status: 'completed',
    strategy: 'AtlasTrend',
    display_strategy: 'AtlasTrend',
    strategy_class: 'AtlasTrendV2',
    started_at: '2026-04-07T08:00:00Z',
    completed_at: '2026-04-07T08:30:00Z',
    result_metrics: {
      profit_percent: 18.9,
      win_rate: 57.4,
      max_drawdown: 9.3,
      profit_factor: 2.14,
      sharpe_ratio: 1.73,
      total_trades: 65,
    },
  },
  {
    run_id: 'run_gamma_defense',
    status: 'completed',
    strategy: 'RangeKeeper',
    display_strategy: 'RangeKeeper',
    strategy_class: 'RangeKeeper',
    started_at: '2026-04-06T06:00:00Z',
    completed_at: '2026-04-06T06:35:00Z',
    result_metrics: {
      profit_percent: 4.2,
      win_rate: 68.9,
      max_drawdown: 3.8,
      profit_factor: 1.42,
      sharpe_ratio: 1.09,
      total_trades: 112,
    },
  },
];

const RESULTS_REGISTRY = {
  metrics: [
    { key: 'profit_percent', label: 'Profit %', format: 'percent', decimals: 1, show_sign: true },
    { key: 'win_rate', label: 'Win Rate', format: 'percent', decimals: 1, show_sign: false },
    { key: 'max_drawdown', label: 'Drawdown', format: 'percent', decimals: 1, show_sign: false, higher_is_better: false },
    { key: 'profit_factor', label: 'Profit Factor', format: 'ratio', decimals: 2 },
    { key: 'sharpe_ratio', label: 'Sharpe', format: 'ratio', decimals: 2 },
    { key: 'total_trades', label: 'Trades', format: 'integer' },
  ],
  groups: {
    results_table: ['profit_percent', 'win_rate', 'max_drawdown', 'profit_factor', 'sharpe_ratio', 'total_trades'],
  },
};

async function installResultsPageMocks(page, appOrigin) {
  const tracker = {
    detailCalls: [],
    applyCalls: [],
  };

  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== appOrigin) return route.continue();

    const { pathname } = url;
    const method = request.method();

    if (method === 'GET' && pathname === '/runs') {
      return fulfillJson(route, { runs: [...RESULTS_RUNS, { run_id: 'ignored_failed', status: 'failed', strategy: 'IgnoreMe' }] });
    }
    if (method === 'GET' && pathname === '/result-metrics') {
      return fulfillJson(route, RESULTS_REGISTRY);
    }
    if (method === 'GET' && pathname === '/strategies') {
      return fulfillJson(route, { strategies: ['MomentumPulse', 'AtlasTrend', 'RangeKeeper'] });
    }
    if (method === 'GET' && pathname === '/hyperopt/runs') {
      return fulfillJson(route, { runs: [] });
    }
    if (method === 'GET' && pathname === '/pairs') {
      return fulfillJson(route, { local_pairs: ['BTC/USDT'], config_pairs: ['BTC/USDT'], popular_pairs: ['BTC/USDT'] });
    }
    if (method === 'GET' && pathname === '/healthz') {
      return fulfillJson(route, { status: 'ok' });
    }
    if (method === 'GET' && (pathname === '/ai/threads' || pathname === '/ai/conversations' || pathname === '/ai/pipeline-logs')) {
      return fulfillJson(route, []);
    }
    if (method === 'GET' && /^\/runs\/[^/]+$/.test(pathname)) {
      const runId = pathname.split('/')[2];
      tracker.detailCalls.push(runId);
      const run = RESULTS_RUNS.find((item) => item.run_id === runId) || RESULTS_RUNS[0];
      return fulfillJson(route, {
        run_id: run.run_id,
        status: 'completed',
        meta: {
          strategy: run.strategy,
          display_strategy: run.display_strategy,
          strategy_class: run.strategy_class,
          pairs: ['BTC/USDT'],
          timeframe: '5m',
          exchange: 'binance',
          strategy_params: { stoploss: -0.1 },
        },
        logs: [],
        results: {
          overview: { starting_balance: 1000, final_balance: 1124, total_trades: run.result_metrics.total_trades },
          summary: { totalProfitPct: run.result_metrics.profit_percent, totalTrades: run.result_metrics.total_trades, winRate: run.result_metrics.win_rate },
          risk_metrics: { max_drawdown: run.result_metrics.max_drawdown },
          strategy_intelligence: {
            diagnosis: { primary: { title: 'Stable run', explanation: 'Healthy result surface.', severity: 'low' }, issues: [] },
            suggestions: [],
            rerun_plan: { auto_param_changes: [] },
          },
        },
      });
    }
    if (method === 'GET' && /^\/runs\/[^/]+\/raw$/.test(pathname)) {
      return fulfillJson(route, { artifact: {}, raw_artifact_missing: true, data_source: 'mock' });
    }
    if (method === 'POST' && pathname.includes('/apply-config')) {
      tracker.applyCalls.push(pathname.split('/')[2]);
      return fulfillJson(route, { applied: true, warnings: [] });
    }

    return route.continue();
  });

  return tracker;
}

test.describe('Results page', () => {
  test('supports search, presets, latest highlight, and stable row actions', async ({ page, baseURL }) => {
    const appOrigin = new URL(baseURL || 'http://127.0.0.1:8000').origin;
    const tracker = await installResultsPageMocks(page, appOrigin);

    await page.goto('/#results');
    await page.waitForSelector('#results-table-wrap .results-table-card');
    await expect(page.locator('[data-results-search]')).toBeVisible();
    await expect(page.locator('[data-results-sort-preset]')).toHaveCount(4);
    await expect(page.locator('[data-results-metric-preset]')).toHaveCount(3);
    await expect(page.locator('[data-results-latest-summary]')).toContainText('MomentumPulse');

    const latestRow = page.locator('tr[data-run-id="run_latest_alpha"]');
    await expect(latestRow).toHaveAttribute('data-row-latest', 'true');
    await expect(latestRow.locator('.results-table__badge--latest')).toHaveText('Latest');

    await page.locator('#result-explorer-modal .modal__close').click();
    await page.locator('[data-results-search]').fill('AtlasTrend');
    await expect(page.locator('tbody tr[data-run-id]')).toHaveCount(1);
    await expect(page.locator('tbody tr[data-run-id] .results-table__strategy-name')).toContainText('AtlasTrend');

    await page.locator('[data-results-search]').fill('');
    await page.locator('[data-results-metric-preset="compact"]').click();
    await expect(page.locator('th[data-sort^="metric:"]')).toHaveCount(4);
    await page.locator('[data-results-metric-preset="all"]').click();
    await expect(page.locator('th[data-sort^="metric:"]')).toHaveCount(6);

    await page.locator('[data-results-sort-preset="profit"]').click();
    await expect(page.locator('tbody tr[data-run-id]').first()).toHaveAttribute('data-run-id', 'run_beta_compare');

    await page.locator('[data-results-sort-preset="drawdown"]').click();
    await expect(page.locator('tbody tr[data-run-id]').first()).toHaveAttribute('data-run-id', 'run_gamma_defense');

    const detailCallsBefore = tracker.detailCalls.length;
    await page.locator('tr[data-run-id="run_beta_compare"]').click();
    await expect(page.locator('#result-explorer-modal .modal__title')).toContainText('run_beta_compare');
    expect(tracker.detailCalls.length).toBe(detailCallsBefore + 1);

    await page.locator('#result-explorer-modal .modal__close').click();
    await page.locator('tr[data-run-id="run_gamma_defense"] [data-apply-btn]').click();
    await expect.poll(() => tracker.applyCalls.length).toBe(1);
    expect(tracker.detailCalls.length).toBe(detailCallsBefore + 1);
  });
});


