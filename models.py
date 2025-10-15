from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)     # BTCUSDT
    side = Column(String, nullable=False)       # BUY / SELL
    price = Column(Float, nullable=False)       # 체결 가격
    qty = Column(Float, nullable=False)         # 수량
    timestamp = Column(DateTime, default=datetime.utcnow)
    pnl = Column(Float, default=0.0)            # 손익

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, unique=True)  # BTCUSDT
    side = Column(String, nullable=True)        # BUY / SELL / None
    qty = Column(Float, default=0.0)            # 수량
    entry_price = Column(Float, default=0.0)    # 평단가
    unrealized_pnl = Column(Float, default=0.0) # 미실현손익
    latest_price = Column(Float, default=0.0)   # 최신가격
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)   # 활성 상태


class AITradingConfig(Base):
    __tablename__ = "ai_trading_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)       # "고위험트레이더", "중위험트레이더", "저위험트레이더"
    risk_level = Column(String, nullable=False) # "HIGH", "MEDIUM", "LOW"
    is_active = Column(Boolean, default=False)  # 활성 상태
    symbol = Column(String, nullable=False)     # BTCUSDT
    exchange_type = Column(String, nullable=False) # binance, bybit
    
    # 전략 설정
    timeframe = Column(String, nullable=False)  # "1m", "5m", "1h"
    leverage_min = Column(Float, default=1.0)   # 최소 레버리지
    leverage_max = Column(Float, default=50.0)  # 최대 레버리지
    position_size_usd = Column(Float, default=100.0) # 포지션 크기 (USD)
    
    # AI 설정
    ai_model_version = Column(String, default="v1.0")
    confidence_threshold = Column(Float, default=0.7) # 신뢰도 임계값
    max_daily_trades = Column(Integer, default=100)  # 일일 최대 거래 수
    stop_loss_pct = Column(Float, default=2.0)       # 손절 비율 (%)
    take_profit_pct = Column(Float, default=3.0)     # 목표 수익 비율 (%)
    
    # 성과 추적
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AITradingLog(Base):
    __tablename__ = "ai_trading_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(Integer, ForeignKey("ai_trading_configs.id"), nullable=False)
    action = Column(String, nullable=False)     # "ENTRY", "EXIT", "ANALYSIS", "UPGRADE"
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=True)        # BUY, SELL
    quantity = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    pnl = Column(Float, default=0.0)
    
    # AI 분석 결과
    confidence_score = Column(Float, nullable=True)
    technical_indicators = Column(Text, nullable=True) # JSON string
    market_sentiment = Column(String, nullable=True)
    risk_assessment = Column(String, nullable=True)
    
    # 메타데이터
    reason = Column(Text, nullable=True)        # 거래 이유
    notes = Column(Text, nullable=True)         # 추가 노트
    created_at = Column(DateTime, default=datetime.utcnow)


class AITradingPerformance(Base):
    __tablename__ = "ai_trading_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(Integer, ForeignKey("ai_trading_configs.id"), nullable=False)
    period_type = Column(String, nullable=False) # "DAILY", "WEEKLY", "MONTHLY"
    period_date = Column(Date, nullable=False)   # 2025-10-11
    
    # 성과 지표
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)        # 승률
    total_pnl = Column(Float, default=0.0)       # 총 손익
    avg_pnl_per_trade = Column(Float, default=0.0) # 거래당 평균 손익
    max_drawdown = Column(Float, default=0.0)    # 최대 손실
    sharpe_ratio = Column(Float, default=0.0)    # 샤프 비율
    profit_factor = Column(Float, default=0.0)   # 수익 팩터
    
    # AI 성능 지표
    avg_confidence = Column(Float, default=0.0)  # 평균 신뢰도
    prediction_accuracy = Column(Float, default=0.0) # 예측 정확도
    risk_adjusted_return = Column(Float, default=0.0) # 위험 조정 수익률
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
