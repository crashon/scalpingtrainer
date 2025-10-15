// Number formatting helpers with dynamic decimals via localStorage settings

export function getFormatSettings() {
  const currencyDecimals = clampInt(parseInt(localStorage.getItem('currencyDecimals')), 0, 4, 2);
  const priceDecimals = clampInt(parseInt(localStorage.getItem('priceDecimals')), 0, 4, 2);
  const qtyDecimals = clampInt(parseInt(localStorage.getItem('qtyDecimals')), 0, 8, 6);
  return { currencyDecimals, priceDecimals, qtyDecimals };
}

function clampInt(n, min, max, fallback) {
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, n));
}

export function formatCurrency(value) {
  const n = Number(value ?? 0);
  const { currencyDecimals } = getFormatSettings();
  if (!isFinite(n)) return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: currencyDecimals, maximumFractionDigits: currencyDecimals }).format(0);
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: currencyDecimals, maximumFractionDigits: currencyDecimals }).format(n);
}

export function formatPrice(value) {
  const n = Number(value ?? 0);
  const { priceDecimals } = getFormatSettings();
  if (!isFinite(n)) return new Intl.NumberFormat('en-US', { minimumFractionDigits: priceDecimals, maximumFractionDigits: priceDecimals }).format(0);
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: priceDecimals, maximumFractionDigits: priceDecimals }).format(n);
}

export function formatQty(value) {
  const n = Number(value ?? 0);
  const { qtyDecimals } = getFormatSettings();
  if (!isFinite(n)) return new Intl.NumberFormat('en-US', { minimumFractionDigits: 0, maximumFractionDigits: qtyDecimals }).format(0);
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: 0, maximumFractionDigits: qtyDecimals }).format(n);
}

export function formatSignedCurrency(value) {
  const n = Number(value ?? 0);
  const { currencyDecimals } = getFormatSettings();
  const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: currencyDecimals, maximumFractionDigits: currencyDecimals });
  if (!isFinite(n)) return fmt.format(0);
  const s = fmt.format(Math.abs(n));
  return (n >= 0 ? '' : '-') + s;
}

// Optional: broadcast change event when settings are updated
export function notifyFormatSettingsChanged() {
  window.dispatchEvent(new CustomEvent('format-settings-changed'));
}
