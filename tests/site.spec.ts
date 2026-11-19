import { test, expect } from '@playwright/test';

test('landing page shows the thesis order and live values', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('/');
  await expect(page.locator('h1')).toHaveText('The benchmark price for AI tokens.');
  const h2 = await page.locator('main h2').allTextContents();
  expect(h2[0]).toContain('benchmark price');
  expect(h2[4]).toContain('numbers');
  await expect(page.locator('.card .value').first()).toContainText('$');
  await expect(page.locator('link[rel=canonical]')).toHaveAttribute('href', 'https://inferencepriceindex.com/');
  expect(errors).toEqual([]);
});

test('phone width has no horizontal scroll', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const w = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(w).toBeLessThanOrEqual(390);
});

test('API latest JSON is published', async ({ request }) => {
  const r = await request.get('/v1/index/latest.json');
  expect(r.ok()).toBeTruthy();
  const j = await r.json();
  expect(j.indices['STCI-ALL'].blended_rate).toBeGreaterThan(0);
});
