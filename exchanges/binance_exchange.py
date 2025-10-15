import asyncio
import aiohttp
import json
import websockets
from typing import Dict, List, Optional, Any
from datetime import datetime
from exchange_interface import ExchangeInterface, ExchangeType, OrderBook, Trade, Kline

class BinanceExchange(ExchangeInterface):
    """Binance 거래소 구현"""
    
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        super().__init__(api_key, api_secret, testnet)
        self.base_url = "https://testnet.binance.vision" if testnet else "https://api.binance.com"
        self.ws_base_url = "wss://testnet.binance.vision" if testnet else "wss://stream.binance.com:9443"
    
    def get_exchange_name(self) -> str:
        return ExchangeType.BINANCE.value
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """현재 가격 조회"""
        url = f"{self.base_url}/api/v3/ticker/price"
        params = {"symbol": symbol.upper()}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return {
                    "symbol": data["symbol"],
                    "price": float(data["price"]),
                    "timestamp": int(datetime.now().timestamp() * 1000)
                }
    
    async def get_orderbook(self, symbol: str, limit: int = 100) -> OrderBook:
        """오더북 조회"""
        url = f"{self.base_url}/api/v3/depth"
        params = {"symbol": symbol.upper(), "limit": limit}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return OrderBook(
                    symbol=data["symbol"],
                    bids=[[float(bid[0]), float(bid[1])] for bid in data["bids"]],
                    asks=[[float(ask[0]), float(ask[1])] for ask in data["asks"]],
                    timestamp=int(datetime.now().timestamp() * 1000)
                )
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 500, 
                        start_time: int = None, end_time: int = None) -> List[Kline]:
        """캔들 데이터 조회"""
        url = f"{self.base_url}/api/v3/klines"
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit
        }
        
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return [
                    Kline(
                        symbol=symbol.upper(),
                        interval=interval,
                        open_time=int(kline[0]),
                        close_time=int(kline[6]),
                        open=float(kline[1]),
                        high=float(kline[2]),
                        low=float(kline[3]),
                        close=float(kline[4]),
                        volume=float(kline[5]),
                        quote_volume=float(kline[7]),
                        trades_count=int(kline[8])
                    )
                    for kline in data
                ]
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """최근 거래 내역 조회"""
        url = f"{self.base_url}/api/v3/trades"
        params = {"symbol": symbol.upper(), "limit": limit}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                return [
                    Trade(
                        symbol=trade["symbol"],
                        price=float(trade["price"]),
                        quantity=float(trade["qty"]),
                        side=trade["isBuyerMaker"] and "sell" or "buy",
                        timestamp=int(trade["time"])
                    )
                    for trade in data
                ]
    
    async def place_order(self, symbol: str, side: str, order_type: str, 
                         quantity: float, price: float = None) -> Dict[str, Any]:
        """주문 실행 (실제 거래용) - 현재는 시뮬레이션만 지원"""
        # 실제 구현에서는 Binance API를 사용하여 주문 실행
        # 현재는 시뮬레이션을 위해 가짜 응답 반환
        return {
            "orderId": f"sim_{int(datetime.now().timestamp() * 1000)}",
            "symbol": symbol.upper(),
            "status": "FILLED",
            "side": side.upper(),
            "type": order_type.upper(),
            "origQty": str(quantity),
            "price": str(price) if price else "0",
            "executedQty": str(quantity),
            "transactTime": int(datetime.now().timestamp() * 1000)
        }
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """주문 취소 (실제 거래용) - 현재는 시뮬레이션만 지원"""
        return {
            "orderId": order_id,
            "symbol": symbol.upper(),
            "status": "CANCELED"
        }
    
    async def get_account_info(self) -> Dict[str, Any]:
        """계좌 정보 조회 (실제 거래용) - 현재는 시뮬레이션만 지원"""
        return {
            "accountType": "SPOT",
            "balances": [
                {"asset": "USDT", "free": "10000.00000000", "locked": "0.00000000"},
                {"asset": "BTC", "free": "0.00000000", "locked": "0.00000000"}
            ]
        }
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """포지션 조회 (실제 거래용) - 현재는 시뮬레이션만 지원"""
        return []
    
    def get_websocket_url(self, symbol: str) -> str:
        """WebSocket URL 반환"""
        stream_name = f"{symbol.lower()}@aggTrade"
        return f"{self.ws_base_url}/ws/{stream_name}"
    
    def parse_websocket_message(self, message: str) -> Optional[Dict[str, Any]]:
        """WebSocket 메시지 파싱"""
        try:
            data = json.loads(message)
            if "p" in data and "q" in data:
                return {
                    "symbol": data.get("s", "").upper(),
                    "price": float(data["p"]),
                    "quantity": float(data["q"]),
                    "side": "buy" if data.get("m", False) else "sell",
                    "timestamp": int(data.get("T", 0))
                }
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        return None
