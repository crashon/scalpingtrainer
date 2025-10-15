import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, PlainTextResponse
from pydantic import BaseModel
from database import SessionLocal, engine, get_db_session
from models import Base
from data_feed import ensure_symbol_listener, get_broadcaster
from multi_exchange_data_feed import multi_exchange_feed
from exchange_factory import ExchangeFactory
from trading_config import TradingConfig, TradingManager, TradingMode, ExchangeConfig
from real_trading_service import RealTradingService
from multi_symbol_service import multi_symbol_service
from ai_trading_service import AITradingService
from trade_service import save_trade
from report_service import get_daily_pnl
from position_service import PositionService
from sqlalchemy.orm import Session
import time
import random
from collections import deque, defaultdict
import urllib.request
import urllib.error
import urllib.parse
import json as pyjson
import os

Base.metadata.create_all(bind=engine)

# 실제 거래 설정 초기화
trading_config = TradingConfig(mode=TradingMode.SIMULATION)
trading_manager = TradingManager(trading_config)
real_trading_service = RealTradingService(trading_manager)

# AI 트레이딩 서비스 초기화
def get_ai_trading_service():
    with get_db_session() as db:
        return AITradingService(db, real_trading_service)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    loop = asyncio.get_event_loop()
    # start default BTCUSDT listener
    loop.create_task(ensure_symbol_listener('BTCUSDT'))
    yield
    # Shutdown
    # listeners will naturally stop when process exits

app = FastAPI(title="Scalping Trainer", version="1.0.0", lifespan=lifespan)

# CORS 설정 (환경변수로 제한 가능)
# ALLOWED_ORIGINS: comma-separated list, e.g. "https://app.example.com,https://admin.example.com"
# CORS_ALLOW_CREDENTIALS: "true" or "false" (default false)
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = ["*"]

allow_credentials_env = os.getenv("CORS_ALLOW_CREDENTIALS", "false").strip().lower()
allow_credentials = allow_credentials_env == "true"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙 (React 빌드 파일용) - 디렉토리가 존재할 때만
import os
if os.path.exists("dist/assets"):
    app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

class TradeRequest(BaseModel):
    symbol: str
    side: str   # BUY or SELL
    price: float
    qty: float

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def read_index():
    return FileResponse('index.html')

@app.post("/api/trade")
def create_trade(trade_request: TradeRequest, db: Session = Depends(get_db)):
    # Update database position and compute pnl if applicable
    pnl = update_position_on_trade(
        db=db,
        symbol=trade_request.symbol,
        side=trade_request.side.upper(),
        price=trade_request.price,
        qty=trade_request.qty
    )
    trade = save_trade(db, trade_request.symbol, trade_request.side, trade_request.price, trade_request.qty, pnl=pnl)
    return {"status": "ok", "trade_id": trade.id, "pnl": pnl}

@app.get("/api/report/daily")
def daily_report(date_str: str, db: Session = Depends(get_db)):
    report = get_daily_pnl(db, date_str)
    return report

@app.get("/api/trades")
def get_trades(db: Session = Depends(get_db)):
    from models import Trade
    trades = db.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
    return [
        {
            "id": trade.id,
            "symbol": trade.symbol,
            "side": trade.side,
            "price": trade.price,
            "qty": trade.qty,
            "timestamp": trade.timestamp.isoformat() if trade.timestamp else None,
            "pnl": trade.pnl
        }
        for trade in trades
    ]

_candle_cache = {}
_CANDLE_TTL_SECONDS = 30

# ----------------------
# Optional Redis client (for multi-instance deployments)
# ----------------------
_redis = None
try:
    import redis  # type: ignore
    REDIS_URL = os.getenv("REDIS_URL")
    if REDIS_URL:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    _redis = None

# ----------------------
# Optional Prometheus metrics
# ----------------------
_metrics = None
try:
    from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST  # type: ignore
    CANDLE_CACHE_HIT = Counter('candle_cache_hit_total', 'Candle cache hits')
    CANDLE_CACHE_MISS = Counter('candle_cache_miss_total', 'Candle cache misses')
    RL_HIT = Counter('rate_limit_exceeded_total', 'Rate limit exceeded events')
    RETRIES = Counter('upstream_retries_total', 'Upstream retry attempts')
    _metrics = {
        'hit': CANDLE_CACHE_HIT,
        'miss': CANDLE_CACHE_MISS,
        'rl': RL_HIT,
        'retry': RETRIES,
    }
