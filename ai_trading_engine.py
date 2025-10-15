import asyncio
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
import time

from models import AITradingConfig, AITradingLog, AITradingPerformance, Trade
from ai_trading_strategies import create_strategy
from position_service import PositionService
from trade_service import save_trade
from multi_exchange_data_feed import multi_exchange_feed
from real_trading_service import RealTradingService
from trading_config import TradingManager, TradingMode


class AITradingEngine:
    """AI 트레이딩 엔진"""
    
    def __init__(self, db: Session, real_trading_service: RealTradingService):
        self.db = db
        self.real_trading_service = real_trading_service
        self.position_service = PositionService(db)
        self.active_strategies: Dict[int, Dict] = {}  # config_id -> strategy info
        self.running = False
        self.websocket_clients = []  # WebSocket 클라이언트 목록
        
    async def start_engine(self):
        """AI 트레이딩 엔진 시작"""
        self.running = True
        print("AI Trading Engine started")
        
        # 활성화된 전략들 로드
        await self._load_active_strategies()
        print(f"Loaded {len(self.active_strategies)} active strategies")
        
        # 메인 루프 시작
        loop_count = 0
        while self.running:
            try:
                loop_count += 1
                if loop_count % 10 == 0:  # 10초마다 상태 출력
                    print(f"AI Engine running... Active strategies: {len(self.active_strategies)}")
                
                await self._process_strategies()
                await self.check_exit_conditions()  # 청산 조건 체크
                await asyncio.sleep(1)  # 1초마다 체크
            except Exception as e:
                print(f"Error in AI trading engine: {e}")
                await asyncio.sleep(5)
    
    async def stop_engine(self):
        """AI 트레이딩 엔진 중지"""
        self.running = False
        print("AI Trading Engine stopped")
    
    def add_websocket_client(self, websocket):
        """WebSocket 클라이언트 추가"""
        self.websocket_clients.append(websocket)
    
    def remove_websocket_client(self, websocket):
        """WebSocket 클라이언트 제거"""
        if websocket in self.websocket_clients:
            self.websocket_clients.remove(websocket)
    
    async def broadcast_activity(self, activity_type: str, message: str, data: dict = None):
        """실시간 활동을 모든 WebSocket 클라이언트에게 브로드캐스트"""
        if not self.websocket_clients:
            return
            
        activity = {
            "type": "ai_activity",
            "data": {
                "activity_type": activity_type,
                "message": message,
                "data": data,
                "timestamp": int(time.time() * 1000)
            }
        }
        
        # 연결이 끊어진 클라이언트 제거
        disconnected_clients = []
        for client in self.websocket_clients:
            try:
                await client.send_json(activity)
            except Exception as e:
                print(f"Error sending activity to WebSocket client: {e}")
                disconnected_clients.append(client)
        
        # 연결이 끊어진 클라이언트 제거
        for client in disconnected_clients:
            self.remove_websocket_client(client)
    
    async def _load_active_strategies(self):
        """활성화된 전략들 로드"""
        print("Loading active strategies...")
        configs = self.db.query(AITradingConfig).filter(AITradingConfig.is_active == True).all()
        print(f"Found {len(configs)} active strategies in database")
        
        for config in configs:
            try:
                print(f"Loading strategy {config.id}: {config.name} ({config.risk_level})")
                strategy = create_strategy(config.risk_level, {
                    'confidence_threshold': config.confidence_threshold,
                    'max_daily_trades': config.max_daily_trades,
                    'stop_loss_pct': config.stop_loss_pct,
                    'take_profit_pct': config.take_profit_pct,
                    'leverage_min': config.leverage_min,
                    'leverage_max': config.leverage_max,
                    'position_size_usd': config.position_size_usd
                })
                
                self.active_strategies[config.id] = {
                    'config': config,
                    'strategy': strategy,
                    'last_analysis': None,
                    'current_position': None,
                    'daily_trades': 0,
                    'last_trade_date': None
                }
                
                print(f"Successfully loaded strategy: {config.name} ({config.risk_level})")
            except Exception as e:
                print(f"Error loading strategy {config.id}: {e}")
    
    async def _process_strategies(self):
        """전략들 처리"""
        if not self.active_strategies:
            return  # 활성화된 전략이 없으면 아무것도 하지 않음
            
        for config_id, strategy_info in self.active_strategies.items():
            try:
                await self._process_strategy(strategy_info)
            except Exception as e:
                print(f"Error processing strategy {config_id}: {e}")
    
    async def _process_strategy(self, strategy_info: Dict):
        """개별 전략 처리"""
        config = strategy_info['config']
        strategy = strategy_info['strategy']
        
        # 일일 거래 수 제한 체크
        today = date.today()
        if strategy_info['last_trade_date'] != today:
            strategy_info['daily_trades'] = 0
            strategy_info['last_trade_date'] = today
        
        if strategy_info['daily_trades'] >= config.max_daily_trades:
            print(f"Strategy {config.name}: Daily trade limit reached ({strategy_info['daily_trades']}/{config.max_daily_trades})")
            return
        
        # 캔들 데이터 가져오기
        try:
            print(f"Getting candles for {config.symbol} ({config.timeframe})")
            candles = await self._get_candles(config.symbol, config.timeframe, 100)
            if not candles or len(candles) < 50:
                print(f"Strategy {config.name}: Insufficient candle data ({len(candles) if candles else 0} candles)")
                return
            print(f"Strategy {config.name}: Got {len(candles)} candles")
        except Exception as e:
            print(f"Error getting candles for {config.symbol}: {e}")
            return
        
        # 시장 분석
        print(f"Strategy {config.name}: Analyzing market...")
        analysis = strategy.analyze_market(candles)
        strategy_info['last_analysis'] = analysis
        print(f"Strategy {config.name}: Analysis result - Signal: {analysis.get('signal', 'NONE')}, Confidence: {analysis.get('confidence', 0):.2f}")
        
        # 실시간 활동 브로드캐스트
        await self.broadcast_activity(
            "analysis",
            f"전략 '{config.name}' 분석 완료: {analysis.get('signal', 'NONE')} 신호 (신뢰도: {analysis.get('confidence', 0):.2f})",
            {
                "strategy_name": config.name,
                "signal": analysis.get('signal', 'NONE'),
                "confidence": analysis.get('confidence', 0),
                "symbol": config.symbol
            }
        )
        
        # 로그 기록
        await self._log_analysis(config.id, config.symbol, analysis)
        
        # 거래 신호 처리
        if analysis['signal'] in ['BUY', 'SELL'] and analysis['confidence'] >= config.confidence_threshold:
            await self._process_trading_signal(strategy_info, analysis, candles[-1])
    
    async def _get_candles(self, symbol: str, timeframe: str, limit: int) -> List[Dict]:
        """캔들 데이터 가져오기"""
        try:
            # Binance 거래소가 없으면 추가
            if "binance" not in multi_exchange_feed.get_available_exchanges():
                multi_exchange_feed.add_exchange("binance", testnet=True)
            
            # Binance에서 데이터 가져오기
            klines = await multi_exchange_feed.get_klines("binance", symbol, timeframe, limit)
            
            # Kline 객체를 딕셔너리로 변환
            candles = []
            for kline in klines:
                candles.append({
                    'open_time': kline.open_time,
                    'close_time': kline.close_time,
                    'open': kline.open,
                    'high': kline.high,
                    'low': kline.low,
                    'close': kline.close,
                    'volume': kline.volume,
                    'quote_volume': kline.quote_volume,
                    'trades_count': kline.trades_count
                })
            
            return candles
        except Exception as e:
            print(f"Error getting candles from Binance: {e}")
            return []
    
    async def _process_trading_signal(self, strategy_info: Dict, analysis: Dict, latest_candle: Dict):
        """거래 신호 처리"""
        config = strategy_info['config']
        current_price = float(latest_candle['close'])
        
        # 현재 포지션 확인
        position = self.position_service.get_position(config.symbol)
        
        if analysis['signal'] == 'BUY':
            if not position or position.side != 'BUY':
                await self._open_position(strategy_info, 'BUY', current_price, analysis)
        elif analysis['signal'] == 'SELL':
            if not position or position.side != 'SELL':
                await self._open_position(strategy_info, 'SELL', current_price, analysis)
    
    async def _open_position(self, strategy_info: Dict, side: str, price: float, analysis: Dict):
        """포지션 오픈"""
        config = strategy_info['config']
        
        # 포지션 크기 계산
        position_size_usd = config.position_size_usd
        quantity = position_size_usd / price
        
        # 레버리지 계산 (랜덤하게 설정)
        import random
        leverage = random.uniform(config.leverage_min, config.leverage_max)
        leveraged_quantity = quantity * leverage
        
        try:
            # 실제 거래 실행 (시뮬레이션 모드에서는 가상 거래)
            if self.real_trading_service.trading_manager.config.mode == TradingMode.SIMULATION:
                # 시뮬레이션 거래
                pnl = 0.0  # 포지션 오픈 시에는 PnL 0
                
                # 포지션 업데이트
                self.position_service.create_or_update_position(
                    symbol=config.symbol,
                    side=side,
                    qty=leveraged_quantity,
                    entry_price=price,
                    latest_price=price
                )
                
                # 거래 기록 저장
                trade = save_trade(
                    self.db,
                    config.symbol,
                    side,
                    price,
                    leveraged_quantity,
                    pnl=pnl
                )
                
                # AI 거래 로그 기록
                await self._log_trade(
                    config.id,
                    'ENTRY',
                    config.symbol,
                    side,
                    leveraged_quantity,
                    price,
                    pnl,
                    analysis
                )
                
                print(f"AI {config.name}: {side} {leveraged_quantity:.6f} {config.symbol} @ {price:.2f} (Leverage: {leverage:.1f}x)")
                
                # 실시간 거래 활동 브로드캐스트
                await self.broadcast_activity(
                    "trade",
                    f"AI {config.name}: {side} {leveraged_quantity:.6f} {config.symbol} @ {price:.2f} (Leverage: {leverage:.1f}x)",
                    {
                        "strategy_name": config.name,
                        "action": side,
                        "symbol": config.symbol,
                        "quantity": leveraged_quantity,
                        "price": price,
                        "leverage": leverage,
                        "pnl": pnl
                    }
                )
                
            else:
                # 실제 거래
                order_result = await self.real_trading_service.place_real_order(
                    self.db,
                    config.exchange_type,
                    config.symbol,
                    side,
                    leveraged_quantity,
                    price
                )
                
                if order_result.get('status') == 'filled':
                    # 포지션 업데이트
                    self.position_service.create_or_update_position(
                        symbol=config.symbol,
                        side=side,
                        qty=leveraged_quantity,
                        entry_price=price,
                        latest_price=price
                    )
                    
                    # AI 거래 로그 기록
                    await self._log_trade(
                        config.id,
                        'ENTRY',
                        config.symbol,
                        side,
                        leveraged_quantity,
                        price,
                        0.0,
                        analysis
                    )
                    
                    print(f"AI {config.name}: Real {side} {leveraged_quantity:.6f} {config.symbol} @ {price:.2f}")
            
            # 일일 거래 수 증가
            strategy_info['daily_trades'] += 1
            
        except Exception as e:
            print(f"Error opening position for {config.name}: {e}")
    
    async def _log_analysis(self, config_id: int, symbol: str, analysis: Dict):
        """분석 로그 기록"""
        log = AITradingLog(
            config_id=config_id,
            action='ANALYSIS',
            symbol=symbol,
            confidence_score=analysis.get('confidence'),
            technical_indicators=json.dumps(analysis.get('technical_indicators', {})),
            market_sentiment=analysis.get('signal'),
            risk_assessment=analysis.get('reason'),
            reason=analysis.get('reason')
        )
        self.db.add(log)
        self.db.commit()
    
    async def _log_trade(self, config_id: int, action: str, symbol: str, side: str, 
                        quantity: float, price: float, pnl: float, analysis: Dict):
        """거래 로그 기록"""
        log = AITradingLog(
            config_id=config_id,
            action=action,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            pnl=pnl,
            confidence_score=analysis.get('confidence'),
            technical_indicators=json.dumps(analysis.get('technical_indicators', {})),
            market_sentiment=analysis.get('signal'),
            risk_assessment=analysis.get('reason'),
            reason=analysis.get('reason')
        )
        self.db.add(log)
        self.db.commit()
    
    async def check_exit_conditions(self):
        """청산 조건 체크"""
        for config_id, strategy_info in self.active_strategies.items():
            config = strategy_info['config']
            position = self.position_service.get_position(config.symbol)
            
            if not position or position.qty == 0:
                continue
            
            current_price = position.latest_price
            entry_price = position.entry_price
            
            # 손절/목표가 체크
            if position.side == 'BUY':
                pnl_pct = (current_price - entry_price) / entry_price * 100
            else:  # SELL
                pnl_pct = (entry_price - current_price) / entry_price * 100
            
            # 손절가 체크
            if pnl_pct <= -config.stop_loss_pct:
                await self._close_position(strategy_info, position, current_price, "STOP_LOSS")
            # 목표가 체크
            elif pnl_pct >= config.take_profit_pct:
                await self._close_position(strategy_info, position, current_price, "TAKE_PROFIT")
    
    async def _close_position(self, strategy_info: Dict, position, current_price: float, reason: str):
        """포지션 청산"""
        config = strategy_info['config']
        
        # PnL 계산
        if position.side == 'BUY':
            pnl = (current_price - position.entry_price) * position.qty
        else:  # SELL
            pnl = (position.entry_price - current_price) * position.qty
        
        # 포지션 청산
        self.position_service.close_position(config.symbol, position.qty)
        
        # 거래 기록 저장
        close_side = 'SELL' if position.side == 'BUY' else 'BUY'
        trade = save_trade(
            self.db,
            config.symbol,
            close_side,
            current_price,
            position.qty,
            pnl=pnl
        )
        
        # AI 거래 로그 기록
        await self._log_trade(
            config.id,
            'EXIT',
            config.symbol,
            close_side,
            position.qty,
            current_price,
            pnl,
            {'reason': reason}
        )
        
        # 성과 업데이트
        await self._update_performance(config.id, pnl)
        
        print(f"AI {config.name}: Closed {position.side} position @ {current_price:.2f}, PnL: {pnl:.2f} ({reason})")
    
    async def _update_performance(self, config_id: int, pnl: float):
        """성과 업데이트"""
        config = self.db.query(AITradingConfig).filter(AITradingConfig.id == config_id).first()
        if not config:
            return
        
        # 기본 통계 업데이트
        config.total_trades += 1
        config.total_pnl += pnl
        
        if pnl > 0:
            config.winning_trades += 1
        
        # 승률 계산
        if config.total_trades > 0:
            win_rate = config.winning_trades / config.total_trades
            config.sharpe_ratio = self._calculate_sharpe_ratio(config_id)
        
        self.db.commit()
        
        # 일일 성과 업데이트
        await self._update_daily_performance(config_id, pnl)
    
    def _calculate_sharpe_ratio(self, config_id: int) -> float:
        """샤프 비율 계산"""
        # 최근 30일간의 거래 데이터로 샤프 비율 계산
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        trades = self.db.query(AITradingLog).filter(
            and_(
                AITradingLog.config_id == config_id,
                AITradingLog.action == 'EXIT',
                AITradingLog.created_at >= thirty_days_ago
            )
        ).all()
        
        if len(trades) < 2:
            return 0.0
        
        pnls = [trade.pnl for trade in trades]
        avg_return = sum(pnls) / len(pnls)
        std_return = (sum([(p - avg_return) ** 2 for p in pnls]) / len(pnls)) ** 0.5
        
        if std_return == 0:
            return 0.0
        
        # 무위험 수익률을 0으로 가정
        return avg_return / std_return
    
    async def _update_daily_performance(self, config_id: int, pnl: float):
        """일일 성과 업데이트"""
        today = date.today()
        
        # 오늘의 성과 기록 찾기
        performance = self.db.query(AITradingPerformance).filter(
            and_(
                AITradingPerformance.config_id == config_id,
                AITradingPerformance.period_type == 'DAILY',
                AITradingPerformance.period_date == today
            )
        ).first()
        
        if not performance:
            performance = AITradingPerformance(
                config_id=config_id,
                period_type='DAILY',
                period_date=today
            )
            self.db.add(performance)
        
        # 성과 업데이트
        performance.total_trades += 1
        performance.total_pnl += pnl
        
        if pnl > 0:
            performance.winning_trades += 1
        else:
            performance.losing_trades += 1
        
        if performance.total_trades > 0:
            performance.win_rate = performance.winning_trades / performance.total_trades
            performance.avg_pnl_per_trade = performance.total_pnl / performance.total_trades
        
        self.db.commit()
    
    def get_strategy_status(self) -> Dict:
        """전략 상태 조회"""
        status = {}
        for config_id, strategy_info in self.active_strategies.items():
            config = strategy_info['config']
            position = self.position_service.get_position(config.symbol)
            
            status[config_id] = {
                'name': config.name,
                'risk_level': config.risk_level,
                'is_active': config.is_active,
                'symbol': config.symbol,
                'current_position': {
                    'side': position.side if position else None,
                    'qty': position.qty if position else 0,
                    'entry_price': position.entry_price if position else 0,
                    'unrealized_pnl': position.unrealized_pnl if position else 0
                } if position else None,
                'daily_trades': strategy_info['daily_trades'],
                'last_analysis': strategy_info['last_analysis'],
                'total_trades': config.total_trades,
                'winning_trades': config.winning_trades,
                'total_pnl': config.total_pnl,
                'win_rate': config.winning_trades / config.total_trades if config.total_trades > 0 else 0
            }
        
        return status

