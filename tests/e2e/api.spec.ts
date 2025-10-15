import { test, expect } from '@playwright/test';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001';

function isJSON(str: string) {
  try { JSON.parse(str); return true; } catch { return false; }
}

test.describe('Backend infra endpoints', () => {
  test('GET /healthz returns ok', async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/healthz`);
    expect(res.ok()).toBeTruthy();
    const json = await res.json();
    expect(json.status).toBe('ok');
  });

  test('GET /readyz returns ok and redis status acceptable', async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/readyz`);
    expect(res.ok()).toBeTruthy();
    const json = await res.json();
    expect(json.status).toBe('ok');
    // Accept either disabled or connected depending on env
    if (json.redis) {
      expect(['disabled', 'connected']).toContain(json.redis);
    }
  });

  test('GET /metrics returns prometheus metrics or disabled notice', async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/metrics`);
    expect(res.ok()).toBeTruthy();
    const ct = res.headers()['content-type'] || '';
    const body = await res.text();
    // If prometheus_client installed, content-type should be text/plain; version=0.0.4
    // Otherwise we expect a plain text string "metrics disabled"
    if (body.includes('metrics disabled')) {
      expect(ct.includes('text/plain')).toBeTruthy();
      expect(body.trim()).toBe('metrics disabled');
    } else {
      expect(ct.includes('text/plain')).toBeTruthy();
      expect(body.length).toBeGreaterThan(0);
      // quick sanity check for at least one metric name when enabled
      expect(/_total|^# HELP/m.test(body)).toBeTruthy();
    }
  });
});