except Exception:
    _metrics = None

# ----------------------
# Simple in-memory rate limiter (sliding window)
# ----------------------
_rate_buckets: Dict[str, deque] = defaultdict(deque)
_RL_WINDOW_SEC = 10  # sliding window length
_RL_MAX_CALLS = 20   # max allowed calls per window per key

def _rl_check(key: str):
    now = time.time()
    if _redis is not None:
        zkey = f"rl:{key}"
        pipe = _redis.pipeline()
        cutoff = now - _RL_WINDOW_SEC
        pipe.zremrangebyscore(zkey, 0, cutoff)
        pipe.zadd(zkey, {str(now): now})
        pipe.zcard(zkey)
        pipe.expire(zkey, _RL_WINDOW_SEC)
        _, _, count, _ = pipe.execute()
        if count is not None and int(count) > _RL_MAX_CALLS:
            if _metrics:
                _metrics['rl'].inc()
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please slow down.")
        return
    # fallback in-memory
    dq = _rate_buckets[key]
    while dq and now - dq[0] > _RL_WINDOW_SEC:
        dq.popleft()
    if len(dq) >= _RL_MAX_CALLS:
        if _metrics:
            _metrics['rl'].inc()
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please slow down.")
    dq.append(now)


def _cache_get(key: str):
    if _redis is not None:
        val = _redis.get(key)
        if val:
            try:
                if _metrics: _metrics['hit'].inc()
                return pyjson.loads(val)
            except Exception:
                return None
        if _metrics: _metrics['miss'].inc()
        return None
    v = _candle_cache.get(key)
    if v: 
        if _metrics: _metrics['hit'].inc()
    else:
        if _metrics: _metrics['miss'].inc()
    return v


def _cache_set(key: str, value, ttl: int):
    if _redis is not None:
        try:
            _redis.setex(key, ttl, pyjson.dumps(value))
            return
        except Exception:
            pass
    _candle_cache[key] = (time.time(), value)


def _binance_fetch_with_retry(url: str, max_retries: int = 3, base_delay: float = 0.3):
    """
    Fetch URL with exponential backoff + jitter. Honors Retry-After on HTTPError 429/5xx if present.
    Returns parsed JSON.
    """
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = resp.read()
                return pyjson.loads(data)
        except urllib.error.HTTPError as e:  # type: ignore
            last_err = e
            status = getattr(e, 'code', None)
            if status and status in (429, 500, 502, 503, 504):
                # honor Retry-After if present
                retry_after = 0.0
                try:
                    ra = e.headers.get('Retry-After')
                    if ra:
                        retry_after = float(ra)
                except Exception:
                    retry_after = 0.0
                # compute backoff with jitter
                delay = retry_after if retry_after > 0 else base_delay * (2 ** attempt)
                delay = delay + random.uniform(0, 0.2)
                if attempt < max_retries:
                    if _metrics: _metrics['retry'].inc()
                    time.sleep(delay)
                    continue
            # non-retryable
            break
        except (urllib.error.URLError, TimeoutError) as e:  # type: ignore
            last_err = e
            if attempt < max_retries:
                if _metrics: _metrics['retry'].inc()
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.2)
                time.sleep(delay)
                continue
            break
        except Exception as e:
            last_err = e
            break
    # give up
    raise HTTPException(status_code=502, detail=f"Upstream fetch failed: {last_err}")


