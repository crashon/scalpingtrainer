import React, { useEffect, useState } from 'react';
import { getTrades } from '../api';
import { formatCurrency, formatQty, formatSignedCurrency } from '../utils/format';

export default function TradeTable() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        setError(null);
        const data = await getTrades();
        if (mounted) {
          setTrades(Array.isArray(data) ? data : []);
          setLoading(false);
        }
      } catch (e) {
        console.error('거래 내역 조회 실패:', e);
        if (mounted) {
          setError('거래 내역을 불러올 수 없습니다.');
          setTrades([]);
          setLoading(false);
        }
      }
    }
    load();
    const t = setInterval(load, 5000);
    return () => { 
      mounted = false; 
      clearInterval(t); 
    }
  }, []);

  if (loading) {
    return (
      <div className="bg-white p-4 shadow rounded mt-4">
        <h3 className="font-semibold mb-2">거래 내역</h3>
        <div className="text-center py-8 text-gray-500">
          로딩 중...
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white p-4 shadow rounded mt-4">
      <h3 className="font-semibold mb-2">거래 내역</h3>
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      <div className="overflow-auto">
        {trades.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            거래 내역이 없습니다. 첫 거래를 시작해보세요!
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase tracking-wider">시간</th>
                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase tracking-wider">가격</th>
                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase tracking-wider">수량</th>
                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase tracking-wider">방향</th>
                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase tracking-wider">손익</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {trades.map(t => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2 whitespace-nowrap">
                    {t.timestamp ? new Date(t.timestamp).toLocaleString('ko-KR') : '-'}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">
                    {formatCurrency(t.price || 0)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">
                    {formatQty(t.qty || 0)}
                  </td>
                  <td className={`px-3 py-2 text-right font-medium ${
                    t.side && (t.side.toLowerCase() === 'buy' || t.side.toLowerCase().includes('long')) 
                      ? 'text-green-600' 
                      : 'text-red-600'
                  }`}>
                    {t.side || '-'}
                  </td>
                  <td className={`px-3 py-2 text-right font-mono ${
                    (t.pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {formatSignedCurrency(t.pnl || 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
