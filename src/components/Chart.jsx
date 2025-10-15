import React, { useEffect, useRef, useState } from 'react';
import { Line } from 'react-chartjs-2';
import { 
  Chart as ChartJS, 
  LineElement, 
  PointElement, 
  CategoryScale, 
  LinearScale, 
  Tooltip, 
  Legend,
  TimeScale,
  Filler
} from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';
import { getTrades } from '../api';
import { formatCurrency, formatPrice } from '../utils/format';

ChartJS.register(LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend, TimeScale, Filler, annotationPlugin);

export default function Chart({ latestPrice, priceMarkers = {} }) {
  const [prices, setPrices] = useState([]);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [highLow, setHighLow] = useState({ high: null, low: null });
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;
    
    async function loadTrades() {
      try {
        const data = await getTrades();
        if (mounted.current) {
          setTrades(Array.isArray(data) ? data : []);
          setLoading(false);
        }
      } catch (e) {
        console.error('거래 데이터 로딩 실패:', e);
        if (mounted.current) {
          setTrades([]);
          setLoading(false);
        }
      }
    }

    loadTrades();
    const t = setInterval(loadTrades, 5000);

    return () => {
      mounted.current = false;
      clearInterval(t);
    }
  }, []);

  useEffect(() => {
    if (latestPrice == null) return;
    setPrices(prev => {
      const now = new Date().toLocaleTimeString();
      const next = [...prev.slice(-50), { time: now, price: latestPrice }];
      
      // Calculate high/low from recent prices
      if (next.length > 0) {
        const recentPrices = next.slice(-20); // Last 20 data points
        const high = Math.max(...recentPrices.map(p => p.price));
        const low = Math.min(...recentPrices.map(p => p.price));
        setHighLow({ high, low });
      }
      
      return next;
    });
  }, [latestPrice]);

  const chartData = {
    labels: prices.map(p => p.time || ''),
    datasets: [
      {
        label: 'BTC/USDT 실시간 가격',
        data: prices.map(p => p.price),
        borderColor: 'rgba(59,130,246,1)',
        backgroundColor: 'rgba(59,130,246,0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 2,
        pointHoverRadius: 6,
        borderWidth: 2
      }
    ]
  };

  // Create annotations for price markers
  const annotations = {};
  
  if (priceMarkers.buyPrice) {
    annotations.buyPrice = {
      type: 'line',
      yMin: priceMarkers.buyPrice,
      yMax: priceMarkers.buyPrice,
      borderColor: 'rgba(34, 197, 94, 0.8)',
      borderWidth: 2,
      borderDash: [5, 5],
      label: {
        content: `매수가: ${formatCurrency(priceMarkers.buyPrice)}`,
        enabled: true,
        position: 'end',
        backgroundColor: 'rgba(34, 197, 94, 0.8)',
        color: 'white',
        font: { size: 11 }
      }
    };
  }
  
  if (priceMarkers.liquidationPrice) {
    annotations.liquidationPrice = {
      type: 'line',
      yMin: priceMarkers.liquidationPrice,
      yMax: priceMarkers.liquidationPrice,
      borderColor: 'rgba(239, 68, 68, 0.8)',
      borderWidth: 2,
      borderDash: [10, 5],
      label: {
        content: `청산가: ${formatCurrency(priceMarkers.liquidationPrice)}`,
        enabled: true,
        position: 'end',
        backgroundColor: 'rgba(239, 68, 68, 0.8)',
        color: 'white',
        font: { size: 11 }
      }
    };
  }
  
  if (priceMarkers.takeProfitPrice) {
    annotations.takeProfitPrice = {
      type: 'line',
      yMin: priceMarkers.takeProfitPrice,
      yMax: priceMarkers.takeProfitPrice,
      borderColor: 'rgba(59, 130, 246, 0.8)',
      borderWidth: 2,
      borderDash: [15, 5],
      label: {
        content: `목표가: ${formatCurrency(priceMarkers.takeProfitPrice)}`,
        enabled: true,
        position: 'end',
        backgroundColor: 'rgba(59, 130, 246, 0.8)',
        color: 'white',
        font: { size: 11 }
      }
    };
  }
  
  if (priceMarkers.stopLossPrice) {
    annotations.stopLossPrice = {
      type: 'line',
      yMin: priceMarkers.stopLossPrice,
      yMax: priceMarkers.stopLossPrice,
      borderColor: 'rgba(245, 101, 101, 0.8)',
      borderWidth: 2,
      borderDash: [5, 10],
      label: {
        content: `손절가: ${formatCurrency(priceMarkers.stopLossPrice)}`,
        enabled: true,
        position: 'end',
        backgroundColor: 'rgba(245, 101, 101, 0.8)',
        color: 'white',
        font: { size: 11 }
      }
    };
  }
  
  if (highLow.high) {
    annotations.highPoint = {
      type: 'line',
      yMin: highLow.high,
      yMax: highLow.high,
      borderColor: 'rgba(168, 85, 247, 0.6)',
      borderWidth: 1,
      borderDash: [3, 3],
      label: {
        content: `고점: ${formatCurrency(highLow.high)}`,
        enabled: true,
        position: 'start',
        backgroundColor: 'rgba(168, 85, 247, 0.6)',
        color: 'white',
        font: { size: 10 }
      }
    };
  }
  
  if (highLow.low) {
    annotations.lowPoint = {
      type: 'line',
      yMin: highLow.low,
      yMax: highLow.low,
      borderColor: 'rgba(251, 146, 60, 0.6)',
      borderWidth: 1,
      borderDash: [3, 3],
      label: {
        content: `저점: ${formatCurrency(highLow.low)}`,
        enabled: true,
        position: 'start',
        backgroundColor: 'rgba(251, 146, 60, 0.6)',
        color: 'white',
        font: { size: 10 }
      }
    };
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          label: function(context) {
            return `가격: ${formatCurrency(context.parsed.y)}`;
          }
        }
      },
      annotation: {
        annotations
      }
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false
    },
    scales: {
      x: {
        display: true,
        title: {
          display: true,
          text: '시간'
        },
        ticks: {
          maxTicksLimit: 10
        }
      },
      y: {
        display: true,
        title: {
          display: true,
          text: '가격 (USD)'
        },
        ticks: {
          callback: function(value) {
            return formatCurrency(value);
          }
        }
      }
    }
  };

  return (
    <div className="bg-white p-4 shadow rounded mb-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-semibold">실시간 가격 차트</h3>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-600">
            데이터 포인트: {prices.length}
          </span>
          <span className="text-gray-600">
            거래 내역: {trades.length}개
          </span>
          {latestPrice != null && (
            <span className="font-mono text-lg">
              {formatCurrency(latestPrice)}
            </span>
          )}
        </div>
      </div>
      
      {loading ? (
        <div className="h-64 flex items-center justify-center text-gray-500">
          차트 로딩 중...
        </div>
      ) : prices.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-gray-500">
          실시간 데이터를 기다리는 중...
        </div>
      ) : (
        <div className="h-64">
          <Line data={chartData} options={options} />
        </div>
      )}
      
      {trades.length > 0 && (
        <div className="mt-4 pt-4 border-t">
          <h4 className="text-sm font-medium text-gray-700 mb-2">최근 거래</h4>
          <div className="flex gap-2 flex-wrap">
            {trades.slice(0, 5).map(trade => (
              <span
                key={trade.id}
                className={`px-2 py-1 rounded text-xs font-medium ${
                  trade.side === 'BUY' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                }`}
              >
                {trade.side} ${trade.price?.toLocaleString()} × {trade.qty}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