@app.get("/api/candles")
def get_candles(request: Request, symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 500, startTime: int | None = None, endTime: int | None = None):
    """
    Fetch recent candles from Binance and return lightweight-charts friendly format.
    Response: [{ time: epoch_sec, open, high, low, close }]
    """
    try:
        # per-IP + global limiter keys
        client_ip = request.client.host if request and request.client else "unknown"
        _rl_check(f"candles:ip:{client_ip}")
        _rl_check("candles:global")

        cache_key = f"candles:{symbol.upper()}:{interval}:{max(1, min(limit, 1000))}:{startTime or ''}:{endTime or ''}"
        now = time.time()
        # Redis cache returns value only, in-memory stores (timestamp, value)
        cached = _cache_get(cache_key)
        if cached:
            # If Redis provided, cached is the value directly
            if _redis is not None:
                return cached
            # in-memory tuple structure
            if isinstance(cached, tuple) and len(cached) == 2:
                ts, val = cached
                if now - ts < _CANDLE_TTL_SECONDS:
                    return val

        base_params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": max(1, min(limit, 1000)),
        }
        if startTime:
            base_params["startTime"] = int(startTime)
        if endTime:
            base_params["endTime"] = int(endTime)
        params = urllib.parse.urlencode(base_params)
        url = f"https://api.binance.com/api/v3/klines?{params}"
        arr = _binance_fetch_with_retry(url)
        candles = []
        for k in arr:
            # [ openTime, open, high, low, close, volume, closeTime, ... ]
            open_time_ms = k[0]
            open_p = float(k[1])
            high_p = float(k[2])
            low_p = float(k[3])
            close_p = float(k[4])
            vol = float(k[5])
            candles.append({
                "time": int(open_time_ms // 1000),
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": round(vol, 6),
            })
        _cache_set(cache_key, candles, _CANDLE_TTL_SECONDS)
        return candles
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ----------------------
# Health/Ready/Metric endpoints
# ----------------------
@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    if _redis is None:
        return {"status": "ok", "redis": "disabled"}
    try:
        _redis.ping()
        return {"status": "ok", "redis": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"redis not ready: {e}")


@app.get("/metrics")
def metrics():
    if _metrics is None:
        return PlainTextResponse("metrics disabled", status_code=200)
    try:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"metrics error: {e}")

@app.websocket("/ws/price")
async def price_ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Read query param ?symbol=BTCUSDT (case-insensitive)
    try:
        symbol = websocket.query_params.get('symbol', 'BTCUSDT')
    except Exception:
        symbol = 'BTCUSDT'
    
    await ensure_symbol_listener(symbol)
    bc = get_broadcaster(symbol)
    queue = await bc.register()
    
    try:
        # Send latest price immediately if available
        if bc.latest_price:
            await websocket.send_json(bc.latest_price)
        
        # Keep connection alive with periodic pings
        while True:
            try:
                # Wait for new data with timeout
                payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(payload)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_json({"type": "ping", "timestamp": int(time.time() * 1000)})
            except Exception as e:
                print(f"Error sending WebSocket message: {e}")
                break
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for {symbol}")
    except Exception as e:
        print(f"WebSocket error for {symbol}: {e}")
    finally:
        await bc.unregister(queue)


# ----------------------
# Position Management (Database-based)
# ----------------------
def get_position_service(db: Session = Depends(get_db)) -> PositionService:
    return PositionService(db)

def update_position_on_trade(db: Session, symbol: str, side: str, price: float, qty: float) -> float:
    """
    Update position with a new trade and return realized PnL if any (for the closing portion).
    Simplified netting logic:
    - Same side: average entry price.
    - Opposite side: reduce existing qty; if flipped, set new side/entry.
    """
    position_service = PositionService(db)
    position = position_service.get_position(symbol)
    realized_pnl = 0.0

    if not position or position.qty == 0 or position.side is None:
        # Open new position
        position_service.create_or_update_position(symbol, side, qty, price, price)
        return 0.0

    if side == position.side:
        # Increase position and average entry
        new_qty = position.qty + qty
        if new_qty > 0:
            new_entry_price = (position.entry_price * position.qty + price * qty) / new_qty
            position_service.create_or_update_position(symbol, side, new_qty, new_entry_price, price)
        return 0.0
    else:
        # Reduce or flip
        if qty < position.qty:
            # Partial close
            if position.side == 'BUY':
                realized_pnl = (price - position.entry_price) * qty
            else:
                realized_pnl = (position.entry_price - price) * qty
            new_qty = position.qty - qty
            position_service.create_or_update_position(symbol, position.side, new_qty, position.entry_price, price)
        elif qty == position.qty:
            # Full close
            if position.side == 'BUY':
                realized_pnl = (price - position.entry_price) * qty
            else:
                realized_pnl = (position.entry_price - price) * qty
            position_service.close_position(symbol, qty)
        else:
            # Flip position: close existing then open new with remaining
            close_qty = position.qty
            if position.side == 'BUY':
                realized_pnl = (price - position.entry_price) * close_qty
            else:
                realized_pnl = (position.entry_price - price) * close_qty
            # Open new
            remaining = qty - close_qty
            position_service.create_or_update_position(symbol, side, remaining, price, price)

        return realized_pnl


