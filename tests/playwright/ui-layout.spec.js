const { test, expect } = require('@playwright/test');

async function gotoPage(page, viewName, waitSelector = null) {
  await page.goto(`/#${viewName}`);
  await page.waitForSelector(`.page-view.active[data-view="${viewName}"]`);
  if (waitSelector) {
    await page.waitForSelector(waitSelector);
  }
}

async function readOverflowMetrics(page) {
  return page.evaluate(() => {
    const root = document.documentElement;
    const content = document.querySelector('[data-page-content]');
    return {
      docScrollWidth: root.scrollWidth,
      viewportWidth: window.innerWidth,
      contentScrollWidth: content ? content.scrollWidth : 0,
      contentClientWidth: content ? content.clientWidth : 0,
      bodyOverflowY: getComputedStyle(document.body).overflowY,
    };
  });
}

test.describe('Layout and shell integrity', () => {
  test('shell boots and hash navigation activates the expected core pages', async ({ page }) => {
    const cases = [
      ['dashboard', '#dash-stats'],
      ['backtesting', '#bt-form'],
      ['hyperopt', '#ho-form'],
      ['strategy-lab', '#sl-list'],
      ['jobs', '#jobs-table-wrap'],
      ['results', '#results-table-wrap'],
      ['settings', '#env-form'],
      ['ai-diagnosis', '#ai-layout'],
    ];

    for (const [viewName, selector] of cases) {
      await gotoPage(page, viewName, selector);
      const title = await page.locator('[data-page-title]').textContent();
      expect(title?.trim().toLowerCase()).toContain(viewName.replace('-', ' '));
    }
  });

  test('no document-level horizontal overflow across core pages', async ({ page }) => {
    const pages = [
      ['dashboard', '#dash-stats'],
      ['backtesting', '#bt-form'],
      ['hyperopt', '#ho-form'],
      ['strategy-lab', '#sl-list'],
      ['jobs', '#jobs-table-wrap'],
      ['results', '#results-table-wrap'],
      ['settings', '#env-form'],
      ['ai-diagnosis', '#ai-layout'],
    ];

    for (const [viewName, selector] of pages) {
      await gotoPage(page, viewName, selector);
      const metrics = await readOverflowMetrics(page);

      expect(metrics.docScrollWidth, `${viewName}: document should not overflow horizontally`).toBeLessThanOrEqual(metrics.viewportWidth + 2);
      expect(metrics.bodyOverflowY, `${viewName}: body must stay non-scrolling`).toBe('hidden');
      expect(metrics.contentScrollWidth, `${viewName}: page-content should fit horizontally`).toBeLessThanOrEqual(metrics.contentClientWidth + 2);
    }
  });

  test('sidebar collapsed state remains compact on desktop', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('4tie_sidebar_collapsed', 'true');
    });

    await gotoPage(page, 'dashboard', '#dash-stats');

    const shell = page.locator('[data-app-shell]');
    await expect(shell).toHaveClass(/sidebar-collapsed/);

    const sidebarBox = await page.locator('[data-sidebar]').boundingBox();
    expect(sidebarBox).not.toBeNull();
    expect(sidebarBox.width).toBeLessThanOrEqual(64);
  });

  test('AI Diagnosis stays usable at compact desktop widths', async ({ page }) => {
    await page.setViewportSize({ width: 1100, height: 860 });
    await gotoPage(page, 'ai-diagnosis', '#ai-layout');

    const metrics = await page.evaluate(() => {
      const sidebar = document.querySelector('#ai-sidebar');
      const header = document.querySelector('.ai-header');
      const thread = document.querySelector('#ai-thread');
      return {
        sidebarWidth: sidebar ? Math.round(sidebar.getBoundingClientRect().width) : 0,
        headerScrollWidth: header ? header.scrollWidth : 0,
        headerClientWidth: header ? header.clientWidth : 0,
        threadScrollWidth: thread ? thread.scrollWidth : 0,
        threadClientWidth: thread ? thread.clientWidth : 0,
      };
    });

    expect(metrics.sidebarWidth, 'AI sidebar should stay compact').toBeLessThanOrEqual(236);
    expect(metrics.headerScrollWidth, 'AI header should not overflow horizontally').toBeLessThanOrEqual(metrics.headerClientWidth + 2);
    expect(metrics.threadScrollWidth, 'AI thread should fit horizontally').toBeLessThanOrEqual(metrics.threadClientWidth + 2);
  });

  test('Strategy Lab stays usable at compact desktop widths', async ({ page }) => {
    await page.setViewportSize({ width: 1100, height: 860 });
    await gotoPage(page, 'strategy-lab', '#sl-list');

    const metrics = await page.evaluate(() => {
      const sidebar = document.querySelector('.split-layout--lab .split-layout__sidebar');
      const detail = document.querySelector('#sl-detail');
      const list = document.querySelector('#sl-list');
      return {
        sidebarWidth: sidebar ? Math.round(sidebar.getBoundingClientRect().width) : 0,
        detailScrollWidth: detail ? detail.scrollWidth : 0,
        detailClientWidth: detail ? detail.clientWidth : 0,
        listScrollWidth: list ? list.scrollWidth : 0,
        listClientWidth: list ? list.clientWidth : 0,
      };
    });

    expect(metrics.sidebarWidth, 'Strategy Lab sidebar should stay compact').toBeLessThanOrEqual(252);
    expect(metrics.detailScrollWidth, 'Strategy detail card should not overflow horizontally').toBeLessThanOrEqual(metrics.detailClientWidth + 2);
    expect(metrics.listScrollWidth, 'Strategy list should fit horizontally').toBeLessThanOrEqual(metrics.listClientWidth + 2);
  });

  test('results and settings remain usable on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    await gotoPage(page, 'results', '#results-table-wrap');
    const resultsMetrics = await readOverflowMetrics(page);
    expect(resultsMetrics.docScrollWidth, 'results: document should fit mobile viewport').toBeLessThanOrEqual(resultsMetrics.viewportWidth + 2);

    await gotoPage(page, 'settings', '#s-or-list');
    const settingsIssues = await page.evaluate(() => {
      const selectors = [
        '.settings-layout',
        '.settings-api-box',
        '.settings-input-panel',
        '.settings-api-actions',
        '.form-actions',
      ];
      const viewportWidth = window.innerWidth;
      const failures = [];
      for (const selector of selectors) {
        document.querySelectorAll(selector).forEach((node) => {
          const rect = node.getBoundingClientRect();
          if (rect.right > viewportWidth + 1 || rect.left < -1) {
            failures.push({ selector, left: rect.left, right: rect.right, viewportWidth });
          }
        });
      }
      return failures;
    });

    expect(settingsIssues, `mobile overflow issues: ${JSON.stringify(settingsIssues)}`).toEqual([]);

    await gotoPage(page, 'jobs', '#jobs-table-wrap');
    const jobsMetrics = await readOverflowMetrics(page);
    expect(jobsMetrics.docScrollWidth, 'jobs: document should fit mobile viewport').toBeLessThanOrEqual(jobsMetrics.viewportWidth + 2);
  });
});
