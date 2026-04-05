const { test, expect } = require('@playwright/test');

async function gotoPage(page, viewName) {
  await page.goto(`/#${viewName}`);
  await page.waitForSelector(`.page-view.active[data-view="${viewName}"]`);
}

test.describe('Layout and scroll integrity', () => {
  test('no document-level horizontal overflow across primary pages', async ({ page }) => {
    const pages = ['dashboard', 'backtesting', 'results', 'settings'];

    for (const viewName of pages) {
      await gotoPage(page, viewName);
      const metrics = await page.evaluate(() => {
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

      expect(
        metrics.docScrollWidth,
        `${viewName}: document should not overflow horizontally`
      ).toBeLessThanOrEqual(metrics.viewportWidth + 2);
      expect(metrics.bodyOverflowY, `${viewName}: body must stay non-scrolling`).toBe('hidden');
      expect(
        metrics.contentScrollWidth,
        `${viewName}: page-content should fit horizontally`
      ).toBeLessThanOrEqual(metrics.contentClientWidth + 2);
    }
  });

  test('settings page containers fit and remain usable on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await gotoPage(page, 'settings');
    await page.waitForSelector('#s-or-list');

    const issues = await page.evaluate(() => {
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
            failures.push({
              selector,
              left: rect.left,
              right: rect.right,
              viewportWidth,
            });
          }
        });
      }
      return failures;
    });

    expect(issues, `mobile overflow issues: ${JSON.stringify(issues)}`).toEqual([]);
  });
});
