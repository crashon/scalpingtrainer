import asyncio
import json
import websockets
from typing import List, Dict
from datetime import datetime

RECONNECT_DELAY = 5


class PriceBroadcaster:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.latest_price = None
        self.clients: List[asyncio.Queue] = []

    async def register(self):
        q = asyncio.Queue()
        self.clients.append(q)
        return q

    async def unregister(self, q: asyncio.Queue):
        try:
            self.clients.remove(q)
        except ValueError:
            pass

    async def broadcast(self, message: dict):
        self.latest_price = message
        for q in list(self.clients):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                pass


_broadcasters: Dict[str, PriceBroadcaster] = {}
_listener_tasks: Dict[str, asyncio.Task] = {}


def get_broadcaster(symbol: str) -> PriceBroadcaster:
    sym = symbol.upper()
    if sym not in _broadcasters:
        _broadcasters[sym] = PriceBroadcaster(sym)
    return _broadcasters[sym]


async def binance_listener(symbol: str):
    sym = symbol.lower()
    ws_url = f"wss://stream.binance.com:9443/ws/{sym}@aggTrade"
    bc = get_broadcaster(symbol)
    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=60, ping_timeout=10) as ws:
                print(f"[{datetime.utcnow()}] Connected to Binance websocket for {symbol}.")
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                        price = None
                        if "p" in data:
                            price = float(data["p"])
                            ts = data.get("T")
                            qty = float(data.get("q", 0))
                        elif "data" in data and isinstance(data["data"], dict) and "p" in data["data"]:
                            price = float(data["data"]["p"])
                            ts = data["data"].get("T")
                            qty = float(data["data"].get("q", 0))
                        else:
                            continue
                        payload = {
                            "symbol": symbol.upper(),
                            "price": price,
                            "qty": qty,
                            "timestamp": ts or int(datetime.utcnow().timestamp() * 1000)
                        }
                        await bc.broadcast(payload)
                    except Exception as e:
                        print("Parse error:", e)
        except Exception as e:
            print(f"Binance websocket error ({symbol}): {e}. Reconnecting in {RECONNECT_DELAY}s...")
            await asyncio.sleep(RECONNECT_DELAY)


async def ensure_symbol_listener(symbol: str):
    sym = symbol.upper()
    if sym in _listener_tasks and not _listener_tasks[sym].done():
        return
    loop = asyncio.get_event_loop()
    _listener_tasks[sym] = loop.create_task(binance_listener(sym))