class ClosePositionRequest(BaseModel):
    symbol: str
    price: Optional[float] = None  # if not provided, use latest price
    qty: Optional[float] = None    # if not provided, close full


@app.get("/api/position")
def get_position(symbol: str = "BTCUSDT", db: Session = Depends(get_db)):
    position_service = PositionService(db)
    pos = position_service.get_position(symbol)
    
    # Get latest price and update position
    latest = None
    try:
        bc = get_broadcaster(symbol)
        if bc.latest_price and isinstance(bc.latest_price, dict):
            latest = bc.latest_price.get("price")
        elif isinstance(bc.latest_price, (int, float)):
            latest = bc.latest_price
    except Exception:
        latest = None
    
    # Update position with latest price if available
    if latest and pos:
        position_service.update_position_price(symbol, latest)
        pos = position_service.get_position(symbol)  # Refresh position
    
    return position_service.to_dict(pos)


@app.post("/api/position/close")
def close_position(req: ClosePositionRequest, db: Session = Depends(get_db)):
    position_service = PositionService(db)
    
    # Determine price
    price = req.price
    if price is None:
        try:
            bc = get_broadcaster(req.symbol)
            if bc.latest_price and isinstance(bc.latest_price, dict):
                price = bc.latest_price.get("price")
            elif isinstance(bc.latest_price, (int, float)):
                price = bc.latest_price
        except Exception:
            pass
    
    if price is None:
        return {"status": "error", "message": "No price available to close position"}

    # Snapshot current position before closing
    before = position_service.get_position(req.symbol)
    if not before or before.qty <= 0:
        return {"status": "error", "message": "No active position to close"}
    
    prev_side = before.side
    prev_qty = before.qty

    # Compute realized PnL
    closed_qty = prev_qty if (req.qty is None or req.qty >= prev_qty) else req.qty
    if prev_side == 'BUY':
        realized = (price - before.entry_price) * closed_qty
    else:  # SELL
        realized = (before.entry_price - price) * closed_qty

    # Close position in database
    position_service.close_position(req.symbol, closed_qty)

    # Record a closing trade for auditability using the opposite side
    if prev_side == 'BUY':
        close_side = 'SELL'
    elif prev_side == 'SELL':
        close_side = 'BUY'
    else:
        close_side = 'CLOSE'
    save_trade(db, req.symbol, close_side, price, closed_qty, pnl=realized)

    return {"status": "ok", "realized_pnl": realized, "price": price, "closed_qty": closed_qty}

@app.get("/api/positions")
def get_all_positions(db: Session = Depends(get_db)):
    """모든 활성 포지션 조회"""
    position_service = PositionService(db)
    positions = position_service.get_all_positions()
    
    # Update all positions with latest prices
    for pos in positions:
        try:
            bc = get_broadcaster(pos.symbol)
            if bc.latest_price and isinstance(bc.latest_price, dict):
                latest = bc.latest_price.get("price")
            elif isinstance(bc.latest_price, (int, float)):
                latest = bc.latest_price
            else:
                latest = None
            
            if latest:
                position_service.update_position_price(pos.symbol, latest)
        except Exception:
            pass
    
    # Refresh positions after price updates
    positions = position_service.get_all_positions()
    return [position_service.to_dict(pos) for pos in positions]

# ----------------------
# Multi-Exchange APIs
# ----------------------

