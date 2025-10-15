import React, { useState, useEffect } from 'react';
import { getTrades, getDailyPnL } from '../api';

export default function TradingJournal() {
  const [trades, setTrades] = useState([]);
  const [dailyReports, setDailyReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [viewMode, setViewMode] = useState('daily'); // 'daily' or 'summary'

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, [selectedDate]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [tradesData, pnlData] = await Promise.all([
        getTrades(),
        getDailyPnL(selectedDate)
      ]);
      
      setTrades(Array.isArray(tradesData) ? tradesData : []);
      
      // Generate daily reports from trades
      const reports = generateDailyReports(Array.isArray(tradesData) ? tradesData : []);
      setDailyReports(reports);
      
    } catch (error) {
      console.error('매매일지 데이터 로딩 실패:', error);
      setTrades([]);
      setDailyReports([]);
    } finally {
      setLoading(false);
    }
  };

  const generateDailyReports = (tradesData) => {
    const dailyGroups = {};
    
    tradesData.forEach(trade => {
      const date = new Date(trade.timestamp).toISOString().split('T')[0];
      if (!dailyGroups[date]) {
        dailyGroups[date] = {
          date,
          trades: [],
          totalPnL: 0,
          totalVolume: 0,
          winCount: 0,
          lossCount: 0,
          winRate: 0,
          avgWin: 0,
          avgLoss: 0,
          maxWin: 0,
          maxLoss: 0,
          tradingTime: { start: null, end: null }
        };
      }
      
      dailyGroups[date].trades.push(trade);
      dailyGroups[date].totalPnL += trade.pnl || 0;
      dailyGroups[date].totalVolume += trade.price * trade.qty;
      
      if (trade.pnl > 0) {
        dailyGroups[date].winCount++;
        dailyGroups[date].maxWin = Math.max(dailyGroups[date].maxWin, trade.pnl);
      } else if (trade.pnl < 0) {
        dailyGroups[date].lossCount++;
        dailyGroups[date].maxLoss = Math.min(dailyGroups[date].maxLoss, trade.pnl);
      }
      
      // Update trading time range
      const tradeTime = new Date(trade.timestamp);
      if (!dailyGroups[date].tradingTime.start || tradeTime < dailyGroups[date].tradingTime.start) {
        dailyGroups[date].tradingTime.start = tradeTime;
      }
      if (!dailyGroups[date].tradingTime.end || tradeTime > dailyGroups[date].tradingTime.end) {
        dailyGroups[date].tradingTime.end = tradeTime;
      }
    });
    
    // Calculate additional metrics
    Object.values(dailyGroups).forEach(report => {
      const totalTrades = report.winCount + report.lossCount;
      report.winRate = totalTrades > 0 ? (report.winCount / totalTrades * 100) : 0;
      
      const wins = report.trades.filter(t => t.pnl > 0);
      const losses = report.trades.filter(t => t.pnl < 0);
      
      report.avgWin = wins.length > 0 ? wins.reduce((sum, t) => sum + t.pnl, 0) / wins.length : 0;
      report.avgLoss = losses.length > 0 ? losses.reduce((sum, t) => sum + t.pnl, 0) / losses.length : 0;
    });
    
    return Object.values(dailyGroups).sort((a, b) => new Date(b.date) - new Date(a.date));
  };

  const getSelectedDateTrades = () => {
    return trades.filter(trade => {
      const tradeDate = new Date(trade.timestamp).toISOString().split('T')[0];
      return tradeDate === selectedDate;
    });
  };

  const getSelectedDateReport = () => {
    return dailyReports.find(report => report.date === selectedDate);
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(amount);
  };

  const getPnLColor = (pnl) => {
    if (pnl > 0) return 'text-green-600';
    if (pnl < 0) return 'text-red-600';
    return 'text-gray-600';
  };

  const getPnLBgColor = (pnl) => {
    if (pnl > 0) return 'bg-green-50 border-green-200';
    if (pnl < 0) return 'bg-red-50 border-red-200';
    return 'bg-gray-50 border-gray-200';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">매매일지 로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header Controls */}
      <div className="bg-white p-4 shadow rounded-lg">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <h2 className="text-2xl font-bold text-gray-900">매매일지</h2>
          
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700">보기 모드:</label>
              <select
                value={viewMode}
                onChange={(e) => setViewMode(e.target.value)}
                className="px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="daily">일별 상세</option>
                <option value="summary">요약 보기</option>
              </select>
            </div>
            
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700">날짜:</label>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>
      </div>

      {viewMode === 'daily' ? (
        /* Daily Detail View */
        <>
          {/* Daily Summary Card */}
          {(() => {
            const report = getSelectedDateReport();
            const selectedTrades = getSelectedDateTrades();
            
            if (!report && selectedTrades.length === 0) {
              return (
                <div className="bg-white p-8 shadow rounded-lg text-center">
                  <div className="text-gray-500">선택한 날짜에 거래 내역이 없습니다.</div>
                </div>
              );
            }
            
            return (
              <div className="bg-white p-6 shadow rounded-lg">
                <h3 className="text-lg font-semibold text-gray-800 mb-4">
                  {new Date(selectedDate).toLocaleDateString('ko-KR', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    weekday: 'long'
                  })} 거래 요약
                </h3>
                
                {report && (
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                    <div className={`p-3 rounded-lg border ${getPnLBgColor(report.totalPnL)}`}>
                      <div className="text-sm text-gray-600">총 손익</div>
                      <div className={`text-lg font-semibold ${getPnLColor(report.totalPnL)}`}>
                        {formatCurrency(report.totalPnL)}
                      </div>
                    </div>
                    
                    <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                      <div className="text-sm text-gray-600">총 거래</div>
                      <div className="text-lg font-semibold text-blue-600">
                        {report.trades.length}건
                      </div>
                    </div>
                    
                    <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                      <div className="text-sm text-gray-600">승률</div>
                      <div className="text-lg font-semibold text-green-600">
                        {report.winRate.toFixed(1)}%
                      </div>
                    </div>
                    
                    <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg">
                      <div className="text-sm text-gray-600">거래량</div>
                      <div className="text-lg font-semibold text-purple-600">
                        {formatCurrency(report.totalVolume)}
                      </div>
                    </div>
                    
                    <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                      <div className="text-sm text-gray-600">최대 수익</div>
                      <div className="text-lg font-semibold text-green-600">
                        {formatCurrency(report.maxWin)}
                      </div>
                    </div>
                    
                    <div className="p-3 bg-orange-50 border border-orange-200 rounded-lg">
                      <div className="text-sm text-gray-600">최대 손실</div>
                      <div className="text-lg font-semibold text-red-600">
                        {formatCurrency(report.maxLoss)}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })()}

          {/* Detailed Trade List */}
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-800">거래 내역</h3>
            </div>
            
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">시간</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">심볼</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">방향</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">가격</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">수량</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">거래금액</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">손익</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {getSelectedDateTrades().map((trade) => (
                    <tr key={trade.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatTime(trade.timestamp)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {trade.symbol}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          trade.side === 'BUY' 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {trade.side === 'BUY' ? '매수' : '매도'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatCurrency(trade.price)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {trade.qty}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatCurrency(trade.price * trade.qty)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <span className={`font-semibold ${getPnLColor(trade.pnl)}`}>
                          {trade.pnl ? formatCurrency(trade.pnl) : '-'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              
              {getSelectedDateTrades().length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  선택한 날짜에 거래 내역이 없습니다.
                </div>
              )}
            </div>
          </div>
        </>
      ) : (
        /* Summary View */
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-800">일별 거래 요약</h3>
          </div>
          
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">날짜</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">거래수</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">승률</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">총 손익</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">거래량</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">최대 수익</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">최대 손실</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {dailyReports.map((report) => (
                  <tr 
                    key={report.date} 
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => {
                      setSelectedDate(report.date);
                      setViewMode('daily');
                    }}
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {new Date(report.date).toLocaleDateString('ko-KR')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {report.trades.length}건
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {report.winRate.toFixed(1)}%
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`font-semibold ${getPnLColor(report.totalPnL)}`}>
                        {formatCurrency(report.totalPnL)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatCurrency(report.totalVolume)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-green-600 font-semibold">
                      {formatCurrency(report.maxWin)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-red-600 font-semibold">
                      {formatCurrency(report.maxLoss)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            
            {dailyReports.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                거래 내역이 없습니다.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
