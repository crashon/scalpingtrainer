import React, { useEffect, useRef, useState } from 'react';
import { createChart, CrosshairMode } from 'lightweight-charts';
import { formatCurrency } from '../utils/format';
import { getTrades, getCandles } from '../api';

export default function TradingViewChart({ symbol = 'BTCUSDT', latestPrice, priceMarkers = {} }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const dataRef = useRef([]); // array of candle bars {time, open, high, low, close}
  const volumeRef = useRef([]); // [{time, value, color}]
  const priceLinesRef = useRef([]);
  const resizeObserverRef = useRef(null);
  const currentMinuteRef = useRef(null); // epoch minute (in seconds)
  const ema20SeriesRef = useRef(null);
  const ema50SeriesRef = useRef(null);
  const ema20DataRef = useRef([]);
  const ema50DataRef = useRef([]);
  const volumeSeriesRef = useRef(null);
  const [interval, setIntervalState] = useState(() => {
    const saved = localStorage.getItem('chartInterval');
    return saved || '1m';
  });
  const [historyLimit, setHistoryLimit] = useState(() => {
    const v = parseInt(localStorage.getItem('chartHistoryLimit'));
    return Number.isFinite(v) ? v : 300;
  });
  const [loadingMore, setLoadingMore] = useState(false);
  const loadMoreBusyRef = useRef(false);
  const [showEMA20, setShowEMA20] = useState(() => {
    const v = localStorage.getItem('chartShowEMA20');
    return v == null ? true : v === '1';
  });
  const [showEMA50, setShowEMA50] = useState(() => {
    const v = localStorage.getItem('chartShowEMA50');
    return v == null ? true : v === '1';
  });
  const [showVolume, setShowVolume] = useState(() => {
    const v = localStorage.getItem('chartShowVolume');
    return v == null ? true : v === '1';
  });
  const [emaPeriod1, setEmaPeriod1] = useState(() => {
    const v = parseInt(localStorage.getItem('chartEmaPeriod1'));
    return Number.isFinite(v) ? v : 20;
  });
  const [emaPeriod2, setEmaPeriod2] = useState(() => {
    const v = parseInt(localStorage.getItem('chartEmaPeriod2'));
    return Number.isFinite(v) ? v : 50;
  });

  const bucketSeconds = intervalToSeconds(interval);

  useEffect(() => {
    if (!containerRef.current) return;

    const pricePrecision = (() => {
      const v = parseInt(localStorage.getItem('chartPricePrecision'));
      return Number.isFinite(v) ? v : 2;
    })();
    const minMove = (() => {
      const v = parseFloat(localStorage.getItem('chartMinMove'));
      return Number.isFinite(v) ? v : 0.01;
    })();
    const locale = localStorage.getItem('chartLocale') || 'ko-KR';
    const timeZone = localStorage.getItem('chartTimeZone') || 'Asia/Seoul';
    const showSeconds = localStorage.getItem('chartShowSeconds') === '1';
    const hour12 = localStorage.getItem('chartHour12') === '1';
    const dateOrder = localStorage.getItem('chartDateOrder') || 'YMD';
    const dateSep = localStorage.getItem('chartDateSep') || '-';
    const dtf = new Intl.DateTimeFormat(locale, {
      timeZone,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
      second: showSeconds ? '2-digit' : undefined,
      hour12,
    });
    const timeFormatter = (t) => {
      // t can be UTCTimestamp (seconds) or BusinessDay { year, month, day }
      let date;
      if (typeof t === 'number') {
        date = new Date(t * 1000);
      } else if (t && typeof t === 'object' && 'year' in t) {
        date = new Date(Date.UTC(t.year, (t.month || 1) - 1, t.day || 1));
      } else {
        date = new Date();
      }
      const parts = dtf.formatToParts(date);
      const get = (type) => (parts.find(p => p.type === type)?.value || '').padStart(type==='year'?4:2, '0');
      const Y = get('year');
      const M = get('month');
      const D = get('day');
      let dateStr = '';
      switch (dateOrder) {
        case 'DMY': dateStr = `${D}${dateSep}${M}${dateSep}${Y}`; break;
        case 'MDY': dateStr = `${M}${dateSep}${D}${dateSep}${Y}`; break;
        case 'YMD':
        default: dateStr = `${Y}${dateSep}${M}${dateSep}${D}`; break;
      }
      const H = get('hour');
      const Min = get('minute');
      const S = showSeconds ? `:${get('second')}` : '';
      const dayPeriod = parts.find(p => p.type === 'dayPeriod')?.value || '';
      // Per-interval formatting rules
      const isDaily = interval.includes('d') || interval.includes('w');
      const isHourly = interval.includes('h');
      const isMinute = interval.includes('m');

      if (isDaily) {
        // Day/Week: date only
        return dateStr;
      }
      if (isHourly) {
        // Hour: date + HH:mm (no seconds)
        const timeStr = `${H}:${Min}${hour12 && dayPeriod ? ` ${dayPeriod}` : ''}`;
        return `${dateStr} ${timeStr}`;
      }
      if (isMinute) {
        // Minute: time only, seconds optional by setting
        const timeStr = `${H}:${Min}${S}${hour12 && dayPeriod ? ` ${dayPeriod}` : ''}`;
        return timeStr;
      }
      // Fallback
      const timeStr = `${H}:${Min}${S}${hour12 && dayPeriod ? ` ${dayPeriod}` : ''}`;
      return `${dateStr} ${timeStr}`;
    };

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: 'Solid', color: '#ffffff' },
        textColor: '#111827',
      },
      localization: { locale, timeFormatter },
      rightPriceScale: {
        borderVisible: false,
      },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        secondsVisible: showSeconds,
      },
      grid: {
        vertLines: { color: 'rgba(0,0,0,0.05)' },
        horzLines: { color: 'rgba(0,0,0,0.05)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    });

    let primarySeries;
    if (typeof chart.addCandlestickSeries === 'function') {
      primarySeries = chart.addCandlestickSeries({
        upColor: '#16a34a',
        downColor: '#ef4444',
        wickUpColor: '#16a34a',
        wickDownColor: '#ef4444',
        borderVisible: false,
        priceFormat: { type: 'price', precision: pricePrecision, minMove: minMove },
      });
    } else {
      // Fallback for environments without candlestick support
      primarySeries = chart.addLineSeries({
        color: '#3b82f6',
        lineWidth: 2,
        priceFormat: { type: 'price', precision: pricePrecision, minMove: minMove },
      });
    }

    chartRef.current = chart;
    seriesRef.current = primarySeries;

    // Volume pane
    volumeSeriesRef.current = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '', // separate scale
      color: '#94a3b8',
      base: 0,
    });

    // EMA overlays
    ema20SeriesRef.current = chart.addLineSeries({ color: '#f59e0b', lineWidth: 2, visible: showEMA20 });
    ema50SeriesRef.current = chart.addLineSeries({ color: '#8b5cf6', lineWidth: 2, visible: showEMA50 });

    // Fit initial empty data
    primarySeries.setData([]);

    // Crosshair tooltip
    const tooltip = document.createElement('div');
    tooltip.style.position = 'absolute';
    tooltip.style.pointerEvents = 'none';
    tooltip.style.background = 'rgba(17,24,39,0.9)';
    tooltip.style.color = '#fff';
    tooltip.style.padding = '4px 8px';
    tooltip.style.borderRadius = '4px';
    tooltip.style.fontSize = '12px';
    tooltip.style.zIndex = '20';
    tooltip.style.display = 'none';
    containerRef.current.style.position = 'relative';
    containerRef.current.appendChild(tooltip);

    const tooltipMatchAxis = localStorage.getItem('chartTooltipMatchAxis') === '1';
    const dtfFull = new Intl.DateTimeFormat(locale, {
      timeZone,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: showSeconds ? '2-digit' : undefined,
      hour12,
    });

    function formatTooltipTime(t) {
      if (tooltipMatchAxis) return timeFormatter(t);
      let date;
      if (typeof t === 'number') date = new Date(t * 1000);
      else if (t && typeof t === 'object' && 'year' in t) date = new Date(Date.UTC(t.year, (t.month || 1) - 1, t.day || 1));
      else date = new Date();
      return dtfFull.format(date);
    }

    const priceFmt = (p) => {
      const n = Number(p);
      if (!Number.isFinite(n)) return '';
      return n.toFixed(pricePrecision);
    };

    const volFmt = (v) => {
      const n = Number(v);
      if (!Number.isFinite(n)) return '';
      return n.toLocaleString(undefined, { maximumFractionDigits: 6 });
    };

    const moveHandler = (param) => {
      if (!param || param.point == null || param.time == null) {
        tooltip.style.display = 'none';
        return;
      }
      // seriesPrices may be undefined when cursor is outside series/pane
      const price = param.seriesPrices && primarySeries ? param.seriesPrices.get(primarySeries) : undefined;
      const t = formatTooltipTime(param.time);
      // find candle/volume at time
      const ts = typeof param.time === 'number' ? param.time : (param.time?.year ? Math.floor(Date.UTC(param.time.year, (param.time.month||1)-1, param.time.day||1)/1000) : undefined);
      let cndl = undefined;
      let vol = undefined;
      if (ts != null) {
        const idx = dataRef.current.findIndex(b => b.time === ts);
        if (idx >= 0) {
          cndl = dataRef.current[idx];
          const v = volumeRef.current?.[idx];
          vol = v?.value;
        }
      }
      // ema values
      let e1, e2;
      if (ts != null) {
        const e1i = ema20DataRef.current.findIndex(e => e.time === ts);
        const e2i = ema50DataRef.current.findIndex(e => e.time === ts);
        if (e1i >= 0) e1 = ema20DataRef.current[e1i]?.value;
        if (e2i >= 0) e2 = ema50DataRef.current[e2i]?.value;
      }
      const lines = [];
      lines.push(`<div><strong>${symbol} ${interval} — ${t}</strong></div>`);
      if (cndl) {
        lines.push(`<div>시 ${priceFmt(cndl.open)}  고 ${priceFmt(cndl.high)}  저 ${priceFmt(cndl.low)}  종 ${priceFmt(cndl.close)}</div>`);
      } else if (price != null) {
        lines.push(`<div>Px ${priceFmt(price)}</div>`);
      }
      if (vol != null) lines.push(`<div>Vol ${volFmt(vol)}</div>`);
      if (e1 != null) lines.push(`<div>EMA${emaPeriod1} ${priceFmt(e1)}</div>`);
      if (e2 != null) lines.push(`<div>EMA${emaPeriod2} ${priceFmt(e2)}</div>`);
      tooltip.innerHTML = lines.join('');
      const { x, y } = param.point;
      const margin = 10;
      tooltip.style.left = `${Math.max(0, Math.min(containerRef.current.clientWidth - 120, x + margin))}px`;
      tooltip.style.top = `${Math.max(0, y + margin)}px`;
      tooltip.style.display = 'block';
    };
    chart.subscribeCrosshairMove(moveHandler);

    // Resize handling
    const ro = new ResizeObserver(() => {
      if (!containerRef.current || !chart) return;
      chart.applyOptions({ width: containerRef.current.clientWidth, height: containerRef.current.clientHeight });
    });
    ro.observe(containerRef.current);
    resizeObserverRef.current = ro;

    // Initial size
    chart.applyOptions({ width: containerRef.current.clientWidth, height: containerRef.current.clientHeight });

    // Subscribe to visible range changes and persist
    const unsub = chart.timeScale().subscribeVisibleTimeRangeChange(async (range) => {
      if (!range) return;
      try { localStorage.setItem('chartVisibleRange', JSON.stringify(range)); } catch {}
      // Infinite scroll: when near left edge, load older
      try {
        const first = dataRef.current?.[0];
        if (!first || !range.from) return;
        // if visible range starts within 2 bars of the first bar, try load more
        if (range.from <= first.time + 2 * bucketSeconds) {
          if (loadMoreBusyRef.current || loadingMore) return;
          loadMoreBusyRef.current = true;
          setLoadingMore(true);
          const endMs = first.time * 1000 - 1;
          let prevRange;
          try { prevRange = chartRef.current?.timeScale()?.getVisibleRange(); } catch {}
          const older = await getCandles(symbol, interval, historyLimit, undefined, endMs);
          if (Array.isArray(older) && older.length) {
            const mapped = older.map(b => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close }));
            // 중복 제거 및 시간 순서대로 정렬
            const combined = [...mapped, ...dataRef.current];
            const uniqueCombined = combined.reduce((acc, current) => {
              const existing = acc.find(item => item.time === current.time);
              if (!existing) {
                acc.push(current);
              }
              return acc;
            }, []);
            uniqueCombined.sort((a, b) => a.time - b.time);
            dataRef.current = uniqueCombined;
            
            const volMapped = older.map((b, i) => ({
              time: b.time,
              value: b.volume ?? 0,
              color: (i>0 && older[i].close >= older[i-1].close) ? 'rgba(22,163,74,0.6)' : 'rgba(239,68,68,0.6)'
            }));
            const combinedVol = [...volMapped, ...volumeRef.current];
            const uniqueVolCombined = combinedVol.reduce((acc, current) => {
              const existing = acc.find(item => item.time === current.time);
              if (!existing) {
                acc.push(current);
              }
              return acc;
            }, []);
            uniqueVolCombined.sort((a, b) => a.time - b.time);
            volumeRef.current = uniqueVolCombined;
            
            seriesRef.current.setData(dataRef.current);
            if (volumeSeriesRef.current) volumeSeriesRef.current.setData(volumeRef.current);
            const closes = dataRef.current.map(b => b.close);
            const ema1 = computeEMA(closes, emaPeriod1, dataRef.current);
            const ema2 = computeEMA(closes, emaPeriod2, dataRef.current);
            ema20DataRef.current = ema1;
            ema50DataRef.current = ema2;
            if (ema20SeriesRef.current) ema20SeriesRef.current.setData(ema1);
            if (ema50SeriesRef.current) ema50SeriesRef.current.setData(ema2);
            if (prevRange && chartRef.current?.timeScale) {
              try { chartRef.current.timeScale().setVisibleRange(prevRange); } catch {}
            }
          }
          setLoadingMore(false);
          loadMoreBusyRef.current = false;
        }
      } catch (e) {
        console.error('Infinite scroll load error:', e);
        setLoadingMore(false);
        loadMoreBusyRef.current = false;
      }
    });

    // Load initial historical candles
    (async () => {
      try {
        const hist = await getCandles(symbol, interval, historyLimit);
        if (Array.isArray(hist) && hist.length > 0 && seriesRef.current) {
          // 중복 제거 및 시간 순서대로 정렬
          const uniqueHist = hist.reduce((acc, current) => {
            const existing = acc.find(item => item.time === current.time);
            if (!existing) {
              acc.push(current);
            }
            return acc;
          }, []);
          
          const sortedHist = uniqueHist.sort((a, b) => a.time - b.time);
          
          dataRef.current = sortedHist.map(b => ({
            time: b.time,
            open: b.open,
            high: b.high,
            low: b.low,
            close: b.close,
          }));
          
          // Volume data
          volumeRef.current = sortedHist.map((b, i) => ({
            time: b.time,
            value: b.volume ?? 0,
            color: (i > 0 && b.close >= sortedHist[i-1].close) ? 'rgba(22,163,74,0.6)' : 'rgba(239,68,68,0.6)'
          }));
          // set current minute reference to last bar time
          const last = dataRef.current[dataRef.current.length - 1];
          currentMinuteRef.current = last?.time ?? null;
          seriesRef.current.setData(dataRef.current);
          if (volumeSeriesRef.current) volumeSeriesRef.current.setData(volumeRef.current);

          // Compute and set EMAs
          const closes = dataRef.current.map(b => b.close);
          const ema20 = computeEMA(closes, emaPeriod1, dataRef.current);
          const ema50 = computeEMA(closes, emaPeriod2, dataRef.current);
          ema20DataRef.current = ema20;
          ema50DataRef.current = ema50;
          if (ema20SeriesRef.current) ema20SeriesRef.current.setData(ema20);
          if (ema50SeriesRef.current) ema50SeriesRef.current.setData(ema50);

          // Restore saved visible range
          try {
            const savedRange = localStorage.getItem('chartVisibleRange');
            if (savedRange) {
              const r = JSON.parse(savedRange);
              if (r && r.from && r.to && chart.timeScale) {
                chart.timeScale().setVisibleRange({ from: r.from, to: r.to });
              }
            }
          } catch {}
        }
      } catch (e) {
        console.error('초기 캔들 로드 실패:', e);
      }
    })();

    return () => {
      if (resizeObserverRef.current) resizeObserverRef.current.disconnect();
      if (chartRef.current) chartRef.current.remove();
      try { chart.unsubscribeCrosshairMove(moveHandler); } catch {}
      if (tooltip && tooltip.parentNode) tooltip.parentNode.removeChild(tooltip);
      chartRef.current = null;
      seriesRef.current = null;
      priceLinesRef.current = [];
    };
  }, [interval, historyLimit, symbol]);

  // Push latest price into 1-minute candle aggregation
  useEffect(() => {
    if (!seriesRef.current || latestPrice == null) return;
    const nowSec = Math.floor(Date.now() / 1000);
    const minute = Math.floor(nowSec / bucketSeconds) * bucketSeconds; // epoch bucket
    const price = Number(latestPrice);

    let candles = dataRef.current;
    const last = candles[candles.length - 1];

    if (currentMinuteRef.current === null) {
      currentMinuteRef.current = minute;
    }

    if (!last || last.time !== minute) {
      // start new candle
      const bar = { time: minute, open: price, high: price, low: price, close: price };
      candles.push(bar);
      currentMinuteRef.current = minute;
      // keep at most 1000 candles
      if (candles.length > 1000) candles.shift();
      // push volume 0 for now (no per-trade vol here)
      volumeRef.current.push({ time: minute, value: 0, color: 'rgba(148,163,184,0.6)' });
      if (volumeRef.current.length > 1000) volumeRef.current.shift();
    } else {
      // update existing candle
      last.high = Math.max(last.high, price);
      last.low = Math.min(last.low, price);
      last.close = price;
      // Update volume color based on direction
      const v = volumeRef.current[volumeRef.current.length - 1];
      if (v && v.time === minute) {
        const prevClose = candles.length > 1 ? candles[candles.length - 2].close : last.open;
        v.color = (last.close >= prevClose) ? 'rgba(22,163,74,0.6)' : 'rgba(239,68,68,0.6)';
      }
    }

    // 데이터 정렬 보장
    candles.sort((a, b) => a.time - b.time);
    volumeRef.current.sort((a, b) => a.time - b.time);
    
    seriesRef.current.setData(candles);
    if (volumeSeriesRef.current) volumeSeriesRef.current.setData(volumeRef.current);

    // Recompute EMAs incrementally
    const closes = candles.map(b => b.close);
    const ema20 = computeEMA(closes, emaPeriod1, candles);
    const ema50 = computeEMA(closes, emaPeriod2, candles);
    if (ema20SeriesRef.current) ema20SeriesRef.current.setData(ema20);
    if (ema50SeriesRef.current) ema50SeriesRef.current.setData(ema50);
  }, [latestPrice, emaPeriod1, emaPeriod2]);

  // Apply visibility when toggles change
  useEffect(() => {
    if (ema20SeriesRef.current) ema20SeriesRef.current.applyOptions({ visible: showEMA20 });
    try { localStorage.setItem('chartShowEMA20', showEMA20 ? '1' : '0'); } catch {}
  }, [showEMA20]);

  useEffect(() => {
    if (ema50SeriesRef.current) ema50SeriesRef.current.applyOptions({ visible: showEMA50 });
    try { localStorage.setItem('chartShowEMA50', showEMA50 ? '1' : '0'); } catch {}
  }, [showEMA50]);

  useEffect(() => {
    if (volumeSeriesRef.current) volumeSeriesRef.current.applyOptions({ visible: showVolume });
    try { localStorage.setItem('chartShowVolume', showVolume ? '1' : '0'); } catch {}
  }, [showVolume]);

  // Update horizontal price lines for markers
  useEffect(() => {
    if (!seriesRef.current) return;
    // Remove existing lines
    priceLinesRef.current.forEach(line => {
      try { seriesRef.current.removePriceLine(line); } catch {}
    });
    priceLinesRef.current = [];

    const addLine = (price, title, color) => {
      if (price == null) return;
      const line = seriesRef.current.createPriceLine({
        price: Number(price),
        color,
        lineWidth: 2,
        lineStyle: 2, // dashed
        axisLabelVisible: true,
        title: `${title} ${formatCurrency(price)}`,
      });
      priceLinesRef.current.push(line);
    };

    addLine(priceMarkers.buyPrice, '매수가', '#22c55e');
    addLine(priceMarkers.liquidationPrice, '청산가', '#ef4444');
    addLine(priceMarkers.takeProfitPrice, '목표가', '#3b82f6');
    addLine(priceMarkers.stopLossPrice, '손절가', '#f56565');
  }, [priceMarkers]);

  // Load trades and place markers on chart
  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const trades = await getTrades();
        if (!mounted || !Array.isArray(trades) || !seriesRef.current) return;
        const markers = trades.map(t => {
          const ts = t.timestamp ? Math.floor(new Date(t.timestamp).getTime() / 1000) : undefined;
          const side = (t.side || '').toUpperCase();
          let color = '#3b82f6';
          let position = 'aboveBar';
          let shape = 'circle';
          if (side.includes('BUY') || side.includes('LONG')) {
            color = '#16a34a';
            shape = 'arrowUp';
            position = 'belowBar';
          } else if (side.includes('SELL') || side.includes('SHORT')) {
            color = '#ef4444';
            shape = 'arrowDown';
            position = 'aboveBar';
          } else if (side.includes('CLOSE')) {
            color = '#f59e0b';
            shape = 'square';
            position = 'aboveBar';
          }
          return {
            time: ts,
            position,
            color,
            shape,
            text: `${t.side} ${t.qty} @ ${t.price}`,
          };
        }).filter(m => m.time);
        // 시간 순서대로 정렬 (오래된 것부터)
        markers.sort((a, b) => a.time - b.time);
        seriesRef.current.setMarkers(markers);
      } catch(e) {
        console.error('거래 마커 로드 실패:', e);
      }
    }
    load();
    const timer = setInterval(load, 5000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);

  return (
    <div className="bg-white p-4 shadow rounded mb-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-semibold">{symbol} 실시간 가격 차트 (TradingView Lightweight)</h3>
        {latestPrice != null && (
          <span className="font-mono text-lg">{formatCurrency(latestPrice)}</span>
        )}
      </div>
      <div className="flex items-center gap-2 mb-3">
        {['1m','3m','5m','15m','30m','1h','2h','4h','6h','12h','1d','1w'].map(iv => (
          <button
            key={iv}
            onClick={() => {
              setIntervalState(iv);
              try { localStorage.setItem('chartInterval', iv); } catch {}
            }}
            className={`px-3 py-1 text-sm rounded border ${interval===iv? 'bg-blue-600 text-white border-blue-600':'border-gray-300 text-gray-700 hover:bg-gray-50'}`}
          >
            {iv}
          </button>
        ))}
        <div className="ml-4 flex items-center gap-2 text-sm">
          <span className="text-gray-600">History</span>
          {[300,500,1000].map(lim => (
            <button
              key={lim}
              onClick={() => { setHistoryLimit(lim); try { localStorage.setItem('chartHistoryLimit', String(lim)); } catch {} }}
              className={`px-2 py-1 rounded border ${historyLimit===lim? 'bg-gray-800 text-white border-gray-800':'border-gray-300 text-gray-700 hover:bg-gray-50'}`}
            >{lim}</button>
          ))}
        </div>
        <div className="ml-4 flex items-center gap-3 text-sm">
          <label className="inline-flex items-center gap-1">
            <input type="checkbox" checked={showEMA20} onChange={e => setShowEMA20(e.target.checked)} /> EMA20
          </label>
          <label className="inline-flex items-center gap-1">
            <input type="checkbox" checked={showEMA50} onChange={e => setShowEMA50(e.target.checked)} /> EMA50
          </label>
          <label className="inline-flex items-center gap-1">
            <input type="checkbox" checked={showVolume} onChange={e => setShowVolume(e.target.checked)} /> Volume
          </label>
          <label className="inline-flex items-center gap-1">
            P1
            <input
              type="number"
              min="2"
              max="500"
              value={emaPeriod1}
              onChange={(e) => {
                const v = Math.max(2, Math.min(500, parseInt(e.target.value) || 0));
                setEmaPeriod1(v);
                try { localStorage.setItem('chartEmaPeriod1', String(v)); } catch {}
              }}
              className="w-16 px-2 py-0.5 border border-gray-300 rounded"
            />
          </label>
          <label className="inline-flex items-center gap-1">
            P2
            <input
              type="number"
              min="2"
              max="500"
              value={emaPeriod2}
              onChange={(e) => {
                const v = Math.max(2, Math.min(500, parseInt(e.target.value) || 0));
                setEmaPeriod2(v);
                try { localStorage.setItem('chartEmaPeriod2', String(v)); } catch {}
              }}
              className="w-16 px-2 py-0.5 border border-gray-300 rounded"
            />
          </label>
          <div className="ml-2 flex items-center gap-2">
            <button
              className="px-2 py-1 text-xs border rounded"
              onClick={() => {
                setShowEMA20(true); setShowEMA50(true); setShowVolume(true);
                setEmaPeriod1(9); setEmaPeriod2(20);
                try {
                  localStorage.setItem('chartShowEMA20','1');
                  localStorage.setItem('chartShowEMA50','1');
                  localStorage.setItem('chartShowVolume','1');
                  localStorage.setItem('chartEmaPeriod1','9');
                  localStorage.setItem('chartEmaPeriod2','20');
                } catch {}
              }}
            >Scalping</button>
            <button
              className="px-2 py-1 text-xs border rounded"
              onClick={() => {
                setShowEMA20(true); setShowEMA50(true); setShowVolume(true);
                setEmaPeriod1(20); setEmaPeriod2(50);
                try {
                  localStorage.setItem('chartShowEMA20','1');
                  localStorage.setItem('chartShowEMA50','1');
                  localStorage.setItem('chartShowVolume','1');
                  localStorage.setItem('chartEmaPeriod1','20');
                  localStorage.setItem('chartEmaPeriod2','50');
                } catch {}
              }}
            >Swing</button>
            <button
              className="px-2 py-1 text-xs border rounded"
              onClick={() => {
                setShowEMA20(true); setShowEMA50(true); setShowVolume(true);
                setEmaPeriod1(50); setEmaPeriod2(200);
                try {
                  localStorage.setItem('chartShowEMA20','1');
                  localStorage.setItem('chartShowEMA50','1');
                  localStorage.setItem('chartShowVolume','1');
                  localStorage.setItem('chartEmaPeriod1','50');
                  localStorage.setItem('chartEmaPeriod2','200');
                } catch {}
              }}
            >Long</button>
            <button
              className="px-2 py-1 text-xs border rounded"
              onClick={() => {
                setShowEMA20(false); setShowEMA50(false); setShowVolume(false);
                try {
                  localStorage.setItem('chartShowEMA20','0');
                  localStorage.setItem('chartShowEMA50','0');
                  localStorage.setItem('chartShowVolume','0');
                } catch {}
              }}
            >Minimal</button>
          </div>
        </div>
      </div>
      <div ref={containerRef} style={{ width: '100%', height: '540px' }} />
      <div className="mt-3 flex justify-center">
        <button
          onClick={async () => {
            if (!seriesRef.current || !dataRef.current?.length || loadingMore) return;
            setLoadingMore(true);
            try {
              const first = dataRef.current[0];
              const endMs = first.time * 1000 - 1; // fetch older than first
              // keep current visible range to restore after prepend
              let prevRange;
              try { prevRange = chartRef.current?.timeScale()?.getVisibleRange(); } catch {}
              const older = await getCandles(symbol, interval, historyLimit, undefined, endMs);
              if (Array.isArray(older) && older.length) {
                const mapped = older.map(b => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close }));
                // 중복 제거 및 시간 순서대로 정렬
                const combined = [...mapped, ...dataRef.current];
                const uniqueCombined = combined.reduce((acc, current) => {
                  const existing = acc.find(item => item.time === current.time);
                  if (!existing) {
                    acc.push(current);
                  }
                  return acc;
                }, []);
                uniqueCombined.sort((a, b) => a.time - b.time);
                dataRef.current = uniqueCombined;
                
                // volume prepend
                const volMapped = older.map((b, i) => ({
                  time: b.time,
                  value: b.volume ?? 0,
                  color: (i>0 && older[i].close >= older[i-1].close) ? 'rgba(22,163,74,0.6)' : 'rgba(239,68,68,0.6)'
                }));
                const combinedVol = [...volMapped, ...volumeRef.current];
                const uniqueVolCombined = combinedVol.reduce((acc, current) => {
                  const existing = acc.find(item => item.time === current.time);
                  if (!existing) {
                    acc.push(current);
                  }
                  return acc;
                }, []);
                uniqueVolCombined.sort((a, b) => a.time - b.time);
                volumeRef.current = uniqueVolCombined;
                
                seriesRef.current.setData(dataRef.current);
                if (volumeSeriesRef.current) volumeSeriesRef.current.setData(volumeRef.current);
                // recompute EMAs for entire dataset
                const closes = dataRef.current.map(b => b.close);
                const ema1 = computeEMA(closes, emaPeriod1, dataRef.current);
                const ema2 = computeEMA(closes, emaPeriod2, dataRef.current);
                if (ema20SeriesRef.current) ema20SeriesRef.current.setData(ema1);
                if (ema50SeriesRef.current) ema50SeriesRef.current.setData(ema2);
                // restore visible range to avoid jump
                if (prevRange && chartRef.current?.timeScale) {
                  try { chartRef.current.timeScale().setVisibleRange(prevRange); } catch {}
                }
              }
            } catch (e) {
              console.error('과거 캔들 로드 실패:', e);
            } finally {
              setLoadingMore(false);
            }
          }}
          className={`px-4 py-2 text-sm rounded border ${loadingMore? 'opacity-60 cursor-not-allowed' : 'hover:bg-gray-50'} border-gray-300`}
          disabled={loadingMore}
        >{loadingMore? 'Loading...' : 'Load more history'}</button>
      </div>
    </div>
  );
}

function computeEMA(values, period, candles) {
  const k = 2 / (period + 1);
  let ema = [];
  let prev;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (i === 0) {
      prev = v; // seed with first value
    } else {
      prev = v * k + prev * (1 - k);
    }
    ema.push({ time: candles[i].time, value: Number(prev.toFixed(2)) });
  }
  return ema;
}

function intervalToSeconds(iv) {
  switch (iv) {
    case '1m': return 60;
    case '3m': return 3*60;
    case '5m': return 5*60;
    case '15m': return 15*60;
    case '30m': return 30*60;
    case '1h': return 60*60;
    case '2h': return 2*60*60;
    case '4h': return 4*60*60;
    case '6h': return 6*60*60;
    case '12h': return 12*60*60;
    case '1d': return 24*60*60;
    case '1w': return 7*24*60*60;
    default: return 60;
  }
}
