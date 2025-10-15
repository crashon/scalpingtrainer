import React, { useState, useEffect } from 'react';
import { notifyFormatSettingsChanged } from '../utils/format';

export default function Settings() {
  // Account Settings
  const [totalAssets, setTotalAssets] = useState(10000);
  const [accountBalances, setAccountBalances] = useState({
    binance: 5000,
    bybit: 3000,
    okx: 2000
  });

  // Trading Personality
  const [personality, setPersonality] = useState('moderate');
  const [investmentStyle, setInvestmentStyle] = useState('short');

  // Risk Management
  const [dailyTradeLimit, setDailyTradeLimit] = useState(10);
  const [consecutiveStopLossLimit, setConsecutiveStopLossLimit] = useState(3);
  const [defaultLeverage, setDefaultLeverage] = useState(20);
  const [defaultStopLoss, setDefaultStopLoss] = useState(2);
  const [defaultTakeProfit, setDefaultTakeProfit] = useState(5);

  // Loss Limits
  const [dailyLossLimit, setDailyLossLimit] = useState(500);
  const [weeklyLossLimit, setWeeklyLossLimit] = useState(2000);
  const [monthlyLossLimit, setMonthlyLossLimit] = useState(5000);

  // Position Management
  const [maxPositionSize, setMaxPositionSize] = useState(1000);
  const [reEntryAfterProfit, setReEntryAfterProfit] = useState(false);
  const [reEntryWaitTime, setReEntryWaitTime] = useState(30); // minutes

  // Notification Settings
  const [notifications, setNotifications] = useState({
    tradeAlerts: true,
    profitAlerts: true,
    lossAlerts: true,
    dailyReport: true
  });

  // Number Formatting Settings
  const [currencyDecimals, setCurrencyDecimals] = useState(2);
  const [priceDecimals, setPriceDecimals] = useState(2);
  const [qtyDecimals, setQtyDecimals] = useState(6);

  // Load settings from localStorage on component mount
  useEffect(() => {
    const savedSettings = localStorage.getItem('scalpingTrainerSettings');
    if (savedSettings) {
      const settings = JSON.parse(savedSettings);
      setTotalAssets(settings.totalAssets || 10000);
      setAccountBalances(settings.accountBalances || { binance: 5000, bybit: 3000, okx: 2000 });
      setPersonality(settings.personality || 'moderate');
      setInvestmentStyle(settings.investmentStyle || 'short');
      setDailyTradeLimit(settings.dailyTradeLimit || 10);
      setConsecutiveStopLossLimit(settings.consecutiveStopLossLimit || 3);
      setDefaultLeverage(settings.defaultLeverage || 20);
      setDefaultStopLoss(settings.defaultStopLoss || 2);
      setDefaultTakeProfit(settings.defaultTakeProfit || 5);
      setDailyLossLimit(settings.dailyLossLimit || 500);
      setWeeklyLossLimit(settings.weeklyLossLimit || 2000);
      setMonthlyLossLimit(settings.monthlyLossLimit || 5000);
      setMaxPositionSize(settings.maxPositionSize || 1000);
      setReEntryAfterProfit(settings.reEntryAfterProfit || false);
      setReEntryWaitTime(settings.reEntryWaitTime || 30);
      setNotifications(settings.notifications || {
        tradeAlerts: true,
        profitAlerts: true,
        lossAlerts: true,
        dailyReport: true
      });
    }

    // Load number formatting from localStorage (used by formatters)
    const cd = parseInt(localStorage.getItem('currencyDecimals'));
    const pd = parseInt(localStorage.getItem('priceDecimals'));
    const qd = parseInt(localStorage.getItem('qtyDecimals'));
    setCurrencyDecimals(Number.isFinite(cd) ? cd : 2);
    setPriceDecimals(Number.isFinite(pd) ? pd : 2);
    setQtyDecimals(Number.isFinite(qd) ? qd : 6);
  }, []);

  // Save settings to localStorage
  const saveSettings = () => {
    const settings = {
      totalAssets,
      accountBalances,
      personality,
      investmentStyle,
      dailyTradeLimit,
      consecutiveStopLossLimit,
      defaultLeverage,
      defaultStopLoss,
      defaultTakeProfit,
      dailyLossLimit,
      weeklyLossLimit,
      monthlyLossLimit,
      maxPositionSize,
      reEntryAfterProfit,
      reEntryWaitTime,
      notifications
    };
    
    localStorage.setItem('scalpingTrainerSettings', JSON.stringify(settings));
    // Save number formatting settings for format utils
    localStorage.setItem('currencyDecimals', String(currencyDecimals));
    localStorage.setItem('priceDecimals', String(priceDecimals));
    localStorage.setItem('qtyDecimals', String(qtyDecimals));
    notifyFormatSettingsChanged();
    alert('설정이 저장되었습니다!');
  };

  // Reset to default settings
  const resetSettings = () => {
    if (confirm('모든 설정을 기본값으로 초기화하시겠습니까?')) {
      setTotalAssets(10000);
      setAccountBalances({ binance: 5000, bybit: 3000, okx: 2000 });
      setPersonality('moderate');
      setInvestmentStyle('short');
      setDailyTradeLimit(10);
      setConsecutiveStopLossLimit(3);
      setDefaultLeverage(20);
      setDefaultStopLoss(2);
      setDefaultTakeProfit(5);
      setDailyLossLimit(500);
      setWeeklyLossLimit(2000);
      setMonthlyLossLimit(5000);
      setMaxPositionSize(1000);
      setReEntryAfterProfit(false);
      setReEntryWaitTime(30);
      setNotifications({
        tradeAlerts: true,
        profitAlerts: true,
        lossAlerts: true,
        dailyReport: true
      });
      localStorage.removeItem('scalpingTrainerSettings');
      localStorage.removeItem('currencyDecimals');
      localStorage.removeItem('priceDecimals');
      localStorage.removeItem('qtyDecimals');
      setCurrencyDecimals(2);
      setPriceDecimals(2);
      setQtyDecimals(6);
      notifyFormatSettingsChanged();
    }
  };

  const updateAccountBalance = (exchange, value) => {
    setAccountBalances(prev => ({
      ...prev,
      [exchange]: parseFloat(value) || 0
    }));
  };

  const updateNotification = (key, value) => {
    setNotifications(prev => ({
      ...prev,
      [key]: value
    }));
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white p-6 shadow rounded-lg">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">거래 설정</h2>
        
        {/* Account Settings */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">계좌 설정</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                총 자산 (USD)
              </label>
              <input
                type="number"
                value={totalAssets}
                onChange={(e) => setTotalAssets(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700">거래소별 잔고</label>
              {Object.entries(accountBalances).map(([exchange, balance]) => (
                <div key={exchange} className="flex items-center space-x-2">
                  <span className="w-16 text-sm font-medium capitalize">{exchange}:</span>
                  <input
                    type="number"
                    value={balance}
                    onChange={(e) => updateAccountBalance(exchange, e.target.value)}
                    className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-500">USD</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Trading Personality */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">거래 성향</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">투자 성향</label>
              <select
                value={personality}
                onChange={(e) => setPersonality(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="aggressive">공격적</option>
                <option value="moderate">보통</option>
                <option value="conservative">보수적</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">투자 방식</label>
              <select
                value={investmentStyle}
                onChange={(e) => setInvestmentStyle(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="ultra-short">초단타 (1-5분)</option>
                <option value="short">단타 (5-30분)</option>
                <option value="mid">중기 (30분-2시간)</option>
                <option value="long">장기 (2시간+)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Risk Management */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">리스크 관리</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">일일 거래 한도</label>
              <input
                type="number"
                value={dailyTradeLimit}
                onChange={(e) => setDailyTradeLimit(parseInt(e.target.value) || 0)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">연속 손절 한도</label>
              <input
                type="number"
                value={consecutiveStopLossLimit}
                onChange={(e) => setConsecutiveStopLossLimit(parseInt(e.target.value) || 0)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">최대 포지션 크기 (USD)</label>
              <input
                type="number"
                value={maxPositionSize}
                onChange={(e) => setMaxPositionSize(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Default Trading Parameters */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">기본 거래 설정</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">기본 레버리지</label>
              <select
                value={defaultLeverage}
                onChange={(e) => setDefaultLeverage(parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {[2, 3, 5, 10, 20, 25, 30, 50, 100].map(lev => (
                  <option key={lev} value={lev}>{lev}x</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">기본 손절 (%)</label>
              <select
                value={defaultStopLoss}
                onChange={(e) => setDefaultStopLoss(parseFloat(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {[1, 2, 3, 5, 7, 10, 15, 20].map(pct => (
                  <option key={pct} value={pct}>{pct}%</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">기본 익절 (%)</label>
              <select
                value={defaultTakeProfit}
                onChange={(e) => setDefaultTakeProfit(parseFloat(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {[5, 10, 20, 50, 100].map(pct => (
                  <option key={pct} value={pct}>{pct}%</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Loss Limits */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">손실 한도</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">일일 손실 한도 (USD)</label>
              <input
                type="number"
                value={dailyLossLimit}
                onChange={(e) => setDailyLossLimit(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">주간 손실 한도 (USD)</label>
              <input
                type="number"
                value={weeklyLossLimit}
                onChange={(e) => setWeeklyLossLimit(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">월간 손실 한도 (USD)</label>
              <input
                type="number"
                value={monthlyLossLimit}
                onChange={(e) => setMonthlyLossLimit(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Re-entry Settings */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">재진입 설정</h3>
          <div className="space-y-4">
            <div className="flex items-center">
              <input
                type="checkbox"
                id="reEntryAfterProfit"
                checked={reEntryAfterProfit}
                onChange={(e) => setReEntryAfterProfit(e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="reEntryAfterProfit" className="ml-2 block text-sm text-gray-900">
                수익 후 재진입 제한
              </label>
            </div>
            
            {reEntryAfterProfit && (
              <div className="ml-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">대기 시간 (분)</label>
                <input
                  type="number"
                  value={reEntryWaitTime}
                  onChange={(e) => setReEntryWaitTime(parseInt(e.target.value) || 0)}
                  className="w-32 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
          </div>
        </div>

        {/* Notification Settings */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">알림 설정</h3>
          <div className="space-y-3">
            {Object.entries(notifications).map(([key, value]) => (
              <div key={key} className="flex items-center">
                <input
                  type="checkbox"
                  id={key}
                  checked={value}
                  onChange={(e) => updateNotification(key, e.target.checked)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor={key} className="ml-2 block text-sm text-gray-900">
                  {key === 'tradeAlerts' && '거래 알림'}
                  {key === 'profitAlerts' && '수익 알림'}
                  {key === 'lossAlerts' && '손실 알림'}
                  {key === 'dailyReport' && '일일 리포트'}
                </label>
              </div>
            ))}
          </div>
        </div>

        {/* Number Formatting */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">표시 소수점 자리수</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">통화 소수점 (USD)</label>
              <select
                value={currencyDecimals}
                onChange={(e) => setCurrencyDecimals(parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {[0,1,2,3,4].map(n => (
                  <option key={n} value={n}>{n}자리</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">가격 소수점</label>
              <select
                value={priceDecimals}
                onChange={(e) => setPriceDecimals(parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {[0,1,2,3,4].map(n => (
                  <option key={n} value={n}>{n}자리</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">수량 소수점</label>
              <select
                value={qtyDecimals}
                onChange={(e) => setQtyDecimals(parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {[0,2,4,6,8].map(n => (
                  <option key={n} value={n}>{n}자리</option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-2">변경 사항은 즉시 적용됩니다. 반영되지 않으면 새로고침하세요.</p>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end space-x-4 pt-6 border-t">
          <button
            onClick={resetSettings}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            초기화
          </button>
          <button
            onClick={saveSettings}
            className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            설정 저장
          </button>
        </div>
      </div>
    </div>
  );
}
