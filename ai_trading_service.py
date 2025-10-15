import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from models import AITradingConfig, AITradingLog, AITradingPerformance
from ai_trading_engine import AITradingEngine
from real_trading_service import RealTradingService
from trading_config import TradingManager, TradingMode
from database import SessionLocal
from position_service import PositionService


class AITradingService:
    """AI 트레이딩 서비스"""
    
    # Class-level shared engine/task to ensure a single running engine per process
    _shared_engine: Optional[AITradingEngine] = None
    _shared_engine_task: Optional[asyncio.Task] = None

    def __init__(self, db: Session, real_trading_service: RealTradingService):
        self.db = db
        self.real_trading_service = real_trading_service
        # Reuse singleton engine/task across all instances
        if AITradingService._shared_engine is None:
            AITradingService._shared_engine = AITradingEngine(db, real_trading_service)
        self.engine = AITradingService._shared_engine
        self.engine_task = AITradingService._shared_engine_task
    
    async def start_ai_trading(self):
        """AI 트레이딩 시작"""
        # Refresh references to the shared objects
        self.engine = AITradingService._shared_engine
        if self.engine is None:
            # Create engine with a dedicated long-lived DB session
            engine_db = SessionLocal()
            self.engine = AITradingEngine(engine_db, self.real_trading_service)
            AITradingService._shared_engine = self.engine
        else:
            # If engine is not running, ensure its DB session is valid/fresh
            if not self.engine.running:
                try:
                    # Close previous dedicated session if present
                    if hasattr(self.engine.db, 'close'):
                        self.engine.db.close()
                except Exception:
                    pass
                engine_db = SessionLocal()
                self.engine.db = engine_db
                # refresh dependent services with new session
                self.engine.position_service = PositionService(engine_db)
        self.engine_task = AITradingService._shared_engine_task

        if self.engine_task and not self.engine_task.done():
            return {"status": "error", "message": "AI trading is already running"}
        
        self.engine_task = asyncio.create_task(self.engine.start_engine())
        AITradingService._shared_engine_task = self.engine_task
        return {"status": "ok", "message": "AI trading started"}
    
    async def stop_ai_trading(self):
        """AI 트레이딩 중지"""
        # Use shared task/engine to stop
        task = AITradingService._shared_engine_task
        engine = AITradingService._shared_engine
        if task:
            if engine:
                await engine.stop_engine()
            try:
                task.cancel()
            except Exception:
                pass
            AITradingService._shared_engine_task = None
        # Close dedicated engine DB session safely
        if engine and getattr(engine, 'db', None) is not None:
            try:
                if hasattr(engine.db, 'close'):
                    engine.db.close()
            except Exception:
                pass
        # keep engine object to allow reusing websocket clients list; it will not run until restarted
        self.engine_task = None
        return {"status": "ok", "message": "AI trading stopped"}
    
    def create_strategy(self, name: str, risk_level: str, symbol: str, exchange_type: str, 
                       timeframe: str, leverage_min: float, leverage_max: float,
                       position_size_usd: float, confidence_threshold: float = 0.7,
                       max_daily_trades: int = 100, stop_loss_pct: float = 2.0,
                       take_profit_pct: float = 3.0) -> Dict:
        """새로운 AI 트레이딩 전략 생성"""
        
        # 기본 설정값 설정
        if risk_level.upper() == "HIGH":
            timeframe = timeframe or "1m"
            leverage_min = leverage_min or 10.0
            leverage_max = leverage_max or 50.0
            confidence_threshold = confidence_threshold or 0.7
        elif risk_level.upper() == "MEDIUM":
            timeframe = timeframe or "5m"
            leverage_min = leverage_min or 5.0
            leverage_max = leverage_max or 10.0
            confidence_threshold = confidence_threshold or 0.6
        elif risk_level.upper() == "LOW":
            timeframe = timeframe or "1h"
            leverage_min = leverage_min or 1.0
            leverage_max = leverage_max or 5.0
            confidence_threshold = confidence_threshold or 0.5
        
        config = AITradingConfig(
            name=name,
            risk_level=risk_level.upper(),
            symbol=symbol.upper(),
            exchange_type=exchange_type.lower(),
            timeframe=timeframe,
            leverage_min=leverage_min,
            leverage_max=leverage_max,
            position_size_usd=position_size_usd,
            confidence_threshold=confidence_threshold,
            max_daily_trades=max_daily_trades,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct
        )
        
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        
        return {"status": "ok", "config_id": config.id, "message": f"Strategy '{name}' created"}
    
    def get_strategies(self) -> List[Dict]:
        """모든 전략 조회"""
        configs = self.db.query(AITradingConfig).all()
        
        strategies = []
        for config in configs:
            strategies.append({
                "id": config.id,
                "name": config.name,
                "risk_level": config.risk_level,
                "is_active": config.is_active,
                "symbol": config.symbol,
                "exchange_type": config.exchange_type,
                "timeframe": config.timeframe,
                "leverage_min": config.leverage_min,
                "leverage_max": config.leverage_max,
                "position_size_usd": config.position_size_usd,
                "confidence_threshold": config.confidence_threshold,
                "max_daily_trades": config.max_daily_trades,
                "stop_loss_pct": config.stop_loss_pct,
                "take_profit_pct": config.take_profit_pct,
                "total_trades": config.total_trades,
                "winning_trades": config.winning_trades,
                "total_pnl": config.total_pnl,
                "win_rate": config.winning_trades / config.total_trades if config.total_trades > 0 else 0,
                "sharpe_ratio": config.sharpe_ratio,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat()
            })
        
        return strategies
    
    def toggle_strategy(self, config_id: int) -> Dict:
        """전략 활성화/비활성화 토글"""
        config = self.db.query(AITradingConfig).filter(AITradingConfig.id == config_id).first()
        if not config:
            return {"status": "error", "message": "Strategy not found"}
        
        config.is_active = not config.is_active
        self.db.commit()
        
        status = "activated" if config.is_active else "deactivated"
        return {"status": "ok", "message": f"Strategy '{config.name}' {status}"}
    
    def update_strategy(self, config_id: int, **kwargs) -> Dict:
        """전략 설정 업데이트"""
        config = self.db.query(AITradingConfig).filter(AITradingConfig.id == config_id).first()
        if not config:
            return {"status": "error", "message": "Strategy not found"}
        
        # 업데이트 가능한 필드들
        updatable_fields = [
            'name', 'symbol', 'exchange_type', 'timeframe', 'leverage_min', 'leverage_max',
            'position_size_usd', 'confidence_threshold', 'max_daily_trades',
            'stop_loss_pct', 'take_profit_pct'
        ]
        
        for field, value in kwargs.items():
            if field in updatable_fields and hasattr(config, field):
                setattr(config, field, value)
        
        self.db.commit()
        
        return {"status": "ok", "message": f"Strategy '{config.name}' updated"}
    
    def delete_strategy(self, config_id: int) -> Dict:
        """전략 삭제"""
        config = self.db.query(AITradingConfig).filter(AITradingConfig.id == config_id).first()
        if not config:
            return {"status": "error", "message": "Strategy not found"}
        
        # 관련 로그와 성과 데이터도 삭제
        self.db.query(AITradingLog).filter(AITradingLog.config_id == config_id).delete()
        self.db.query(AITradingPerformance).filter(AITradingPerformance.config_id == config_id).delete()
        
        self.db.delete(config)
        self.db.commit()
        
        return {"status": "ok", "message": f"Strategy '{config.name}' deleted"}
    
    def get_strategy_logs(self, config_id: int, limit: int = 100) -> List[Dict]:
        """전략 로그 조회"""
        logs = self.db.query(AITradingLog).filter(
            AITradingLog.config_id == config_id
        ).order_by(desc(AITradingLog.created_at)).limit(limit).all()
        
        result = []
        for log in logs:
            result.append({
                "id": log.id,
                "action": log.action,
                "symbol": log.symbol,
                "side": log.side,
                "quantity": log.quantity,
                "price": log.price,
                "pnl": log.pnl,
                "confidence_score": log.confidence_score,
                "technical_indicators": log.technical_indicators,
                "market_sentiment": log.market_sentiment,
                "risk_assessment": log.risk_assessment,
                "reason": log.reason,
                "notes": log.notes,
                "created_at": log.created_at.isoformat()
            })
        
        return result
    
    def get_performance_analysis(self, config_id: int, period_type: str = "DAILY") -> Dict:
        """성과 분석 조회"""
        # 최근 30일 데이터
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        performances = self.db.query(AITradingPerformance).filter(
            and_(
                AITradingPerformance.config_id == config_id,
                AITradingPerformance.period_type == period_type,
                AITradingPerformance.period_date >= start_date,
                AITradingPerformance.period_date <= end_date
            )
        ).order_by(AITradingPerformance.period_date).all()
        
        if not performances:
            return {"status": "error", "message": "No performance data found"}
        
        # 일일 성과 데이터
        daily_data = []
        total_pnl = 0
        total_trades = 0
        winning_trades = 0
        
        for perf in performances:
            daily_data.append({
                "date": perf.period_date.isoformat(),
                "total_trades": perf.total_trades,
                "winning_trades": perf.winning_trades,
                "losing_trades": perf.losing_trades,
                "win_rate": perf.win_rate,
                "total_pnl": perf.total_pnl,
                "avg_pnl_per_trade": perf.avg_pnl_per_trade,
                "max_drawdown": perf.max_drawdown,
                "sharpe_ratio": perf.sharpe_ratio,
                "profit_factor": perf.profit_factor,
                "avg_confidence": perf.avg_confidence,
                "prediction_accuracy": perf.prediction_accuracy,
                "risk_adjusted_return": perf.risk_adjusted_return
            })
            
            total_pnl += perf.total_pnl
            total_trades += perf.total_trades
            winning_trades += perf.winning_trades
        
        # 전체 통계
        overall_stats = {
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "win_rate": winning_trades / total_trades if total_trades > 0 else 0,
            "avg_pnl_per_trade": total_pnl / total_trades if total_trades > 0 else 0,
            "avg_daily_pnl": total_pnl / len(performances) if performances else 0
        }
        
        return {
            "status": "ok",
            "period_type": period_type,
            "overall_stats": overall_stats,
            "daily_data": daily_data
        }
    
    def get_ai_status(self) -> Dict:
        """AI 트레이딩 상태 조회"""
        # 엔진이 실행 중인지 확인 (engine_task와 engine.running 모두 확인)
        is_running = False
        strategy_status: Dict[int, Dict] = {}
        
        if self.engine:
            is_running = (self.engine_task and not self.engine_task.done()) or self.engine.running
            if is_running:
                # Build strategy status using the current request-scoped DB to avoid closed sessions
                pos_service = PositionService(self.db)
                for config_id, si in self.engine.active_strategies.items():
                    config = si['config']
                    pos = pos_service.get_position(config.symbol)
                    strategy_status[config_id] = {
                        'name': config.name,
                        'risk_level': config.risk_level,
                        'is_active': config.is_active,
                        'symbol': config.symbol,
                        'current_position': {
                            'side': pos.side if pos else None,
                            'qty': pos.qty if pos else 0,
                            'entry_price': pos.entry_price if pos else 0,
                            'unrealized_pnl': pos.unrealized_pnl if pos else 0,
                        } if pos else None,
                        'daily_trades': si.get('daily_trades', 0),
                        'last_analysis': si.get('last_analysis'),
                        'total_trades': config.total_trades,
                        'winning_trades': config.winning_trades,
                        'total_pnl': config.total_pnl,
                        'win_rate': (config.winning_trades / config.total_trades) if config.total_trades > 0 else 0,
                    }

        return {
            "is_running": is_running,
            "active_strategies": len([s for s in strategy_status.values() if s.get('is_active', False)]),
            "total_strategies": len(strategy_status),
            "strategies": strategy_status
        }
    
    def reset_strategy_performance(self, config_id: int) -> Dict:
        """전략 성과 리셋"""
        config = self.db.query(AITradingConfig).filter(AITradingConfig.id == config_id).first()
        if not config:
            return {"status": "error", "message": "Strategy not found"}
        
        # 성과 통계 리셋
        config.total_trades = 0
        config.winning_trades = 0
        config.total_pnl = 0.0
        config.max_drawdown = 0.0
        config.sharpe_ratio = 0.0
        
        # 관련 로그와 성과 데이터 삭제
        self.db.query(AITradingLog).filter(AITradingLog.config_id == config_id).delete()
        self.db.query(AITradingPerformance).filter(AITradingPerformance.config_id == config_id).delete()
        
        self.db.commit()
        
        return {"status": "ok", "message": f"Performance data for '{config.name}' reset"}
    
    def get_ai_dashboard_data(self) -> Dict:
        """AI 대시보드 데이터 조회"""
        # 모든 전략의 성과 요약
        strategies = self.db.query(AITradingConfig).all()
        
        total_strategies = len(strategies)
        active_strategies = len([s for s in strategies if s.is_active])
        
        total_pnl = sum(s.total_pnl for s in strategies)
        total_trades = sum(s.total_trades for s in strategies)
        total_winning_trades = sum(s.winning_trades for s in strategies)
        
        # 최근 7일간의 일일 성과
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        recent_performance = self.db.query(AITradingPerformance).filter(
            and_(
                AITradingPerformance.period_type == "DAILY",
                AITradingPerformance.period_date >= start_date,
                AITradingPerformance.period_date <= end_date
            )
        ).all()
        
        daily_pnl = {}
        for perf in recent_performance:
            daily_pnl[perf.period_date.isoformat()] = perf.total_pnl
        
        return {
            "total_strategies": total_strategies,
            "active_strategies": active_strategies,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "total_winning_trades": total_winning_trades,
            "overall_win_rate": total_winning_trades / total_trades if total_trades > 0 else 0,
            "daily_pnl": daily_pnl,
            "strategies": [
                {
                    "id": s.id,
                    "name": s.name,
                    "risk_level": s.risk_level,
                    "is_active": s.is_active,
                    "total_pnl": s.total_pnl,
                    "total_trades": s.total_trades,
                    "win_rate": s.winning_trades / s.total_trades if s.total_trades > 0 else 0
                }
                for s in strategies
            ]
        }

