from dataclasses import dataclass
from typing import Dict, Optional, List
from enum import Enum

class TradingMode(Enum):
    SIMULATION = "simulation"
    PAPER_TRADING = "paper_trading"
    LIVE_TRADING = "live_trading"

@dataclass
class ExchangeConfig:
    """거래소 설정"""
    exchange_type: str
    api_key: str
    api_secret: str
    testnet: bool = True
    enabled: bool = False
    max_position_size: float = 1000.0  # USD
    daily_loss_limit: float = 100.0    # USD
    max_leverage: int = 20

@dataclass
class TradingConfig:
    """거래 설정"""
    mode: TradingMode = TradingMode.SIMULATION
    exchanges: Dict[str, ExchangeConfig] = None
    default_exchange: str = "binance"
    risk_management: bool = True
    auto_close_on_loss: bool = True
    max_daily_trades: int = 50
    
    def __post_init__(self):
        if self.exchanges is None:
            self.exchanges = {}

class TradingManager:
    """실제 거래 관리자"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.active_orders: Dict[str, List[Dict]] = {}  # {exchange: [orders]}
        self.daily_pnl: Dict[str, float] = {}  # {exchange: pnl}
        self.daily_trades: Dict[str, int] = {}  # {exchange: count}
    
    def is_trading_enabled(self) -> bool:
        """실제 거래가 활성화되어 있는지 확인"""
        return self.config.mode in [TradingMode.PAPER_TRADING, TradingMode.LIVE_TRADING]
    
    def is_live_trading(self) -> bool:
        """라이브 거래인지 확인"""
        return self.config.mode == TradingMode.LIVE_TRADING
    
    def can_place_order(self, exchange_type: str) -> bool:
        """주문 가능 여부 확인"""
        if not self.is_trading_enabled():
            return False
        
        exchange_config = self.config.exchanges.get(exchange_type)
        if not exchange_config or not exchange_config.enabled:
            return False
        
        # 일일 거래 한도 확인
        daily_trades = self.daily_trades.get(exchange_type, 0)
        if daily_trades >= self.config.max_daily_trades:
            return False
        
        return True
    
    def check_risk_limits(self, exchange_type: str, order_value: float) -> bool:
        """리스크 한도 확인"""
        if not self.config.risk_management:
            return True
        
        exchange_config = self.config.exchanges.get(exchange_type)
        if not exchange_config:
            return False
        
        # 포지션 크기 한도
        if order_value > exchange_config.max_position_size:
            return False
        
        # 일일 손실 한도
        daily_pnl = self.daily_pnl.get(exchange_type, 0)
        if daily_pnl < -exchange_config.daily_loss_limit:
            return False
        
        return True
    
    def record_trade(self, exchange_type: str, pnl: float):
        """거래 기록"""
        if exchange_type not in self.daily_trades:
            self.daily_trades[exchange_type] = 0
        if exchange_type not in self.daily_pnl:
            self.daily_pnl[exchange_type] = 0
        
        self.daily_trades[exchange_type] += 1
        self.daily_pnl[exchange_type] += pnl
    
    def reset_daily_stats(self):
        """일일 통계 초기화"""
        self.daily_trades.clear()
        self.daily_pnl.clear()
    
    def get_daily_stats(self) -> Dict[str, Dict]:
        """일일 통계 조회"""
        stats = {}
        for exchange_type in self.config.exchanges:
            stats[exchange_type] = {
                "trades": self.daily_trades.get(exchange_type, 0),
                "pnl": self.daily_pnl.get(exchange_type, 0)
            }
        return stats
