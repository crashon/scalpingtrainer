import asyncio
import json
import websockets
from typing import Dict, List, Optional, Callable
from datetime import datetime
from exchange_factory import ExchangeFactory
from exchange_interface import ExchangeType

class MultiExchangeDataFeed:
    """다중 거래소 데이터 피드"""
    
    def __init__(self):
        self.exchanges: Dict[str, any] = {}
        self.websocket_connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}
        self.latest_prices: Dict[str, Dict[str, float]] = {}  # {exchange: {symbol: price}}
        self.running = False
    
    def add_exchange(self, exchange_type: str, api_key: str = None, 
                    api_secret: str = None, testnet: bool = True):
        """거래소 추가"""
        exchange = ExchangeFactory.get_exchange(exchange_type, api_key, api_secret, testnet)
        self.exchanges[exchange_type] = exchange
        self.latest_prices[exchange_type] = {}
    
    async def start_websocket(self, exchange_type: str, symbol: str):
        """WebSocket 시작"""
        if exchange_type not in self.exchanges:
            raise ValueError(f"Exchange {exchange_type} not found")
        
        exchange = self.exchanges[exchange_type]
        ws_url = exchange.get_websocket_url(symbol)
        
        try:
            async with websockets.connect(ws_url) as websocket:
                self.websocket_connections[f"{exchange_type}_{symbol}"] = websocket
                print(f"[{datetime.utcnow()}] Connected to {exchange_type} WebSocket for {symbol}")
                
                async for message in websocket:
                    try:
                        data = exchange.parse_websocket_message(message)
                        if data and data.get("price"):
                            # 가격 업데이트
                            self.latest_prices[exchange_type][symbol] = data["price"]
                            
                            # 구독자들에게 브로드캐스트
                            await self._broadcast_price(exchange_type, symbol, data)
                    except Exception as e:
                        print(f"Error processing {exchange_type} message: {e}")
        except Exception as e:
            print(f"WebSocket error for {exchange_type} {symbol}: {e}")
        finally:
            if f"{exchange_type}_{symbol}" in self.websocket_connections:
                del self.websocket_connections[f"{exchange_type}_{symbol}"]
    
    async def _broadcast_price(self, exchange_type: str, symbol: str, data: dict):
        """가격 브로드캐스트"""
        key = f"{exchange_type}_{symbol}"
        if key in self.subscribers:
            for queue in self.subscribers[key]:
                try:
                    await queue.put({
                        "exchange": exchange_type,
                        "symbol": symbol,
                        "price": data["price"],
                        "quantity": data.get("quantity", 0),
                        "side": data.get("side", "unknown"),
                        "timestamp": data.get("timestamp", int(datetime.now().timestamp() * 1000))
                    })
                except asyncio.QueueFull:
                    pass
    
    async def subscribe(self, exchange_type: str, symbol: str) -> asyncio.Queue:
        """가격 구독"""
        key = f"{exchange_type}_{symbol}"
        if key not in self.subscribers:
            self.subscribers[key] = []
            # WebSocket 시작
            asyncio.create_task(self.start_websocket(exchange_type, symbol))
        
        queue = asyncio.Queue()
        self.subscribers[key].append(queue)
        return queue
    
    async def unsubscribe(self, exchange_type: str, symbol: str, queue: asyncio.Queue):
        """가격 구독 해제"""
        key = f"{exchange_type}_{symbol}"
        if key in self.subscribers:
            try:
                self.subscribers[key].remove(queue)
            except ValueError:
                pass
    
    def get_latest_price(self, exchange_type: str, symbol: str) -> Optional[float]:
        """최신 가격 조회"""
        return self.latest_prices.get(exchange_type, {}).get(symbol)
    
    def get_all_prices(self, symbol: str) -> Dict[str, float]:
        """모든 거래소의 가격 조회"""
        prices = {}
        for exchange_type in self.latest_prices:
            price = self.latest_prices[exchange_type].get(symbol)
            if price:
                prices[exchange_type] = price
        return prices
    
    async def get_ticker(self, exchange_type: str, symbol: str) -> dict:
        """현재 가격 조회 (REST API)"""
        if exchange_type not in self.exchanges:
            raise ValueError(f"Exchange {exchange_type} not found")
        
        exchange = self.exchanges[exchange_type]
        return await exchange.get_ticker(symbol)
    
    async def get_klines(self, exchange_type: str, symbol: str, interval: str, 
                        limit: int = 500, start_time: int = None, end_time: int = None) -> list:
        """캔들 데이터 조회"""
        if exchange_type not in self.exchanges:
            raise ValueError(f"Exchange {exchange_type} not found")
        
        exchange = self.exchanges[exchange_type]
        return await exchange.get_klines(symbol, interval, limit, start_time, end_time)
    
    def get_available_exchanges(self) -> List[str]:
        """사용 가능한 거래소 목록"""
        return list(self.exchanges.keys())
    
    async def stop_all(self):
        """모든 WebSocket 연결 종료"""
        for websocket in self.websocket_connections.values():
            await websocket.close()
        self.websocket_connections.clear()
        self.subscribers.clear()

# 전역 인스턴스
multi_exchange_feed = MultiExchangeDataFeed()
