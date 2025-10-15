import { Page, expect } from '@playwright/test';

export async function clearLocalStorage(page: Page) {
  await page.addInitScript(() => localStorage.clear());
}

export async function mockCandles(page: Page, opts?: { count?: number; stepSec?: number }) {
  const calls: { url: string; endTime?: string }[] = [];
  const count = opts?.count ?? 50;
  await page.route('**/api/candles**', async route => {
    const url = new URL(route.request().url());
    const interval = url.searchParams.get('interval') || '1m';
    const endTime = url.searchParams.get('endTime') || undefined;
    calls.push({ url: url.toString(), endTime });
    const step = interval.endsWith('m') ? parseInt(interval) * 60 : interval.endsWith('h') ? parseInt(interval) * 3600 : interval.endsWith('d') ? 86400 : 60;
    const now = Math.floor(Date.now() / 1000);
    const body = JSON.stringify(buildCandles(now, count, step));
    await route.fulfill({ status: 200, contentType: 'application/json', body });
  });
  return calls;
}

export function buildCandles(startTsSec: number, count: number, stepSec: number) {
  const arr: any[] = [];
  let t = startTsSec - count * stepSec;
  let price = 64000;
  for (let i = 0; i < count; i++) {
    const open = price;
    const high = open + 50;
    const low = open - 50;
    const close = low + (high - low) * 0.6;
    const volume = 100 + i;
    arr.push({ time: t, open, high, low, close, volume });
    t += stepSec;
    price = close;
  }
  return arr;
}

export async function mockWebSocket(page: Page, symbol: string = 'BTCUSDT') {
  // Replace WebSocket to emit a simple price tick every 200ms
  await page.addInitScript(([sym]) => {
    class MockWS {
      url: string;
      onopen: any; onmessage: any; onclose: any; onerror: any;
      interval: any;
      constructor(url: string) { this.url = url; setTimeout(() => this.onopen && this.onopen({} as any), 0); this.start(); }
      start() {
        let p = 64000;
        this.interval = setInterval(() => {
          p += (Math.random() - 0.5) * 5;
          this.onmessage && this.onmessage({ data: JSON.stringify({ symbol: sym, price: p, timestamp: Date.now() }) });
        }, 200);
      }
      close() { clearInterval(this.interval); this.onclose && this.onclose({} as any); }
      send(_msg: string) {}
      addEventListener(type: string, cb: any) { (this as any)['on' + type] = cb; }
      removeEventListener() {}
    }
    // @ts-ignore
    window._RealWebSocket = window.WebSocket;
    // @ts-ignore
    window.WebSocket = MockWS as any;
  }, [symbol]);
}

export async function expectLocalStorage(page: Page, key: string, expected: string) {
  await expect.poll(async () => page.evaluate((k) => localStorage.getItem(k), key)).toBe(expected);
}
