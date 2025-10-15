from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

class ExchangeType(Enum):
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    COINBASE = "coinbase"

@dataclass
class OrderBook:
    symbol: str
    bids: List[List[float]]  # [[price, quantity], ...]
    asks: List[List[float]]  # [[price, quantity], ...]
    timestamp: int

@dataclass
class Trade:
    symbol: str
    price: float
    quantity: float
    side: str  # 'buy' or 'sell'
    timestamp: int

@dataclass
class Kline:
    symbol: str
    interval: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades_count: int

class ExchangeInterface(ABC):
    """거래소 인터페이스"""
    
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.name = self.get_exchange_name()
    
    @abstractmethod
    def get_exchange_name(self) -> str:
        """거래소 이름 반환"""
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """현재 가격 조회"""
        pass
    
    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 100) -> OrderBook:
        """오더북 조회"""
        pass
    
    @abstractmethod
    async def get_klines(self, symbol: str, interval: str, limit: int = 500, 
                        start_time: int = None, end_time: int = None) -> List[Kline]:
        """캔들 데이터 조회"""
        pass
    
    @abstractmethod
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """최근 거래 내역 조회"""
        pass
    
    @abstractmethod
    async def place_order(self, symbol: str, side: str, order_type: str, 
                         quantity: float, price: float = None) -> Dict[str, Any]:
        """주문 실행 (실제 거래용)"""
        pass
    
    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """주문 취소 (실제 거래용)"""
        pass
    
    @abstractmethod
    async def get_account_info(self) -> Dict[str, Any]:
        """계좌 정보 조회 (실제 거래용)"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """포지션 조회 (실제 거래용)"""
        pass
    
    @abstractmethod
    def get_websocket_url(self, symbol: str) -> str:
        """WebSocket URL 반환"""
        pass
    
    @abstractmethod
    def parse_websocket_message(self, message: str) -> Optional[Dict[str, Any]]:
        """WebSocket 메시지 파싱"""
        pass
