// @ts-check
import { test, expect } from '@playwright/test';

test('inspector workflow', async ({ page }) => {
  await page.goto('http://127.0.0.1:5000/');
  await expect(page).toHaveTitle(/4tie/i);
  await page.pause();
});