@app.get("/api/exchanges")
def get_available_exchanges():
    """사용 가능한 거래소 목록 조회"""
    return {
        "exchanges": ExchangeFactory.get_available_exchanges(),
        "active_exchanges": multi_exchange_feed.get_available_exchanges()
    }

@app.post("/api/exchanges/{exchange_type}/connect")
def connect_exchange(exchange_type: str, api_key: str = None, api_secret: str = None, testnet: bool = True):
    """거래소 연결"""
    try:
        multi_exchange_feed.add_exchange(exchange_type, api_key, api_secret, testnet)
        return {"status": "ok", "message": f"Connected to {exchange_type}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/exchanges/{exchange_type}/ticker/{symbol}")
async def get_exchange_ticker(exchange_type: str, symbol: str):
    """거래소별 현재 가격 조회"""
    try:
        ticker = await multi_exchange_feed.get_ticker(exchange_type, symbol)
        return ticker
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/exchanges/{exchange_type}/klines/{symbol}")
async def get_exchange_klines(exchange_type: str, symbol: str, interval: str = "1m", limit: int = 500):
    """거래소별 캔들 데이터 조회"""
    try:
        klines = await multi_exchange_feed.get_klines(exchange_type, symbol, interval, limit)
        return klines
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/exchanges/prices/{symbol}")
def get_all_exchange_prices(symbol: str):
    """모든 거래소의 가격 조회"""
    prices = multi_exchange_feed.get_all_prices(symbol)
    return {
        "symbol": symbol,
        "prices": prices,
        "timestamp": int(time.time() * 1000)
    }

@app.websocket("/ws/multi-exchange/{symbol}")
async def multi_exchange_websocket(websocket: WebSocket, symbol: str):
    """다중 거래소 WebSocket"""
    await websocket.accept()
    
    # 기본적으로 Binance와 Bybit 연결
    exchanges = ["binance", "bybit"]
    queues = {}
    
    try:
        # 각 거래소에 구독
        for exchange_type in exchanges:
            try:
                queue = await multi_exchange_feed.subscribe(exchange_type, symbol)
                queues[exchange_type] = queue
            except Exception as e:
                print(f"Failed to subscribe to {exchange_type}: {e}")
        
        # 메시지 브로드캐스트
        while True:
            for exchange_type, queue in queues.items():
                try:
                    # 비동기적으로 큐에서 메시지 가져오기
                    message = await asyncio.wait_for(queue.get(), timeout=0.1)
                    await websocket.send_json(message)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"Error processing {exchange_type} message: {e}")
            
            await asyncio.sleep(0.01)  # CPU 사용량 조절
            
    except WebSocketDisconnect:
        pass
    finally:
        # 구독 해제
        for exchange_type, queue in queues.items():
            try:
                await multi_exchange_feed.unsubscribe(exchange_type, symbol, queue)
            except Exception as e:
                print(f"Error unsubscribing from {exchange_type}: {e}")

# ----------------------
# Real Trading APIs
# ----------------------

class ExchangeConfigRequest(BaseModel):
    api_key: str
    api_secret: str
    testnet: bool = True
    enabled: bool = False
    max_position_size: float = 1000.0
    daily_loss_limit: float = 100.0
    max_leverage: int = 20

class TradingModeRequest(BaseModel):
    mode: str  # "simulation", "paper_trading", "live_trading"

class RealOrderRequest(BaseModel):
    exchange_type: str
    symbol: str
    side: str
    quantity: float
    price: float = None
    order_type: str = "MARKET"

@app.get("/api/trading/config")
def get_trading_config():
    """거래 설정 조회"""
    return {
        "mode": trading_config.mode.value,
        "exchanges": {
            name: {
                "exchange_type": config.exchange_type,
                "enabled": config.enabled,
                "testnet": config.testnet,
                "max_position_size": config.max_position_size,
                "daily_loss_limit": config.daily_loss_limit,
                "max_leverage": config.max_leverage
            }
            for name, config in trading_config.exchanges.items()
        },
        "risk_management": trading_config.risk_management,
        "auto_close_on_loss": trading_config.auto_close_on_loss,
        "max_daily_trades": trading_config.max_daily_trades
    }

