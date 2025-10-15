import React, { useState, useEffect } from 'react';
import { api, connectWebSocket } from '../api';

const AITradingDashboard = () => {
  const [strategies, setStrategies] = useState([]);
  const [aiStatus, setAiStatus] = useState({});
  const [dashboardData, setDashboardData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [recentActivity, setRecentActivity] = useState([]);
  const [newStrategy, setNewStrategy] = useState({
    name: '',
    risk_level: 'MEDIUM',
    symbol: 'BTCUSDT',
    exchange_type: 'binance',
    timeframe: '5m',
    leverage_min: 5.0,
    leverage_max: 10.0,
    position_size_usd: 100.0,
    confidence_threshold: 0.6,
    max_daily_trades: 50,
    stop_loss_pct: 2.0,
    take_profit_pct: 3.0
  });

  useEffect(() => {
    loadData();
    
    // WebSocket 연결
    let ws = null;
    let reconnectTimeout = null;
    let isMounted = true;
    
    const connect = () => {
      if (!isMounted) return;
      
      try {
        ws = api.connectAITradingWebSocket();
        
        ws.onopen = () => {
          if (isMounted) {
            console.log('AI Trading WebSocket 연결됨');
          }
        };
        
            ws.onmessage = evt => {
              if (!isMounted) return;
              try {
                const data = JSON.parse(evt.data);
                const timestamp = new Date().toLocaleTimeString();
                
                if (data && data.type === 'ai_status') {
                  setAiStatus(data.data.status);
                  setDashboardData(data.data.dashboard);
                  
                  // 실시간 활동 로그 추가
                  const activity = {
                    time: timestamp,
                    type: 'status_update',
                    message: `AI 상태 업데이트: ${data.data.status?.is_running ? '실행 중' : '중지됨'}`,
                    data: data.data
                  };
                  setRecentActivity(prev => [activity, ...prev.slice(0, 19)]); // 최근 20개만 유지
                } else if (data && data.type === 'ai_activity') {
                  // AI 활동 메시지 처리
                  const activity = {
                    time: timestamp,
                    type: data.data.activity_type,
                    message: data.data.message,
                    data: data.data.data
                  };
                  setRecentActivity(prev => [activity, ...prev.slice(0, 19)]); // 최근 20개만 유지
                }
              } catch(e) {
                console.error('AI Trading WebSocket 메시지 파싱 오류:', e);
              }
            };
        
        ws.onclose = (event) => {
          if (!isMounted) return;
          console.log('AI Trading WebSocket 연결 종료', event.code, event.reason);
          
          // 정상적인 종료가 아닌 경우 재연결 시도
          if (event.code !== 1000 && event.code !== 1001) {
            reconnectTimeout = setTimeout(() => {
              if (isMounted) {
                connect();
              }
            }, 3000);
          }
        };
        
        ws.onerror = (error) => {
          if (!isMounted) return;
          console.error('AI Trading WebSocket 오류:', error);
        };
      } catch (error) {
        console.error('AI Trading WebSocket 연결 실패:', error);
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
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [strategiesRes, statusRes, dashboardRes] = await Promise.all([
        api.getAIStrategies(),
        api.getAIStatus(),
        api.getAIDashboard()
      ]);
      
      setStrategies(strategiesRes || []);
      setAiStatus(statusRes || {});
      setDashboardData(dashboardRes || {});
      setError(null);
    } catch (err) {
      setError('데이터를 불러오는 중 오류가 발생했습니다.');
      console.error('Error loading AI data:', err);
    } finally {
      setLoading(false);
    }
  };

  const createStrategy = async (e) => {
    e.preventDefault();
    try {
      console.log('Creating strategy with data:', newStrategy);
      const result = await api.createAIStrategy(newStrategy);
      console.log('Strategy creation result:', result);
      setShowCreateForm(false);
      setNewStrategy({
        name: '',
        risk_level: 'MEDIUM',
        symbol: 'BTCUSDT',
        exchange_type: 'binance',
        timeframe: '5m',
        leverage_min: 5.0,
        leverage_max: 10.0,
        position_size_usd: 100.0,
        confidence_threshold: 0.6,
        max_daily_trades: 50,
        stop_loss_pct: 2.0,
        take_profit_pct: 3.0
      });
      loadData();
    } catch (err) {
      setError('전략 생성 중 오류가 발생했습니다.');
      console.error('Error creating strategy:', err);
    }
  };

  const toggleStrategy = async (configId) => {
    try {
      await api.toggleAIStrategy(configId);
      loadData();
    } catch (err) {
      setError('전략 상태 변경 중 오류가 발생했습니다.');
      console.error('Error toggling strategy:', err);
    }
  };

  const deleteStrategy = async (configId) => {
    if (!window.confirm('정말로 이 전략을 삭제하시겠습니까?')) return;
    
    try {
      await api.deleteAIStrategy(configId);
      loadData();
    } catch (err) {
      setError('전략 삭제 중 오류가 발생했습니다.');
      console.error('Error deleting strategy:', err);
    }
  };

  const startAITrading = async () => {
    try {
      await api.startAITrading();
      loadData();
    } catch (err) {
      setError('AI 트레이딩 시작 중 오류가 발생했습니다.');
      console.error('Error starting AI trading:', err);
    }
  };

  const stopAITrading = async () => {
    try {
      await api.stopAITrading();
      loadData();
    } catch (err) {
      setError('AI 트레이딩 중지 중 오류가 발생했습니다.');
      console.error('Error stopping AI trading:', err);
    }
  };

  const getRiskLevelColor = (riskLevel) => {
    switch (riskLevel) {
      case 'HIGH': return 'text-red-600 bg-red-100';
      case 'MEDIUM': return 'text-yellow-600 bg-yellow-100';
      case 'LOW': return 'text-green-600 bg-green-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getRiskLevelText = (riskLevel) => {
    switch (riskLevel) {
      case 'HIGH': return '고위험';
      case 'MEDIUM': return '중위험';
      case 'LOW': return '저위험';
      default: return '알 수 없음';
    }
  };

  if (loading && strategies.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">AI 트레이딩 대시보드</h2>
        <div className="flex space-x-2">
          <button
            onClick={() => setShowCreateForm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            새 전략 생성
          </button>
          {aiStatus.is_running ? (
            <button
              onClick={stopAITrading}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              AI 트레이딩 중지
            </button>
          ) : (
            <button
              onClick={startAITrading}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              AI 트레이딩 시작
            </button>
          )}
        </div>
      </div>

      {/* 작동 방식 설명 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
        <h3 className="text-sm font-semibold text-blue-900 mb-2">🔄 AI 트레이딩 작동 방식</h3>
        <div className="text-sm text-blue-800 space-y-1">
          <div>1️⃣ <strong>새 전략 생성</strong>: AI 전략을 데이터베이스에 저장 (비활성 상태)</div>
          <div>2️⃣ <strong>전략 활성화</strong>: AI 엔진이 해당 전략을 모니터링하도록 설정</div>
          <div>3️⃣ <strong>AI 트레이딩 시작</strong>: 활성화된 모든 전략이 실제로 실행됨</div>
          <div className="text-xs text-blue-600 mt-2">
            💡 활성화된 전략만 AI 엔진이 실행하며, 실시간 활동 로그에서 작동 상태를 확인할 수 있습니다.
          </div>
        </div>
      </div>

      {/* 상태 표시 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-lg shadow">
          <div className="text-sm text-gray-600">AI 상태</div>
          <div className={`text-lg font-semibold ${aiStatus.is_running ? 'text-green-600' : 'text-red-600'}`}>
            {aiStatus.is_running ? '실행 중' : '중지됨'}
          </div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <div className="text-sm text-gray-600">활성 전략</div>
          <div className="text-lg font-semibold text-blue-600">
            {aiStatus.active_strategies || 0} / {aiStatus.total_strategies || 0}
          </div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <div className="text-sm text-gray-600">총 손익</div>
          <div className={`text-lg font-semibold ${dashboardData.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            ${dashboardData.total_pnl?.toFixed(2) || '0.00'}
          </div>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <div className="text-sm text-gray-600">총 거래 수</div>
          <div className="text-lg font-semibold text-blue-600">
            {dashboardData.total_trades || 0}
          </div>
        </div>
      </div>

      {/* 전략 목록 */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">AI 트레이딩 전략</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  전략명
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  위험도
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  심볼
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  상태
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  손익
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  승률
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  거래 수
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  액션
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {strategies.map((strategy) => (
                <tr key={strategy.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {strategy.name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getRiskLevelColor(strategy.risk_level)}`}>
                      {getRiskLevelText(strategy.risk_level)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {strategy.symbol}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      strategy.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {strategy.is_active ? '활성' : '비활성'}
                    </span>
                  </td>
                  <td className={`px-6 py-4 whitespace-nowrap text-sm font-medium ${
                    strategy.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    ${strategy.total_pnl?.toFixed(2) || '0.00'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {(strategy.win_rate * 100).toFixed(1)}%
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {strategy.total_trades || 0}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                    <button
                      onClick={() => toggleStrategy(strategy.id)}
                      className={`px-3 py-1 rounded text-xs ${
                        strategy.is_active 
                          ? 'bg-red-100 text-red-700 hover:bg-red-200' 
                          : 'bg-green-100 text-green-700 hover:bg-green-200'
                      }`}
                    >
                      {strategy.is_active ? '비활성화' : '활성화'}
                    </button>
                    <button
                      onClick={() => deleteStrategy(strategy.id)}
                      className="px-3 py-1 bg-red-100 text-red-700 rounded text-xs hover:bg-red-200"
                    >
                      삭제
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 새 전략 생성 모달 */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">새 AI 트레이딩 전략 생성</h3>
              <form onSubmit={createStrategy} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">전략명</label>
                  <input
                    type="text"
                    value={newStrategy.name}
                    onChange={(e) => setNewStrategy({...newStrategy, name: e.target.value})}
                    className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                    required
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700">위험도</label>
                  <select
                    value={newStrategy.risk_level}
                    onChange={(e) => setNewStrategy({...newStrategy, risk_level: e.target.value})}
                    className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                  >
                    <option value="LOW">저위험</option>
                    <option value="MEDIUM">중위험</option>
                    <option value="HIGH">고위험</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">심볼</label>
                  <input
                    type="text"
                    value={newStrategy.symbol}
                    onChange={(e) => setNewStrategy({...newStrategy, symbol: e.target.value})}
                    className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">거래소</label>
                  <select
                    value={newStrategy.exchange_type}
                    onChange={(e) => setNewStrategy({...newStrategy, exchange_type: e.target.value})}
                    className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                  >
                    <option value="binance">Binance</option>
                    <option value="bybit">Bybit</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">시간프레임</label>
                  <select
                    value={newStrategy.timeframe}
                    onChange={(e) => setNewStrategy({...newStrategy, timeframe: e.target.value})}
                    className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                  >
                    <option value="1m">1분</option>
                    <option value="5m">5분</option>
                    <option value="15m">15분</option>
                    <option value="1h">1시간</option>
                    <option value="4h">4시간</option>
                    <option value="1d">1일</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">최소 레버리지</label>
                    <input
                      type="number"
                      step="0.1"
                      value={newStrategy.leverage_min}
                      onChange={(e) => setNewStrategy({...newStrategy, leverage_min: parseFloat(e.target.value)})}
                      className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">최대 레버리지</label>
                    <input
                      type="number"
                      step="0.1"
                      value={newStrategy.leverage_max}
                      onChange={(e) => setNewStrategy({...newStrategy, leverage_max: parseFloat(e.target.value)})}
                      className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">포지션 크기 (USD)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={newStrategy.position_size_usd}
                    onChange={(e) => setNewStrategy({...newStrategy, position_size_usd: parseFloat(e.target.value)})}
                    className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">신뢰도 임계값</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={newStrategy.confidence_threshold}
                    onChange={(e) => setNewStrategy({...newStrategy, confidence_threshold: parseFloat(e.target.value)})}
                    className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">일일 최대 거래 수</label>
                    <input
                      type="number"
                      value={newStrategy.max_daily_trades}
                      onChange={(e) => setNewStrategy({...newStrategy, max_daily_trades: parseInt(e.target.value)})}
                      className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">손절 비율 (%)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={newStrategy.stop_loss_pct}
                      onChange={(e) => setNewStrategy({...newStrategy, stop_loss_pct: parseFloat(e.target.value)})}
                      className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">목표 수익 비율 (%)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={newStrategy.take_profit_pct}
                    onChange={(e) => setNewStrategy({...newStrategy, take_profit_pct: parseFloat(e.target.value)})}
                    className="mt-1 block w-full border border-gray-300 rounded-md px-3 py-2"
                    required
                  />
                </div>

                <div className="flex justify-end space-x-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowCreateForm(false)}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
                  >
                    취소
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                  >
                    생성
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* 에러 메시지 */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* 실시간 활동 로그 */}
      <div className="mt-8 bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">📊 실시간 활동 로그</h3>
        <div className="bg-gray-50 rounded-lg p-4 h-64 overflow-y-auto">
          {recentActivity.length === 0 ? (
            <p className="text-gray-500 text-center">활동 로그가 없습니다</p>
          ) : (
            <div className="space-y-2">
              {recentActivity.map((activity, index) => (
                <div key={index} className="flex items-start space-x-3 p-2 bg-white rounded border-l-4 border-blue-500">
                  <div className="text-xs text-gray-500 font-mono">{activity.time}</div>
                  <div className="flex-1">
                    <div className="text-sm text-gray-900">{activity.message}</div>
                    {activity.data && (
                      <div className="text-xs text-gray-600 mt-1">
                        활성 전략: {activity.data?.status?.active_strategies ?? 0}개 | 
                        총 거래: {activity.data?.dashboard?.total_trades ?? 0}건 | 
                        총 손익: {typeof activity.data?.dashboard?.total_pnl === 'number' ? `$${activity.data.dashboard.total_pnl.toFixed(2)}` : '$0.00'}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AITradingDashboard;
