import { test, expect } from '@playwright/test';

function buildCandles(startTsSec: number, count: number, stepSec: number) {
  const arr: any[] = [];
  let t = startTsSec - count * stepSec;
  let price = 64000;
  for (let i = 0; i < count; i++) {
    const open = price;
    const high = open + Math.random() * 50;
    const low = open - Math.random() * 50;
    const close = low + Math.random() * (high - low);
    const volume = Math.random() * 200;
    arr.push({ time: t, open, high, low, close, volume });
    t += stepSec;
    price = close;
  }
  return arr;
}

// Intercept /api/candles and serve fake data; also capture endTime queries
async function mockCandles(page) {
  const calls: { url: string; endTime?: string }[] = [];
  await page.route('**/api/candles**', async route => {
    const url = new URL(route.request().url());
    const interval = url.searchParams.get('interval') || '1m';
    const endTime = url.searchParams.get('endTime') || undefined;
    calls.push({ url: url.toString(), endTime });
    const step = interval.endsWith('m') ? parseInt(interval) * 60 : interval.endsWith('h') ? parseInt(interval) * 3600 : 60;
    const now = Math.floor(Date.now() / 1000);
    const body = JSON.stringify(buildCandles(now, 50, step));
    await route.fulfill({ status: 200, contentType: 'application/json', body });
  });
  return calls;
}

test.describe('Chart basics and controls', () => {
  test.beforeEach(async ({ page, baseURL }) => {
    // Clean settings for determinism
    await page.addInitScript(() => localStorage.clear());
    await page.goto(baseURL!);
  });

  test('renders chart and updates controls with persistence', async ({ page }) => {
    const calls = await mockCandles(page);

    await page.reload();

    // Chart header contains symbol
    await expect(page.getByRole('heading', { name: /실시간 가격 차트/ })).toBeVisible();

    // Change interval to 1h and verify persistence
    await page.getByRole('button', { name: '1h' }).click();
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('chartInterval'))).toBe('1h');

    // Change history to 500 and verify
    await page.getByRole('button', { name: '500' }).click();
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('chartHistoryLimit'))).toBe('500');

    // Toggle EMA/Volume and verify persistence
    await page.getByLabel('EMA20').check();
    await page.getByLabel('EMA50').check();
    await page.getByLabel('Volume').check();
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('chartShowEMA20'))).toBe('1');
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('chartShowEMA50'))).toBe('1');
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('chartShowVolume'))).toBe('1');

    // Load more history triggers additional /api/candles call with endTime
    await page.getByRole('button', { name: /Load more history|Loading/ }).click();
    await expect.poll(() => calls.some(c => !!c.endTime)).toBeTruthy();
  });

  test('date/time formatting toggles persist', async ({ page }) => {
    await mockCandles(page);
    await page.reload();

    // Open preset controls toggles
    await page.getByLabel('Seconds').check();
    await page.getByLabel('12h').uncheck();

    await expect.poll(async () => page.evaluate(() => localStorage.getItem('chartShowSeconds'))).toBe('1');
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('chartHour12'))).toBe('0');

    await page.locator('label:has-text("Date") >> select').first().selectOption('DMY');
    await page.locator('label:has-text("Date") >> select').nth(1).selectOption('/');

    await expect.poll(async () => page.evaluate(() => localStorage.getItem('chartDateOrder'))).toBe('DMY');
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('chartDateSep'))).toBe('/');

    // Tooltip=Axis toggle
    await page.getByLabel('Tooltip=Axis').check();
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('chartTooltipMatchAxis'))).toBe('1');
  });
});