@app.post("/api/trading/config/exchange/{exchange_type}")
def configure_exchange(exchange_type: str, config: ExchangeConfigRequest):
    """거래소 설정"""
    try:
        exchange_config = ExchangeConfig(
            exchange_type=exchange_type,
            api_key=config.api_key,
            api_secret=config.api_secret,
            testnet=config.testnet,
            enabled=config.enabled,
            max_position_size=config.max_position_size,
            daily_loss_limit=config.daily_loss_limit,
            max_leverage=config.max_leverage
        )
        
        trading_config.exchanges[exchange_type] = exchange_config
        return {"status": "ok", "message": f"Exchange {exchange_type} configured"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/trading/config/mode")
def set_trading_mode(mode_request: TradingModeRequest):
    """거래 모드 설정"""
    try:
        mode = TradingMode(mode_request.mode)
        trading_config.mode = mode
        return {"status": "ok", "message": f"Trading mode set to {mode.value}"}
    except ValueError:
        return {"status": "error", "message": "Invalid trading mode"}

@app.post("/api/trading/order")
async def place_real_order(order_request: RealOrderRequest, db: Session = Depends(get_db)):
    """실제 주문 실행"""
    return await real_trading_service.place_real_order(
        db=db,
        exchange_type=order_request.exchange_type,
        symbol=order_request.symbol,
        side=order_request.side,
        quantity=order_request.quantity,
        price=order_request.price,
        order_type=order_request.order_type
    )

@app.delete("/api/trading/order/{exchange_type}/{symbol}/{order_id}")
async def cancel_real_order(exchange_type: str, symbol: str, order_id: str):
    """실제 주문 취소"""
    return await real_trading_service.cancel_real_order(exchange_type, symbol, order_id)

@app.get("/api/trading/positions/{exchange_type}")
async def get_real_positions(exchange_type: str):
    """실제 포지션 조회"""
    positions = await real_trading_service.get_real_positions(exchange_type)
    return {"positions": positions}

@app.get("/api/trading/account/{exchange_type}")
async def get_real_account_info(exchange_type: str):
    """실제 계좌 정보 조회"""
    account_info = await real_trading_service.get_real_account_info(exchange_type)
    return account_info

@app.get("/api/trading/stats")
def get_trading_stats():
    """거래 통계 조회"""
    return real_trading_service.get_trading_stats()

@app.post("/api/trading/reset-daily")
def reset_daily_stats():
    """일일 통계 초기화"""
    trading_manager.reset_daily_stats()
    return {"status": "ok", "message": "Daily stats reset"}

# ----------------------
# Multi-Symbol APIs
# ----------------------

class SymbolRequest(BaseModel):
    symbol: str
    exchanges: List[str] = None

class MultiSymbolOrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: float
    price: float
    exchange_type: str = None

class ClosePositionRequest(BaseModel):
    symbol: str
    quantity: float = None

@app.get("/api/symbols")
def get_active_symbols():
    """활성 심볼 목록 조회"""
    return {
        "active_symbols": multi_symbol_service.get_active_symbols(),
        "symbol_exchanges": {
            symbol: multi_symbol_service.get_symbol_exchanges(symbol)
            for symbol in multi_symbol_service.get_active_symbols()
        }
    }

@app.post("/api/symbols/add")
async def add_symbol(symbol_request: SymbolRequest):
    """심볼 추가"""
    try:
        success = await multi_symbol_service.add_symbol(
            symbol_request.symbol, 
            symbol_request.exchanges
        )
        if success:
            return {"status": "ok", "message": f"Symbol {symbol_request.symbol} added"}
        else:
            return {"status": "error", "message": "Failed to add symbol"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/symbols/{symbol}")
async def remove_symbol(symbol: str):
    """심볼 제거"""
    try:
        success = await multi_symbol_service.remove_symbol(symbol)
        if success:
            return {"status": "ok", "message": f"Symbol {symbol} removed"}
        else:
            return {"status": "error", "message": f"Symbol {symbol} not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/symbols/prices")
async def get_all_symbols_prices():
    """모든 심볼의 가격 조회"""
    try:
        prices = await multi_symbol_service.get_all_symbols_prices()
        return {
            "prices": prices,
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/symbols/{symbol}/prices")
async def get_symbol_prices(symbol: str):
    """특정 심볼의 가격 조회"""
    try:
        prices = await multi_symbol_service.get_symbol_prices(symbol)
        return {
            "symbol": symbol.upper(),
            "prices": prices,
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/symbols/order")
async def place_multi_symbol_order(order_request: MultiSymbolOrderRequest, db: Session = Depends(get_db)):
    """다중 심볼 주문 실행"""
    return await multi_symbol_service.place_multi_symbol_order(
        db=db,
        symbol=order_request.symbol,
        side=order_request.side,
        quantity=order_request.quantity,
        price=order_request.price,
        exchange_type=order_request.exchange_type
    )

@app.get("/api/symbols/positions")
async def get_multi_symbol_positions(symbol: str = None, db: Session = Depends(get_db)):
    """다중 심볼 포지션 조회"""
    try:
        positions = await multi_symbol_service.get_symbol_positions(db, symbol)
        return {"positions": positions}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/symbols/close")
async def close_symbol_position(close_request: ClosePositionRequest, db: Session = Depends(get_db)):
    """심볼 포지션 청산"""
    return await multi_symbol_service.close_symbol_position(
        db=db,
        symbol=close_request.symbol,
        quantity=close_request.quantity
    )

@app.websocket("/ws/multi-symbol")
async def multi_symbol_websocket(websocket: WebSocket):
    """다중 심볼 WebSocket"""
    await websocket.accept()
    
    try:
        # 모든 활성 심볼의 가격 스트림
        while True:
            prices = await multi_symbol_service.get_all_symbols_prices()
            if prices:
                await websocket.send_json({
                    "type": "prices",
                    "data": prices,
                    "timestamp": int(time.time() * 1000)
                })
            await asyncio.sleep(1)  # 1초마다 업데이트
    except WebSocketDisconnect:
        pass

@app.websocket("/ws/ai-trading")
async def ai_trading_websocket(websocket: WebSocket):
    """AI 트레이딩 WebSocket"""
    await websocket.accept()
    
    # AI 트레이딩 엔진에 WebSocket 클라이언트 등록
    with get_db_session() as db:
        ai_service = AITradingService(db, real_trading_service)
        if ai_service.engine:
            ai_service.engine.add_websocket_client(websocket)
    
    try:
        while True:
            try:
                # 매번 새로운 세션으로 AI 서비스 생성
                with get_db_session() as db:
                    ai_service = AITradingService(db, real_trading_service)
                    
                    # AI 상태 업데이트
                    status = ai_service.get_ai_status()
                    dashboard_data = ai_service.get_ai_dashboard_data()
                    
                try:
                    await websocket.send_json({
                        "type": "ai_status",
                        "data": {
                            "status": status,
                            "dashboard": dashboard_data,
                            "timestamp": int(time.time() * 1000)
                        }
                    })
                except Exception as ws_error:
                    print(f"Error sending WebSocket message: {ws_error}")
                    break  # WebSocket 연결이 끊어진 경우 루프 종료
                
                await asyncio.sleep(2)  # 2초마다 업데이트
            except Exception as e:
                print(f"Error in AI trading WebSocket loop: {e}")
                await asyncio.sleep(5)  # 오류 시 5초 대기
    except WebSocketDisconnect:
        print("AI trading WebSocket disconnected")
    except Exception as e:
        print(f"AI trading WebSocket error: {e}")
    finally:
        # WebSocket 연결이 끊어질 때 클라이언트 제거
        with get_db_session() as db:
            ai_service = AITradingService(db, real_trading_service)
            if ai_service.engine:
                ai_service.engine.remove_websocket_client(websocket)




# ----------------------
# AI Trading API Endpoints
# ----------------------

@app.get("/api/ai/status")
def get_ai_status():
    """AI 트레이딩 상태 조회"""
    with get_db_session() as db:
        ai_service = AITradingService(db, real_trading_service)
        return ai_service.get_ai_status()

@app.get("/api/ai/strategies")
def get_ai_strategies():
    """AI 트레이딩 전략 목록 조회"""
    with get_db_session() as db:
        ai_service = AITradingService(db, real_trading_service)
        return ai_service.get_strategies()

class AIStrategyRequest(BaseModel):
    name: str
    risk_level: str
    symbol: str
    exchange_type: str = "binance"
    timeframe: str = None
    leverage_min: float = None
    leverage_max: float = None
    position_size_usd: float = 100.0
    confidence_threshold: float = None
    max_daily_trades: int = 100
    stop_loss_pct: float = None
    take_profit_pct: float = None

@app.post("/api/ai/strategies")
def create_ai_strategy(strategy_request: AIStrategyRequest):
    """새로운 AI 트레이딩 전략 생성"""
    try:
        print(f"Received strategy request: {strategy_request}")
        with get_db_session() as db:
            ai_service = AITradingService(db, real_trading_service)
            result = ai_service.create_strategy(
                name=strategy_request.name,
                risk_level=strategy_request.risk_level,
                symbol=strategy_request.symbol,
                exchange_type=strategy_request.exchange_type,
                timeframe=strategy_request.timeframe,
                leverage_min=strategy_request.leverage_min,
                leverage_max=strategy_request.leverage_max,
                position_size_usd=strategy_request.position_size_usd,
                confidence_threshold=strategy_request.confidence_threshold,
                max_daily_trades=strategy_request.max_daily_trades,
                stop_loss_pct=strategy_request.stop_loss_pct,
                take_profit_pct=strategy_request.take_profit_pct
            )
        print(f"Strategy creation result: {result}")
        return result
    except Exception as e:
        print(f"Error creating AI strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/ai/strategies/{config_id}")
def update_ai_strategy(config_id: int, **kwargs):
    """AI 트레이딩 전략 설정 업데이트"""
    ai_service = get_ai_trading_service()
    return ai_service.update_strategy(config_id, **kwargs)

@app.delete("/api/ai/strategies/{config_id}")
def delete_ai_strategy(config_id: int):
    """AI 트레이딩 전략 삭제"""
    ai_service = get_ai_trading_service()
    return ai_service.delete_strategy(config_id)

@app.post("/api/ai/strategies/{config_id}/toggle")
def toggle_ai_strategy(config_id: int):
    """AI 트레이딩 전략 활성화/비활성화"""
    ai_service = get_ai_trading_service()
    return ai_service.toggle_strategy(config_id)

@app.get("/api/ai/strategies/{config_id}/logs")
def get_ai_strategy_logs(config_id: int, limit: int = 100):
    """AI 트레이딩 전략 로그 조회"""
    ai_service = get_ai_trading_service()
    return ai_service.get_strategy_logs(config_id, limit)

@app.get("/api/ai/strategies/{config_id}/performance")
def get_ai_strategy_performance(config_id: int, period_type: str = "DAILY"):
    """AI 트레이딩 전략 성과 분석 조회"""
    ai_service = get_ai_trading_service()
    return ai_service.get_performance_analysis(config_id, period_type)

@app.post("/api/ai/strategies/{config_id}/reset")
def reset_ai_strategy_performance(config_id: int):
    """AI 트레이딩 전략 성과 리셋"""
    ai_service = get_ai_trading_service()
    return ai_service.reset_strategy_performance(config_id)

@app.post("/api/ai/start")
async def start_ai_trading():
    """AI 트레이딩 시작"""
    try:
        with get_db_session() as db:
            ai_service = AITradingService(db, real_trading_service)
            result = await ai_service.start_ai_trading()
        return result
    except Exception as e:
        print(f"Error starting AI trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ai/stop")
async def stop_ai_trading():
    """AI 트레이딩 중지"""
    try:
        with get_db_session() as db:
            ai_service = AITradingService(db, real_trading_service)
            result = await ai_service.stop_ai_trading()
        return result
    except Exception as e:
        print(f"Error stopping AI trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ai/dashboard")
def get_ai_dashboard():
    """AI 트레이딩 대시보드 데이터 조회"""
    with get_db_session() as db:
        ai_service = AITradingService(db, real_trading_service)
        return ai_service.get_ai_dashboard_data()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
