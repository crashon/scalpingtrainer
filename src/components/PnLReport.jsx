import React, { useEffect, useState } from 'react';
import { getDailyPnL } from '../api';

export default function PnLReport() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadReport() {
      try {
        setError(null);
        const today = new Date().toISOString().split('T')[0];
        const data = await getDailyPnL(today);
        setReport(data);
      } catch (e) {
        console.error('일일 손익 조회 실패:', e);
        setError('손익 데이터를 불러올 수 없습니다.');
      } finally {
        setLoading(false);
      }
    }
    loadReport();
  }, []);

  if (loading) {
    return (
      <div className="bg-white p-4 shadow rounded mt-4">
        <h3 className="font-semibold mb-2">일일 손익 리포트</h3>
        <div className="text-center py-4 text-gray-500">
          로딩 중...
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white p-4 shadow rounded mt-4">
      <h3 className="font-semibold mb-2">일일 손익 리포트</h3>
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      {report ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-50 p-3 rounded">
            <div className="text-sm text-gray-600">날짜</div>
            <div className="text-lg font-semibold">{report.date}</div>
          </div>
          <div className="bg-gray-50 p-3 rounded">
            <div className="text-sm text-gray-600">일일 손익</div>
            <div className={`text-lg font-semibold ${
              (report.daily_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {(report.daily_pnl || 0) >= 0 ? '+' : ''}${(report.daily_pnl || 0).toFixed(2)}
            </div>
          </div>
          <div className="bg-gray-50 p-3 rounded">
            <div className="text-sm text-gray-600">거래 횟수</div>
            <div className="text-lg font-semibold">{report.num_trades || 0}회</div>
          </div>
        </div>
      ) : (
        <div className="text-center py-4 text-gray-500">
          오늘 거래 내역이 없습니다.
        </div>
      )}
    </div>
  );
}
