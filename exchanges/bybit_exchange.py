import asyncio
import aiohttp
import json
import websockets
from typing import Dict, List, Optional, Any
from datetime import datetime
from exchange_interface import ExchangeInterface, ExchangeType, OrderBook, Trade, Kline

class BybitExchange(ExchangeInterface):
    """Bybit 거래소 구현"""
    
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        super().__init__(api_key, api_secret, testnet)
        self.base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
        self.ws_base_url = "wss://stream-testnet.bybit.com" if testnet else "wss://stream.bybit.com"
    
    def get_exchange_name(self) -> str:
        return ExchangeType.BYBIT.value
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """현재 가격 조회"""
        url = f"{self.base_url}/v5/market/tickers"
        params = {"category": "spot", "symbol": symbol.upper()}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                    ticker = data["result"]["list"][0]
                    return {
                        "symbol": ticker["symbol"],
                        "price": float(ticker["lastPrice"]),
                        "timestamp": int(ticker["time"])
                    }
        return {}
    
    async def get_orderbook(self, symbol: str, limit: int = 100) -> OrderBook:
        """오더북 조회"""
        url = f"{self.base_url}/v5/market/orderbook"
        params = {"category": "spot", "symbol": symbol.upper(), "limit": limit}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                if data.get("retCode") == 0 and data.get("result"):
                    orderbook = data["result"]
                    return OrderBook(
                        symbol=orderbook["s"],
                        bids=[[float(bid[0]), float(bid[1])] for bid in orderbook["b"]],
                        asks=[[float(ask[0]), float(ask[1])] for ask in orderbook["a"]],
                        timestamp=int(orderbook["ts"])
                    )
        return OrderBook(symbol=symbol, bids=[], asks=[], timestamp=0)
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 500, 
                        start_time: int = None, end_time: int = None) -> List[Kline]:
        """캔들 데이터 조회"""
        url = f"{self.base_url}/v5/market/kline"
        params = {
            "category": "spot",
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit
        }
        
        if start_time:
            params["start"] = start_time
        if end_time:
            params["end"] = end_time
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                    return [
                        Kline(
                            symbol=symbol.upper(),
                            interval=interval,
                            open_time=int(kline[0]),
                            close_time=int(kline[0]) + self._interval_to_ms(interval),
                            open=float(kline[1]),
                            high=float(kline[2]),
                            low=float(kline[3]),
                            close=float(kline[4]),
                            volume=float(kline[5]),
                            quote_volume=float(kline[6]),
                            trades_count=int(kline[7])
                        )
                        for kline in data["result"]["list"]
                    ]
        return []
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """최근 거래 내역 조회"""
        url = f"{self.base_url}/v5/market/recent-trade"
        params = {"category": "spot", "symbol": symbol.upper(), "limit": limit}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                    return [
                        Trade(
                            symbol=trade["symbol"],
                            price=float(trade["price"]),
                            quantity=float(trade["size"]),
                            side=trade["side"].lower(),
                            timestamp=int(trade["time"])
                        )
                        for trade in data["result"]["list"]
                    ]
        return []
    
    async def place_order(self, symbol: str, side: str, order_type: str, 
                         quantity: float, price: float = None) -> Dict[str, Any]:
        """주문 실행 (실제 거래용) - 현재는 시뮬레이션만 지원"""
        return {
            "orderId": f"sim_{int(datetime.now().timestamp() * 1000)}",
            "symbol": symbol.upper(),
            "status": "Filled",
            "side": side.capitalize(),
            "type": order_type.capitalize(),
            "qty": str(quantity),
            "price": str(price) if price else "0",
            "cumExecQty": str(quantity),
            "timeInForce": "GTC",
            "createTime": int(datetime.now().timestamp() * 1000)
        }
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """주문 취소 (실제 거래용) - 현재는 시뮬레이션만 지원"""
        return {
            "orderId": order_id,
            "symbol": symbol.upper(),
            "status": "Cancelled"
        }
    
    async def get_account_info(self) -> Dict[str, Any]:
        """계좌 정보 조회 (실제 거래용) - 현재는 시뮬레이션만 지원"""
        return {
            "accountType": "UNIFIED",
            "accounts": [
                {"accountType": "SPOT", "totalWalletBalance": "10000", "totalAvailableBalance": "10000"}
            ]
        }
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """포지션 조회 (실제 거래용) - 현재는 시뮬레이션만 지원"""
        return []
    
    def get_websocket_url(self, symbol: str) -> str:
        """WebSocket URL 반환"""
        return f"{self.ws_base_url}/v5/public/spot"
    
    def parse_websocket_message(self, message: str) -> Optional[Dict[str, Any]]:
        """WebSocket 메시지 파싱"""
        try:
            data = json.loads(message)
            if data.get("topic") == f"publicTrade.{symbol.upper()}" and data.get("data"):
                trade_data = data["data"][0]
                return {
                    "symbol": trade_data["s"],
                    "price": float(trade_data["p"]),
                    "quantity": float(trade_data["v"]),
                    "side": trade_data["S"].lower(),
                    "timestamp": int(trade_data["T"])
                }
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        return None
    
    def _interval_to_ms(self, interval: str) -> int:
        """인터벌을 밀리초로 변환"""
        interval_map = {
            "1": 60 * 1000,
            "3": 3 * 60 * 1000,
            "5": 5 * 60 * 1000,
            "15": 15 * 60 * 1000,
            "30": 30 * 60 * 1000,
            "60": 60 * 60 * 1000,
            "120": 2 * 60 * 60 * 1000,
            "240": 4 * 60 * 60 * 1000,
            "360": 6 * 60 * 60 * 1000,
            "720": 12 * 60 * 60 * 1000,
            "D": 24 * 60 * 60 * 1000,
            "W": 7 * 24 * 60 * 60 * 1000
        }
        return interval_map.get(interval, 60 * 1000)
