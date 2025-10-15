const API_URL = import.meta.env.DEV ? "http://localhost:8001" : "";

export async function placeOrder(order) {
  const res = await fetch(`${API_URL}/api/trade`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(order)
  });
  return res.json();
}

export async function getDailyPnL(dateStr = "2024-01-01") {
  const res = await fetch(`${API_URL}/api/report/daily?date_str=${dateStr}`);
  return res.json();
}

export async function getTrades() {
  const res = await fetch(`${API_URL}/api/trades`);
  return res.json();
}

export function connectWebSocket(symbol = 'BTCUSDT') {
  const base = import.meta.env.DEV ? "ws://localhost:8001/ws/price" : `ws://${window.location.host}/ws/price`;
  const url = `${base}?symbol=${encodeURIComponent(symbol)}`;
  return new WebSocket(url);
}

// Position APIs
export async function getPosition(symbol = "BTCUSDT") {
  const url = new URL(`${API_URL}/api/position`);
  url.searchParams.set('symbol', symbol);
  const res = await fetch(url.toString());
  return res.json();
}

export async function closePosition(symbol = "BTCUSDT", price, qty) {
  const res = await fetch(`${API_URL}/api/position/close`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, price, qty })
  });
  return res.json();
}

// Candles API
export async function getCandles(symbol = 'BTCUSDT', interval = '1m', limit = 500, startTime, endTime) {
  const url = new URL(`${API_URL}/api/candles`);
  url.searchParams.set('symbol', symbol);
  url.searchParams.set('interval', interval);
  url.searchParams.set('limit', String(limit));
  if (Number.isFinite(startTime)) url.searchParams.set('startTime', String(startTime));
  if (Number.isFinite(endTime)) url.searchParams.set('endTime', String(endTime));

  const maxRetries = 3;
  const baseDelay = 300; // ms
  let lastErr;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(url.toString());
      if (res.ok) return res.json();
      // Retry on 429/502
      if (res.status === 429 || res.status === 502) {
        if (attempt < maxRetries) {
          // Honor Retry-After if provided
          const ra = res.headers.get('Retry-After');
          let delay = ra ? parseFloat(ra) * 1000 : baseDelay * Math.pow(2, attempt);
          delay += Math.random() * 200; // jitter
          await new Promise(r => setTimeout(r, delay));
          continue;
        }
      }
      // Other errors: return JSON for consistent handling
      return res.json();
    } catch (e) {
      lastErr = e;
      if (attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt) + Math.random() * 200;
        await new Promise(r => setTimeout(r, delay));
        continue;
      }
      throw e;
    }
  }
  // Should not reach here, but return empty on failure
  return [];
}

// AI Trading APIs
export async function getAIStatus() {
  const res = await fetch(`${API_URL}/api/ai/status`);
  return res.json();
}

export async function getAIStrategies() {
  const res = await fetch(`${API_URL}/api/ai/strategies`);
  return res.json();
}

export async function createAIStrategy(strategy) {
  const res = await fetch(`${API_URL}/api/ai/strategies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(strategy)
  });
  return res.json();
}

export async function updateAIStrategy(configId, updates) {
  const res = await fetch(`${API_URL}/api/ai/strategies/${configId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates)
  });
  return res.json();
}

export async function deleteAIStrategy(configId) {
  const res = await fetch(`${API_URL}/api/ai/strategies/${configId}`, {
    method: 'DELETE'
  });
  return res.json();
}

export async function toggleAIStrategy(configId) {
  const res = await fetch(`${API_URL}/api/ai/strategies/${configId}/toggle`, {
    method: 'POST'
  });
  return res.json();
}

export async function startAITrading() {
  const res = await fetch(`${API_URL}/api/ai/start`, {
    method: 'POST'
  });
  return res.json();
}

export async function stopAITrading() {
  const res = await fetch(`${API_URL}/api/ai/stop`, {
    method: 'POST'
  });
  return res.json();
}

export async function getAIDashboard() {
  const res = await fetch(`${API_URL}/api/ai/dashboard`);
  return res.json();
}

// AI Trading WebSocket
export function connectAITradingWebSocket() {
  const base = import.meta.env.DEV ? "ws://localhost:8001/ws/ai-trading" : `ws://${window.location.host}/ws/ai-trading`;
  return new WebSocket(base);
}

// Consolidated API object
export const api = {
  // Trading APIs
  placeOrder,
  getDailyPnL,
  getTrades,
  getPosition,
  closePosition,
  getCandles,
  connectWebSocket,
  
  // AI Trading APIs
  getAIStatus,
  getAIStrategies,
  createAIStrategy,
  updateAIStrategy,
  deleteAIStrategy,
  toggleAIStrategy,
  startAITrading,
  stopAITrading,
  getAIDashboard,
  connectAITradingWebSocket
};
