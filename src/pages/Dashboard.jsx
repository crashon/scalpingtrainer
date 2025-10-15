import React, { useEffect, useState } from 'react';
import TradingViewChart from '../components/TradingViewChart';
import TradePanel from '../components/TradePanel';
import TradeTable from '../components/TradeTable';
import PnLReport from '../components/PnLReport';
import TradingJournal from '../components/TradingJournal';
import Settings from '../components/Settings';
import AITradingDashboard from '../components/AITradingDashboard';
import { connectWebSocket } from '../api';
import { formatCurrency } from '../utils/format';

export default function Dashboard() {
  const [latestPrice, setLatestPrice] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('연결 중...');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [priceMarkers, setPriceMarkers] = useState({});
  const [symbol, setSymbol] = useState(() => {
    const s = localStorage.getItem('chartSymbol');
    return s || 'BTCUSDT';
  });
  const [customSymbol, setCustomSymbol] = useState('');
  const [favGroups, setFavGroups] = useState(() => {
    try {
      // New structure [{'name': 'Favorites', symbols: ['BTCUSDT', ...]}]
      const rawNew = localStorage.getItem('favGroups');
      if (rawNew) {
        const parsed = JSON.parse(rawNew);
        if (Array.isArray(parsed)) return parsed;
      }
      // Migration from old array favSymbols
      const rawOld = localStorage.getItem('favSymbols');
      const arr = rawOld ? JSON.parse(rawOld) : [];
      const migrated = [{ name: 'Favorites', symbols: Array.isArray(arr) ? arr : [] }];
      localStorage.setItem('favGroups', JSON.stringify(migrated));
      return migrated;
    } catch {
      return [{ name: 'Favorites', symbols: [] }];
    }
  });
  const [activeGroup, setActiveGroup] = useState(() => {
    const g = localStorage.getItem('favActiveGroup');
    return g || 'Favorites';
  });

  const allFavoriteSymbols = Array.from(new Set(favGroups.flatMap(g => g.symbols)));

  function saveFavGroups(next) {
    setFavGroups(next);
    try { localStorage.setItem('favGroups', JSON.stringify(next)); } catch {}
  }

  // Presets: stored per-group in localStorage key 'favGroupPresets'
  const [chartKey, setChartKey] = useState(0);
  function readPresets() {
    try {
      const raw = localStorage.getItem('favGroupPresets');
      return raw ? JSON.parse(raw) : {};
    } catch { return {}; }
  }
  function writePresets(obj) {
    try { localStorage.setItem('favGroupPresets', JSON.stringify(obj)); } catch {}
  }
  // Preset include toggles (persisted)
  const [presetIncludeVisibleRange, setPresetIncludeVisibleRange] = useState(() => {
    return localStorage.getItem('presetIncludeVisibleRange') === '1';
  });
  const [presetIncludeHistory, setPresetIncludeHistory] = useState(() => {
    return localStorage.getItem('presetIncludeHistory') === '1';
  });
  // Layout options state (persist in localStorage)
  const [chartLocale, setChartLocale] = useState(() => localStorage.getItem('chartLocale') || 'ko-KR');
  const [chartTimeZone, setChartTimeZone] = useState(() => localStorage.getItem('chartTimeZone') || 'Asia/Seoul');
  const [chartPricePrecision, setChartPricePrecision] = useState(() => {
    const v = parseInt(localStorage.getItem('chartPricePrecision'));
    return Number.isFinite(v) ? v : 2;
  });
  const [chartMinMove, setChartMinMove] = useState(() => {
    const v = parseFloat(localStorage.getItem('chartMinMove'));
    return Number.isFinite(v) ? v : 0.01;
  });
  const [chartShowSeconds, setChartShowSeconds] = useState(() => localStorage.getItem('chartShowSeconds') === '1');
  const [chartHour12, setChartHour12] = useState(() => localStorage.getItem('chartHour12') === '1');
  const [chartTooltipMatchAxis, setChartTooltipMatchAxis] = useState(() => localStorage.getItem('chartTooltipMatchAxis') === '1');
  const COMMON_TIMEZONES = ['Asia/Seoul','UTC','America/New_York','Europe/London','Europe/Paris','Asia/Tokyo','Asia/Hong_Kong','Asia/Singapore','Australia/Sydney'];
  // Date format options
  const [chartDateOrder, setChartDateOrder] = useState(() => localStorage.getItem('chartDateOrder') || 'YMD'); // YMD, DMY, MDY
  const [chartDateSep, setChartDateSep] = useState(() => localStorage.getItem('chartDateSep') || '-'); // '-', '/', '.'
  function getCurrentChartSettings() {
    // Read current settings from localStorage (used by TradingViewChart)
    const interval = localStorage.getItem('chartInterval') || '1m';
    const showEMA20 = localStorage.getItem('chartShowEMA20') !== '0';
    const showEMA50 = localStorage.getItem('chartShowEMA50') !== '0';
    const showVolume = localStorage.getItem('chartShowVolume') !== '0';
    const ema1 = parseInt(localStorage.getItem('chartEmaPeriod1')) || 20;
    const ema2 = parseInt(localStorage.getItem('chartEmaPeriod2')) || 50;
    const historyLimit = parseInt(localStorage.getItem('chartHistoryLimit')) || 300;
    let visibleRange = undefined;
    try {
      const vr = localStorage.getItem('chartVisibleRange');
      if (vr) visibleRange = JSON.parse(vr);
    } catch {}
    // include current symbol as defaultSymbol for this group
    const defaultSymbol = symbol;
    // layout options
    const locale = localStorage.getItem('chartLocale') || chartLocale;
    const timeZone = localStorage.getItem('chartTimeZone') || chartTimeZone;
    const pricePrecision = parseInt(localStorage.getItem('chartPricePrecision')) || chartPricePrecision;
    const minMove = parseFloat(localStorage.getItem('chartMinMove')) || chartMinMove;
    const dateOrder = localStorage.getItem('chartDateOrder') || chartDateOrder;
    const dateSep = localStorage.getItem('chartDateSep') || chartDateSep;
    return { interval, showEMA20, showEMA50, showVolume, ema1, ema2, historyLimit, visibleRange, defaultSymbol, locale, timeZone, pricePrecision, minMove, showSeconds: chartShowSeconds, hour12: chartHour12, dateOrder, dateSep, tooltipMatchAxis: chartTooltipMatchAxis };
  }
  function applyChartSettings(preset) {
    if (!preset) return;
    try {
      localStorage.setItem('chartInterval', preset.interval);
      localStorage.setItem('chartShowEMA20', preset.showEMA20 ? '1' : '0');
      localStorage.setItem('chartShowEMA50', preset.showEMA50 ? '1' : '0');
      localStorage.setItem('chartShowVolume', preset.showVolume ? '1' : '0');
      localStorage.setItem('chartEmaPeriod1', String(preset.ema1));
      localStorage.setItem('chartEmaPeriod2', String(preset.ema2));
      localStorage.setItem('chartHistoryLimit', String(preset.historyLimit || 300));
      if (preset.visibleRange) {
        localStorage.setItem('chartVisibleRange', JSON.stringify(preset.visibleRange));
      }
      if (preset.defaultSymbol) {
        setSymbol(preset.defaultSymbol);
        try { localStorage.setItem('chartSymbol', preset.defaultSymbol); } catch {}
      }
      if (preset.locale) {
        setChartLocale(preset.locale);
        try { localStorage.setItem('chartLocale', preset.locale); } catch {}
      }
      if (preset.timeZone) {
        setChartTimeZone(preset.timeZone);
        try { localStorage.setItem('chartTimeZone', preset.timeZone); } catch {}
      }
      if (Number.isFinite(preset.pricePrecision)) {
        setChartPricePrecision(preset.pricePrecision);
        try { localStorage.setItem('chartPricePrecision', String(preset.pricePrecision)); } catch {}
      }
      if (Number.isFinite(preset.minMove)) {
        setChartMinMove(preset.minMove);
        try { localStorage.setItem('chartMinMove', String(preset.minMove)); } catch {}
      }
      if (typeof preset.showSeconds === 'boolean') {
        setChartShowSeconds(preset.showSeconds);
        try { localStorage.setItem('chartShowSeconds', preset.showSeconds ? '1' : '0'); } catch {}
      }
      if (typeof preset.hour12 === 'boolean') {
        setChartHour12(preset.hour12);
        try { localStorage.setItem('chartHour12', preset.hour12 ? '1' : '0'); } catch {}
      }
      if (preset.dateOrder) {
        setChartDateOrder(preset.dateOrder);
        try { localStorage.setItem('chartDateOrder', preset.dateOrder); } catch {}
      }
      if (preset.dateSep) {
        setChartDateSep(preset.dateSep);
        try { localStorage.setItem('chartDateSep', preset.dateSep); } catch {}
      }
      if (typeof preset.tooltipMatchAxis === 'boolean') {
        setChartTooltipMatchAxis(preset.tooltipMatchAxis);
        try { localStorage.setItem('chartTooltipMatchAxis', preset.tooltipMatchAxis ? '1' : '0'); } catch {}
      }
    } finally {
      // Force remount of chart so it re-reads initial settings
      setChartKey(k => k + 1);
    }
  }
  function savePresetForActiveGroup() {
    const presets = readPresets();
    const settings = getCurrentChartSettings();
    // Respect toggle options
    if (!presetIncludeVisibleRange) delete settings.visibleRange;
    if (!presetIncludeHistory) delete settings.historyLimit;
    presets[activeGroup] = settings;
    writePresets(presets);
  }
  function clearPresetForActiveGroup() {
    const presets = readPresets();
    delete presets[activeGroup];
    writePresets(presets);
  }

  useEffect(() => {
    let ws = null;
    let reconnectTimeout = null;
    let isMounted = true;
    
    const connect = () => {
      if (!isMounted) return;
      
      try {
        ws = connectWebSocket(symbol);
        
        ws.onopen = () => {
          if (isMounted) {
            console.log('WebSocket 연결됨');
            setConnectionStatus('연결됨');
          }
        };
        
        ws.onmessage = evt => {
          if (!isMounted) return;
          try {
            const data = JSON.parse(evt.data);
            if (data && data.price) {
              setLatestPrice(data.price);
            } else if (data && data.type === 'ping') {
              // Ping 메시지 처리 (연결 유지 확인)
              console.log('WebSocket ping received');
            }
          } catch(e) {
            console.error('WebSocket 메시지 파싱 오류:', e);
          }
        };
        
        ws.onclose = (event) => {
          if (!isMounted) return;
          console.log('WebSocket 연결 종료', event.code, event.reason);
          setConnectionStatus('연결 끊김');
          
          // 정상적인 종료가 아닌 경우 재연결 시도
          if (event.code !== 1000 && event.code !== 1001) {
            setConnectionStatus('재연결 중...');
            reconnectTimeout = setTimeout(() => {
              if (isMounted) {
                connect();
              }
            }, 3000);
          }
        };
        
        ws.onerror = (error) => {
          if (!isMounted) return;
          console.error('WebSocket 오류:', error);
          setConnectionStatus('연결 오류');
        };
      } catch (error) {
        console.error('WebSocket 연결 실패:', error);
        setConnectionStatus('연결 실패');
        if (isMounted) {
          reconnectTimeout = setTimeout(() => {
            connect();
          }, 5000);
        }
      }
    };
    
    connect();
    
    return () => {
      isMounted = false;
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (ws) {
        ws.close(1000, 'Component unmounting');
      }
    };
  }, [symbol]);

  const renderContent = () => {
    switch(activeTab) {
      case 'journal':
        return <TradingJournal />;
      case 'settings':
        return <Settings />;
      case 'ai-trading':
        return <AITradingDashboard />;
      default:
        return (
          <>
            <TradingViewChart symbol={symbol} latestPrice={latestPrice} priceMarkers={priceMarkers} />
            <TradePanel latestPrice={latestPrice} onPriceMarkersChange={setPriceMarkers} />
            <TradeTable />
            <PnLReport />
          </>
        );
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation Header */}
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4">
              <h1 className="text-xl font-bold text-gray-900">Scalping Simulator V3</h1>
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-600">Symbol</span>
                <select
                  value={symbol}
                  onChange={(e) => { setSymbol(e.target.value); try { localStorage.setItem('chartSymbol', e.target.value); } catch {} }}
                  className="border border-gray-300 rounded px-2 py-1 text-sm"
                >
                  {[...new Set(['BTCUSDT','ETHUSDT','XRPUSDT','SOLUSDT','DOGEUSDT','SUIUSDT', ...allFavoriteSymbols])].map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <input
                  value={customSymbol}
                  onChange={e => setCustomSymbol(e.target.value)}
                  placeholder="e.g. ARBUSDT"
                  className="border border-gray-300 rounded px-2 py-1 text-sm w-28"
                />
                <button
                  className="px-2 py-1 text-sm border rounded hover:bg-gray-50"
                  onClick={() => {
                    const sym = (customSymbol || '').trim().toUpperCase();
                    if (!sym) return;
                    setSymbol(sym);
                    try { localStorage.setItem('chartSymbol', sym); } catch {}
                    // add to active group
                    const idx = favGroups.findIndex(g => g.name === activeGroup);
                    const next = [...favGroups];
                    if (idx >= 0) {
                      const symbols = next[idx].symbols;
                      if (!symbols.includes(sym)) symbols.push(sym);
                    } else {
                      next.push({ name: activeGroup, symbols: [sym] });
                    }
                    saveFavGroups(next);
                    setCustomSymbol('');
                  }}
                >Add</button>
              </div>
            </div>
            
            {/* Navigation Menu */}
            <div className="flex space-x-8">
              <button
                onClick={() => setActiveTab('dashboard')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  activeTab === 'dashboard' 
                    ? 'bg-blue-100 text-blue-700' 
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                대시보드
              </button>
              <button
                onClick={() => setActiveTab('ai-trading')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  activeTab === 'ai-trading' 
                    ? 'bg-blue-100 text-blue-700' 
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                AI 트레이딩
              </button>
              <button
                onClick={() => setActiveTab('journal')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  activeTab === 'journal' 
                    ? 'bg-blue-100 text-blue-700' 
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                매매일지
              </button>
              <button
                onClick={() => setActiveTab('settings')}
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  activeTab === 'settings' 
                    ? 'bg-blue-100 text-blue-700' 
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                세팅
              </button>
            </div>

            {/* Status Indicators */}
            <div className="flex items-center gap-4">
              <span className={`px-3 py-1 rounded text-sm ${
                connectionStatus === '연결됨' ? 'bg-green-100 text-green-800' : 
                connectionStatus === '연결 중...' ? 'bg-yellow-100 text-yellow-800' : 
                'bg-red-100 text-red-800'
              }`}>
                {connectionStatus}
              </span>
              {latestPrice != null && (
                <span className="text-lg font-mono font-semibold">
                  {symbol}: {formatCurrency(latestPrice)}
                </span>
              )}
            </div>
          </div>
        </div>
      </nav>
      {/* Favorites Groups */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-500">Groups:</span>
            {favGroups.map(g => (
              <button
                key={g.name}
                onClick={() => {
                  setActiveGroup(g.name);
                  try { localStorage.setItem('favActiveGroup', g.name); } catch {}
                  const presets = readPresets();
                  if (presets[g.name]) {
                    applyChartSettings(presets[g.name]);
                  }
                }}
                className={`px-2 py-1 text-xs rounded border ${activeGroup===g.name? 'bg-blue-600 text-white border-blue-600':'border-gray-300 text-gray-700 hover:bg-gray-50'}`}
              >{g.name}</button>
            ))}
            <button
              className="px-2 py-1 text-xs rounded border border-gray-300 hover:bg-gray-50"
              onClick={() => {
                const name = prompt('새 그룹 이름');
                if (!name) return;
                if (favGroups.some(g => g.name === name)) return;
                const next = [...favGroups, { name, symbols: [] }];
                saveFavGroups(next);
                setActiveGroup(name);
                try { localStorage.setItem('favActiveGroup', name); } catch {}
              }}
            >+ New Group</button>
            {activeGroup !== 'Favorites' && (
              <button
                className="px-2 py-1 text-xs rounded border border-red-300 text-red-700 hover:bg-red-50"
                onClick={() => {
                  if (!confirm('현재 그룹을 삭제하시겠습니까? (심볼도 함께 제거)')) return;
                  const next = favGroups.filter(g => g.name !== activeGroup);
                  const fallback = next[0]?.name || 'Favorites';
                  saveFavGroups(next);
                  setActiveGroup(fallback);
                  try { localStorage.setItem('favActiveGroup', fallback); } catch {}
                }}
              >Delete Group</button>
            )}
            {/* Preset controls */}
            <div className="ml-2 flex items-center gap-2">
              <label className="inline-flex items-center gap-1 text-xs text-gray-700">
                <input
                  type="checkbox"
                  checked={presetIncludeVisibleRange}
                  onChange={(e) => {
                    setPresetIncludeVisibleRange(e.target.checked);
                    try { localStorage.setItem('presetIncludeVisibleRange', e.target.checked ? '1' : '0'); } catch {}
                  }}
                /> Include Range
              </label>
              <label className="inline-flex items-center gap-1 text-xs text-gray-700">
                <input
                  type="checkbox"
                  checked={presetIncludeHistory}
                  onChange={(e) => {
                    setPresetIncludeHistory(e.target.checked);
                    try { localStorage.setItem('presetIncludeHistory', e.target.checked ? '1' : '0'); } catch {}
                  }}
                /> Include History
              </label>
              <button
                className="px-2 py-1 text-xs rounded border border-gray-300 hover:bg-gray-50"
                onClick={savePresetForActiveGroup}
              >Save Preset</button>
              <button
                className="px-2 py-1 text-xs rounded border border-gray-300 hover:bg-gray-50"
                onClick={() => {
                  const presets = readPresets();
                  const p = presets[activeGroup];
                  applyChartSettings(p);
                }}
              >Apply Preset</button>
              <button
                className="px-2 py-1 text-xs rounded border border-red-300 text-red-700 hover:bg-red-50"
                onClick={clearPresetForActiveGroup}
              >Clear Preset</button>
              {/* Layout inputs */}
              <div className="ml-3 flex items-center gap-2">
                <label className="inline-flex items-center gap-1 text-xs text-gray-700">
                  Seconds
                  <input
                    type="checkbox"
                    checked={chartShowSeconds}
                    onChange={(e) => { setChartShowSeconds(e.target.checked); try { localStorage.setItem('chartShowSeconds', e.target.checked ? '1' : '0'); } catch {} }}
                  />
                </label>
                <label className="inline-flex items-center gap-1 text-xs text-gray-700">
                  12h
                  <input
                    type="checkbox"
                    checked={chartHour12}
                    onChange={(e) => { setChartHour12(e.target.checked); try { localStorage.setItem('chartHour12', e.target.checked ? '1' : '0'); } catch {} }}
                  />
                </label>
                <label className="inline-flex items-center gap-1 text-xs text-gray-700" title="Apply axis date/time format to crosshair tooltip">
                  Tooltip=Axis
                  <input
                    type="checkbox"
                    checked={chartTooltipMatchAxis}
                    onChange={(e) => { setChartTooltipMatchAxis(e.target.checked); try { localStorage.setItem('chartTooltipMatchAxis', e.target.checked ? '1' : '0'); } catch {} }}
                  />
                </label>
                <label className="inline-flex items-center gap-1 text-xs text-gray-700">
                  Date
                  <select
                    value={chartDateOrder}
                    onChange={(e) => { setChartDateOrder(e.target.value); try { localStorage.setItem('chartDateOrder', e.target.value); } catch {} }}
                    className="border border-gray-300 rounded px-2 py-0.5 text-xs"
                  >
                    <option value="YMD">YYYY-MM-DD</option>
                    <option value="DMY">DD-MM-YYYY</option>
                    <option value="MDY">MM-DD-YYYY</option>
                  </select>
                  <select
                    value={chartDateSep}
                    onChange={(e) => { setChartDateSep(e.target.value); try { localStorage.setItem('chartDateSep', e.target.value); } catch {} }}
                    className="border border-gray-300 rounded px-2 py-0.5 text-xs"
                  >
                    <option value="-">-</option>
                    <option value="/">/</option>
                    <option value=".">.</option>
                  </select>
                </label>
                <label className="inline-flex items-center gap-1 text-xs text-gray-700">
                  TimeZone
                  <select
                    value={COMMON_TIMEZONES.includes(chartTimeZone) ? chartTimeZone : '__custom'}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === '__custom') {
                        const tz = prompt('Enter IANA Time Zone (e.g., Asia/Seoul, UTC, America/New_York):', chartTimeZone) || chartTimeZone;
                        setChartTimeZone(tz);
                        try { localStorage.setItem('chartTimeZone', tz); } catch {}
                      } else {
                        setChartTimeZone(val);
                        try { localStorage.setItem('chartTimeZone', val); } catch {}
                      }
                    }}
                    className="border border-gray-300 rounded px-2 py-0.5 text-xs"
                  >
                    {COMMON_TIMEZONES.map(tz => (<option key={tz} value={tz}>{tz}</option>))}
                    <option value="__custom">Custom...</option>
                  </select>
                </label>
                {!COMMON_TIMEZONES.includes(chartTimeZone) && (
                  <span className="text-[11px] text-gray-500">{chartTimeZone}</span>
                )}
                <label className="inline-flex items-center gap-1 text-xs text-gray-700">
                  Locale
                  <input
                    value={chartLocale}
                    onChange={(e) => { setChartLocale(e.target.value); try { localStorage.setItem('chartLocale', e.target.value); } catch {} }}
                    className="border border-gray-300 rounded px-2 py-0.5 text-xs w-24"
                  />
                </label>
                <label className="inline-flex items-center gap-1 text-xs text-gray-700">
                  Precision
                  <input
                    type="number"
                    min="0"
                    max="8"
                    value={chartPricePrecision}
                    onChange={(e) => { const v = Math.max(0, Math.min(8, parseInt(e.target.value) || 0)); setChartPricePrecision(v); try { localStorage.setItem('chartPricePrecision', String(v)); } catch {} }}
                    className="border border-gray-300 rounded px-2 py-0.5 text-xs w-16"
                  />
                </label>
                <label className="inline-flex items-center gap-1 text-xs text-gray-700">
                  MinMove
                  <input
                    type="number"
                    step="0.0001"
                    min="0.00000001"
                    value={chartMinMove}
                    onChange={(e) => { const v = parseFloat(e.target.value) || 0.0001; setChartMinMove(v); try { localStorage.setItem('chartMinMove', String(v)); } catch {} }}
                    className="border border-gray-300 rounded px-2 py-0.5 text-xs w-24"
                  />
                </label>
              </div>
            </div>
          </div>
          {/* Active group symbols with sort controls */}
          <div className="mt-2 flex flex-wrap gap-2">
            {(favGroups.find(g => g.name === activeGroup)?.symbols || []).map((f, idx, arr) => (
              <span key={f} className={`inline-flex items-center gap-2 px-2 py-1 text-xs rounded border ${symbol===f? 'bg-blue-50 border-blue-300':'border-gray-300'}`}>
                <button onClick={() => { setSymbol(f); try { localStorage.setItem('chartSymbol', f); } catch {} }} className="font-mono">
                  {f}
                </button>
                <div className="flex items-center gap-1">
                  <button
                    title="Up"
                    className="text-gray-500 hover:text-gray-800"
                    disabled={idx===0}
                    onClick={() => {
                      const next = favGroups.map(g => g.name===activeGroup ? { ...g, symbols: [...g.symbols] } : g);
                      const gIdx = next.findIndex(g => g.name===activeGroup);
                      const s = next[gIdx].symbols;
                      if (idx>0) { [s[idx-1], s[idx]] = [s[idx], s[idx-1]]; }
                      saveFavGroups(next);
                    }}
                  >↑</button>
                  <button
                    title="Down"
                    className="text-gray-500 hover:text-gray-800"
                    disabled={idx===arr.length-1}
                    onClick={() => {
                      const next = favGroups.map(g => g.name===activeGroup ? { ...g, symbols: [...g.symbols] } : g);
                      const gIdx = next.findIndex(g => g.name===activeGroup);
                      const s = next[gIdx].symbols;
                      if (idx<arr.length-1) { [s[idx+1], s[idx]] = [s[idx], s[idx+1]]; }
                      saveFavGroups(next);
                    }}
                  >↓</button>
                  <button
                    title="Remove"
                    className="text-gray-500 hover:text-red-600"
                    onClick={() => {
                      const next = favGroups.map(g => g.name===activeGroup ? { ...g, symbols: g.symbols.filter(x => x!==f) } : g);
                      saveFavGroups(next);
                    }}
                  >×</button>
                </div>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* key forces chart remount on preset apply */}
        {activeTab === 'dashboard' ? (
          <>
            <TradingViewChart key={chartKey} symbol={symbol} latestPrice={latestPrice} priceMarkers={priceMarkers} />
            <TradePanel latestPrice={latestPrice} onPriceMarkersChange={setPriceMarkers} />
            <TradeTable />
            <PnLReport />
          </>
        ) : renderContent()}
      </div>
    </div>
  );
}
