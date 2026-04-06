const { test, expect } = require('@playwright/test');

const STRATEGIES = ['MomentumPulse', 'AtlasTrend', 'RangeKeeper'];
const STRATEGY_PARAMS = {
  parameters: [
    { name: 'buy_rsi', type: 'IntParameter', default: 28, description: 'Entry trigger threshold.' },
    { name: 'sell_rsi', type: 'IntParameter', default: 72, description: 'Exit trigger threshold.' },
    { name: 'risk_window', type: 'DecimalParameter', default: 1.6, description: 'Volatility guard multiplier.' },
  ],
};
const STRATEGY_SOURCE = [
  'from freqtrade.strategy import IStrategy, IntParameter',
  '',
  '',
  'class MomentumPulse(IStrategy):',
  '    buy_rsi = IntParameter(20, 40, default=28, space="buy")',
  '    sell_rsi = IntParameter(60, 85, default=72, space="sell")',
  '',
  '    timeframe = "5m"',
  '',
].join('\n');

function fulfillJson(route, payload) {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installApiMocks(page, appOrigin) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (url.origin !== appOrigin) {
      return route.continue();
    }

    const { pathname } = url;
    const method = request.method();

    if (method === 'GET' && pathname === '/strategies') {
      return fulfillJson(route, { strategies: STRATEGIES });
    }

    if (method === 'GET' && pathname === '/hyperopt/loss-functions') {
      return fulfillJson(route, {
        loss_functions: [
          { name: 'SharpeHyperOptLossDaily', label: 'Sharpe Daily' },
          { name: 'SortinoHyperOptLossDaily', label: 'Sortino Daily' },
        ],
      });
    }

    if (method === 'GET' && pathname === '/hyperopt/spaces') {
      return fulfillJson(route, {
        spaces: [
          { value: 'default', label: 'Default' },
          { value: 'buy', label: 'Buy' },
          { value: 'sell', label: 'Sell' },
        ],
      });
    }

    if (method === 'GET' && pathname === '/pairs') {
      return fulfillJson(route, {
        local_pairs: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
        config_pairs: ['BTC/USDT', 'ETH/USDT', 'XRP/USDT'],
        popular_pairs: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'LINK/USDT'],
      });
    }

    if (method === 'GET' && pathname === '/hyperopt/runs') {
      return fulfillJson(route, {
        runs: [
          {
            run_id: 'ho_20260406_001',
            strategy: 'MomentumPulse',
            status: 'completed',
            started_at: '2026-04-06T08:10:00Z',
            epochs: 180,
          },
          {
            run_id: 'ho_20260405_007',
            strategy: 'AtlasTrend',
            status: 'failed',
            started_at: '2026-04-05T17:30:00Z',
            epochs: 120,
          },
        ],
      });
    }

    if (method === 'GET' && pathname === '/runs') {
      return fulfillJson(route, {
        runs: [
          {
            run_id: 'bt_20260406_004',
            strategy: 'MomentumPulse',
            status: 'completed',
            started_at: '2026-04-06T07:42:00Z',
          },
          {
            run_id: 'bt_20260404_013',
            strategy: 'RangeKeeper',
            status: 'failed',
            started_at: '2026-04-04T22:18:00Z',
          },
        ],
      });
    }

    if (method === 'GET' && pathname === '/activity') {
      return fulfillJson(route, {
        events: [
          {
            timestamp: '2026-04-06T08:20:00Z',
            category: 'job',
            source: 'backtest',
            action: 'completed',
            status: 'completed',
            message: 'Backtest completed for MomentumPulse.',
            run_id: 'bt_20260406_004',
            strategy: 'MomentumPulse',
          },
          {
            timestamp: '2026-04-06T08:10:00Z',
            category: 'job',
            source: 'hyperopt',
            action: 'failed',
            status: 'failed',
            message: 'Hyperopt failed for AtlasTrend.',
            run_id: 'ho_20260405_007',
            strategy: 'AtlasTrend',
          },
        ],
      });
    }

    if (method === 'GET' && pathname === '/healthz') {
      return fulfillJson(route, { status: 'ok' });
    }

    if (method === 'GET' && pathname === '/ai/threads') {
      return fulfillJson(route, []);
    }

    if (method === 'GET' && pathname === '/ai/conversations') {
      return fulfillJson(route, []);
    }

    if (method === 'GET' && pathname === '/ai/pipeline-logs') {
      return fulfillJson(route, []);
    }

    if (method === 'GET' && pathname.endsWith('/params') && pathname.startsWith('/strategies/')) {
      return fulfillJson(route, STRATEGY_PARAMS);
    }

    if (method === 'GET' && pathname.endsWith('/source') && pathname.startsWith('/strategies/')) {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain; charset=utf-8',
        body: STRATEGY_SOURCE,
      });
    }

    return route.continue();
  });
}

async function gotoPage(page, viewName, waitSelector) {
  await page.goto(`/#${viewName}`);
  await page.waitForSelector(`.page-view.active[data-view="${viewName}"]`);
  await page.waitForSelector(waitSelector);
  await page.evaluate(async () => {
    if (document.fonts && document.fonts.ready) {
      await document.fonts.ready;
    }
  });
}

function screenshotOptions(page) {
  return {
    animations: 'disabled',
    caret: 'hide',
    maxDiffPixelRatio: 0.01,
    mask: [
      page.locator('[data-clock]'),
      page.locator('[data-stream]'),
      page.locator('[data-conn-label]'),
      page.locator('[data-conn-dot]'),
    ],
  };
}

test.describe('Visual regression', () => {
  test.beforeEach(async ({ page, baseURL }) => {
    const appOrigin = new URL(baseURL || 'http://127.0.0.1:5000').origin;
    await installApiMocks(page, appOrigin);
  });

  test('hyperopt desktop shell stays visually stable', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 980 });
    await gotoPage(page, 'hyperopt', '#ho-form');
    await expect(page.locator('[data-app-shell]')).toHaveScreenshot('hyperopt-desktop.png', screenshotOptions(page));
  });

  test('jobs desktop shell stays visually stable', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoPage(page, 'jobs', '#jobs-table-wrap');
    await expect(page.locator('[data-app-shell]')).toHaveScreenshot('jobs-desktop.png', screenshotOptions(page));
  });

  test('strategy lab desktop detail stays visually stable', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 960 });
    await gotoPage(page, 'strategy-lab', '#sl-list');
    await page.waitForSelector('[data-strategy="MomentumPulse"]');
    await page.locator('[data-strategy="MomentumPulse"]').click();
    await page.waitForSelector('#sl-detail .card__title');
    await expect(page.locator('[data-app-shell]')).toHaveScreenshot('strategy-lab-desktop.png', screenshotOptions(page));
  });

  test('jobs mobile shell stays visually stable', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await gotoPage(page, 'jobs', '#jobs-table-wrap');
    await expect(page.locator('[data-app-shell]')).toHaveScreenshot('jobs-mobile.png', screenshotOptions(page));
  });
});
