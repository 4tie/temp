const { test, expect } = require('@playwright/test');

function fulfillJson(route, payload, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installSelectMocks(page, appOrigin) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== appOrigin) return route.continue();

    const { pathname } = url;
    const method = request.method();

    if (method === 'GET' && pathname === '/healthz') return fulfillJson(route, { status: 'ok' });
    if (method === 'GET' && pathname === '/strategies') {
      return fulfillJson(route, {
        strategies: ['AtlasTrend', 'BaseStarterStrategy', 'MultiMa', 'MultiMa_evo_g3'],
      });
    }
    if (method === 'GET' && pathname === '/pairs') {
      return fulfillJson(route, {
        local_pairs: ['BTC/USDT', 'ETH/USDT'],
        config_pairs: ['BTC/USDT'],
        popular_pairs: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
      });
    }
    if (method === 'GET' && pathname === '/config') {
      return fulfillJson(route, {
        strategy: 'MultiMa',
        exchange: 'binance',
        timeframe: '5m',
        timerange: '20260101-20260201',
        dry_run_wallet: 1000,
        max_open_trades: 3,
        stake_amount: 'unlimited',
      });
    }
    if (method === 'GET' && pathname === '/last-config') {
      return fulfillJson(route, { config: null });
    }
    if (method === 'GET' && pathname === '/settings') {
      return fulfillJson(route, {
        openrouter_api_keys: [],
        freqtrade_exchange: 'binance',
        backtest_api_port: '8000',
      });
    }
    if (method === 'GET' && pathname === '/presets') {
      return fulfillJson(route, { presets: {} });
    }
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
    if (method === 'GET' && pathname === '/ai/threads') {
      return fulfillJson(route, []);
    }

    return route.continue();
  });
}

test.describe('custom selects', () => {
  test.beforeEach(async ({ page, baseURL }) => {
    await installSelectMocks(page, new URL(baseURL).origin);
  });

  test('backtesting strategy select supports search and updates the hidden native select', async ({ page }) => {
    await page.goto('/#backtesting');
    await page.waitForSelector('#bt-form');

    const trigger = page.locator('#bt-strategy + [data-custom-select-host] .custom-select__trigger');
    await expect(trigger).toBeVisible();

    await trigger.click();
    await expect(page.locator('.custom-select__panel')).toBeVisible();
    await expect(page.locator('.custom-select__search')).toBeVisible();

    await page.locator('.custom-select__search').fill('MultiMa_evo');
    await page.locator('.custom-select__option', { hasText: 'MultiMa_evo_g3' }).click();

    await expect.poll(() => page.locator('#bt-strategy').evaluate((el) => el.value)).toBe('MultiMa_evo_g3');
    await expect(page.locator('#bt-strategy + [data-custom-select-host] [data-custom-select-label]')).toHaveText('MultiMa_evo_g3');
  });

  test('settings non-searchable select stays simple and tracks programmatic value changes', async ({ page }) => {
    await page.goto('/#settings');
    await page.waitForSelector('#env-form');

    const exchangeTrigger = page.locator('#s-exchange + [data-custom-select-host] .custom-select__trigger');
    await expect(exchangeTrigger).toBeVisible();

    await exchangeTrigger.click();
    await expect(page.locator('.custom-select__panel')).toBeVisible();
    await expect(page.locator('.custom-select__search-wrap')).toBeHidden();
    await page.keyboard.press('Escape');

    await page.evaluate(() => {
      const exchange = document.getElementById('s-exchange');
      const timeframe = document.getElementById('s-timeframe');
      if (exchange instanceof HTMLSelectElement) {
        exchange.value = 'kraken';
      }
      if (timeframe instanceof HTMLSelectElement) {
        timeframe.value = '1h';
      }
    });

    await expect.poll(() => page.locator('#s-exchange').evaluate((el) => el.value)).toBe('kraken');
    await expect(page.locator('#s-exchange + [data-custom-select-host] [data-custom-select-label]')).toHaveText('Kraken');
    await expect(page.locator('#s-timeframe + [data-custom-select-host] [data-custom-select-label]')).toHaveText('1h');
  });
});
