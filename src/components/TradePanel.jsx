import React, { useState, useEffect } from 'react';
import { placeOrder, getPosition, closePosition } from '../api';
import { formatCurrency, formatPrice, formatQty, formatSignedCurrency } from '../utils/format';

export default function TradePanel({ latestPrice, onOrderPlaced, onPriceMarkersChange }) {
  const [qty, setQty] = useState(0.01);
  const [leverage, setLeverage] = useState(20);
  const [takeProfitPct, setTakeProfitPct] = useState(5);
  const [stopLossPct, setStopLossPct] = useState(2);
  const [isLoading, setIsLoading] = useState(false);

  // 현재 포지션
  const [position, setPosition] = useState({ side: null, qty: 0, entry_price: null, unrealized_pnl: 0, latest_price: null });
  const [closing, setClosing] = useState(false);

  // 계산된 가격들
  const [liquidationPrice, setLiquidationPrice] = useState(0);
  const [takeProfitPrice, setTakeProfitPrice] = useState(0);
  const [stopLossPrice, setStopLossPrice] = useState(0);

  const leverageOptions = [100, 50, 30, 25, 10, 5, 3, 2];
  const takeProfitOptions = [5, 10, 20, 50, 100];
  const stopLossOptions = [1, 2, 3, 5, 7, 10, 15, 20];

  // 가격 계산
  useEffect(() => {
    if (!latestPrice) return;

    // 청산가격 계산 (레버리지에 따른 대략적인 계산)
    const liquidation = latestPrice * (1 - (0.9 / leverage));
    setLiquidationPrice(liquidation);

    // 목표가격 계산 (매수가 기준)
    const takeProfit = latestPrice * (1 + takeProfitPct / 100);
    setTakeProfitPrice(takeProfit);

    // 손절가격 계산 (매수가 기준)
    const stopLoss = latestPrice * (1 - stopLossPct / 100);
    setStopLossPrice(stopLoss);

    // 가격 마커를 상위 컴포넌트에 전달
    if (onPriceMarkersChange) {
      onPriceMarkersChange({
        buyPrice: latestPrice,
        liquidationPrice: liquidation,
        takeProfitPrice: takeProfit,
        stopLossPrice: stopLoss
      });
    }
  }, [latestPrice, leverage, takeProfitPct, stopLossPct, onPriceMarkersChange]);

  // 포지션 폴링
  useEffect(() => {
    let mounted = true;
    const loadPosition = async () => {
      try {
        const pos = await getPosition('BTCUSDT');
        if (mounted) setPosition(pos || {});
      } catch (e) {
        console.error('포지션 조회 실패:', e);
      }
    };
    loadPosition();
    const t = setInterval(loadPosition, 5000);
    return () => {
      mounted = false;
      clearInterval(t);
    };
  }, []);

  const handleOrder = async (side) => {
    if (!latestPrice) {
      alert('가격 정보를 기다리는 중입니다...');
      return;
    }

    setIsLoading(true);
    const payload = {
      symbol: 'BTCUSDT',
      side: side.toUpperCase(),
      price: latestPrice,
      qty: qty,
      leverage: leverage,
      takeProfitPrice: takeProfitPrice,
      stopLossPrice: stopLossPrice,
      liquidationPrice: liquidationPrice
    };

    try {
      const res = await placeOrder(payload);
      if (onOrderPlaced) onOrderPlaced(res);
      // 포지션 갱신
      try {
        const pos = await getPosition('BTCUSDT');
        setPosition(pos || {});
      } catch {}
      alert(`${side} 주문 완료 (ID: ${res.trade_id})\n레버리지: ${leverage}x\n목표가: ${formatCurrency(takeProfitPrice)}\n손절가: ${formatCurrency(stopLossPrice)}`);
    } catch (e) {
      console.error('주문 오류:', e);
      alert('주문 실패: ' + e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClosePosition = async () => {
    if (!position || !position.side) return;
    setClosing(true);
    try {
      const res = await closePosition('BTCUSDT');
      // 포지션 새로고침
      const pos = await getPosition('BTCUSDT');
      setPosition(pos || {});
      alert(`포지션 청산 완료\n실현 손익: $${(res?.realized_pnl ?? 0).toLocaleString()}\n가격: $${(res?.price ?? 0).toLocaleString()}`);
    } catch (e) {
      console.error('청산 실패:', e);
      alert('포지션 청산 실패: ' + e.message);
    } finally {
      setClosing(false);
    }
  };

  const handlePartialClose = async (ratio) => {
    if (!position || !position.side || !position.qty || position.qty <= 0) return;
    const qty = Math.max(0, +(position.qty * ratio).toFixed(6));
    if (qty <= 0) return;
    setClosing(true);
    try {
      const res = await closePosition('BTCUSDT', undefined, qty);
      const pos = await getPosition('BTCUSDT');
      setPosition(pos || {});
      alert(`부분 청산(${Math.round(ratio*100)}%) 완료\n청산 수량: ${formatQty(qty)}\n실현 손익: ${formatSignedCurrency(res?.realized_pnl ?? 0)}\n가격: ${formatCurrency(res?.price ?? 0)}`);
    } catch (e) {
      console.error('부분 청산 실패:', e);
      alert('부분 청산 실패: ' + e.message);
    } finally {
      setClosing(false);
    }
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow mb-4">
      <h3 className="text-lg font-semibold mb-4">거래 패널</h3>
      
      {/* 첫 번째 행: 수량, 레버리지 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            수량 (BTC)
          </label>
          <input
            type="number"
            step="0.001"
            min="0.001"
            value={qty}
            onChange={(e) => setQty(parseFloat(e.target.value) || 0.001)}
            className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            레버리지
          </label>
          <select
            value={leverage}
            onChange={(e) => setLeverage(parseInt(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500"
          >
            {leverageOptions.map(lev => (
              <option key={lev} value={lev}>{lev}x</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            목표 수익률 (%)
          </label>
          <select
            value={takeProfitPct}
            onChange={(e) => setTakeProfitPct(parseInt(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500"
          >
            {takeProfitOptions.map(pct => (
              <option key={pct} value={pct}>{pct}%</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            손절 비율 (%)
          </label>
          <select
            value={stopLossPct}
            onChange={(e) => setStopLossPct(parseInt(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500"
          >
            {stopLossOptions.map(pct => (
              <option key={pct} value={pct}>{pct}%</option>
            ))}
          </select>
        </div>
      </div>

      {/* 가격 정보 표시 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 p-3 bg-gray-50 rounded">
        <div className="text-center">
          <div className="text-xs text-gray-500">현재가</div>
          <div className="font-mono font-semibold text-blue-600">
            {latestPrice != null ? formatCurrency(latestPrice) : '...'}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500">청산가격</div>
          <div className="font-mono font-semibold text-red-600">
            {formatCurrency(liquidationPrice)}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500">목표가격</div>
          <div className="font-mono font-semibold text-green-600">
            {formatCurrency(takeProfitPrice)}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500">손절가격</div>
          <div className="font-mono font-semibold text-orange-600">
            {formatCurrency(stopLossPrice)}
          </div>
        </div>
      </div>

      {/* 예상 금액 및 수익/손실 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4 text-sm text-gray-600">
        <div>
          예상 투자금액: {latestPrice ? formatCurrency(latestPrice * qty) : '...'}
        </div>
        <div className="text-green-600">
          예상 수익: {latestPrice ? formatCurrency((takeProfitPrice - latestPrice) * qty) : '...'}
        </div>
        <div className="text-red-600">
          예상 손실: {latestPrice ? formatCurrency((latestPrice - stopLossPrice) * qty) : '...'}
        </div>
      </div>

      {/* 현재 포지션 */}
      <div className="mb-4 p-4 border rounded bg-gray-50">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">현재 포지션:</span>
            {position?.side ? (
              <span className={`px-2 py-1 rounded text-xs font-semibold ${position.side === 'BUY' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                {position.side === 'BUY' ? 'LONG (매수)' : 'SHORT (매도)'}
              </span>
            ) : (
              <span className="text-sm text-gray-500">없음</span>
            )}
          </div>
          {position?.side && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-gray-500">수량</div>
                <div className="font-mono">{formatQty(position.qty)}</div>
              </div>
              <div>
                <div className="text-gray-500">평단가</div>
                <div className="font-mono">{position.entry_price != null ? formatCurrency(position.entry_price) : '-'}</div>
              </div>
              <div>
                <div className="text-gray-500">현재가</div>
                <div className="font-mono">{position.latest_price != null ? formatCurrency(position.latest_price) : '-'}</div>
              </div>
              <div>
                <div className="text-gray-500">미실현손익</div>
                <div className={`font-mono font-semibold ${position.unrealized_pnl > 0 ? 'text-green-600' : position.unrealized_pnl < 0 ? 'text-red-600' : 'text-gray-700'}`}>
                  {formatSignedCurrency(position.unrealized_pnl)}
                </div>
              </div>
            </div>
          )}
          <div className="ml-auto">
            <button
              onClick={handleClosePosition}
              disabled={!position?.side || closing}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-100 disabled:opacity-50"
            >
              {closing ? '닫는 중...' : '포지션 닫기'}
            </button>
          </div>
        </div>
        {position?.side && (
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => handlePartialClose(0.25)}
              disabled={!position?.side || closing}
              className="px-3 py-1 text-xs rounded border border-gray-300 hover:bg-gray-100 disabled:opacity-50"
            >
              25% 닫기
            </button>
            <button
              onClick={() => handlePartialClose(0.5)}
              disabled={!position?.side || closing}
              className="px-3 py-1 text-xs rounded border border-gray-300 hover:bg-gray-100 disabled:opacity-50"
            >
              50% 닫기
            </button>
            <button
              onClick={() => handlePartialClose(1)}
              disabled={!position?.side || closing}
              className="px-3 py-1 text-xs rounded border border-gray-300 hover:bg-gray-100 disabled:opacity-50"
            >
              100% 닫기
            </button>
          </div>
        )}
      </div>

      {/* 주문 버튼 */}
      <div className="flex gap-3">
        <button 
          onClick={() => handleOrder('BUY')} 
          disabled={isLoading || !latestPrice}
          className="flex-1 bg-green-500 hover:bg-green-600 disabled:bg-gray-400 text-white px-6 py-3 rounded font-medium transition-colors"
        >
          {isLoading ? '처리 중...' : `매수 (LONG) ${leverage}x`}
        </button>
        <button 
          onClick={() => handleOrder('SELL')} 
          disabled={isLoading || !latestPrice}
          className="flex-1 bg-red-500 hover:bg-red-600 disabled:bg-gray-400 text-white px-6 py-3 rounded font-medium transition-colors"
        >
          {isLoading ? '처리 중...' : `매도 (SHORT) ${leverage}x`}
        </button>
      </div>
    </div>
  );
}
