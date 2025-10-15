from typing import Dict, List, Optional, Set, Any
from sqlalchemy.orm import Session
from position_service import PositionService
from trade_service import save_trade
from multi_exchange_data_feed import multi_exchange_feed
import asyncio
from datetime import datetime

class MultiSymbolService:
    """다중 심볼 거래 서비스"""
    
    def __init__(self):
        self.active_symbols: Set[str] = set()
        self.symbol_exchanges: Dict[str, List[str]] = {}  # {symbol: [exchanges]}
        self.symbol_websockets: Dict[str, Dict[str, asyncio.Queue]] = {}  # {symbol: {exchange: queue}}
        self.running = False
    
    async def add_symbol(self, symbol: str, exchanges: List[str] = None) -> bool:
        """심볼 추가"""
        if exchanges is None:
            exchanges = ["binance", "bybit"]  # 기본 거래소
        
        symbol = symbol.upper()
        self.active_symbols.add(symbol)
        self.symbol_exchanges[symbol] = exchanges
        self.symbol_websockets[symbol] = {}
        
        # 각 거래소에 WebSocket 연결
        for exchange in exchanges:
            try:
                queue = await multi_exchange_feed.subscribe(exchange, symbol)
                self.symbol_websockets[symbol][exchange] = queue
            except Exception as e:
                print(f"Failed to subscribe {symbol} on {exchange}: {e}")
        
        return True
    
    async def remove_symbol(self, symbol: str) -> bool:
        """심볼 제거"""
        symbol = symbol.upper()
        if symbol not in self.active_symbols:
            return False
        
        # WebSocket 구독 해제
        if symbol in self.symbol_websockets:
            for exchange, queue in self.symbol_websockets[symbol].items():
                try:
                    await multi_exchange_feed.unsubscribe(exchange, symbol, queue)
                except Exception as e:
                    print(f"Error unsubscribing {symbol} from {exchange}: {e}")
            del self.symbol_websockets[symbol]
        
        self.active_symbols.discard(symbol)
        if symbol in self.symbol_exchanges:
            del self.symbol_exchanges[symbol]
        
        return True
    
    def get_active_symbols(self) -> List[str]:
        """활성 심볼 목록 조회"""
        return list(self.active_symbols)
    
    def get_symbol_exchanges(self, symbol: str) -> List[str]:
        """심볼의 거래소 목록 조회"""
        return self.symbol_exchanges.get(symbol.upper(), [])
    
    async def get_symbol_prices(self, symbol: str) -> Dict[str, float]:
        """심볼의 모든 거래소 가격 조회"""
        return multi_exchange_feed.get_all_prices(symbol.upper())
    
    async def get_all_symbols_prices(self) -> Dict[str, Dict[str, float]]:
        """모든 심볼의 가격 조회"""
        all_prices = {}
        for symbol in self.active_symbols:
            prices = await self.get_symbol_prices(symbol)
            if prices:
                all_prices[symbol] = prices
        return all_prices
    
    async def place_multi_symbol_order(self, db: Session, symbol: str, side: str, 
                                     quantity: float, price: float, 
                                     exchange_type: str = None) -> Dict[str, any]:
        """다중 심볼 주문 실행"""
        symbol = symbol.upper()
        
        if symbol not in self.active_symbols:
            return {"status": "error", "message": f"Symbol {symbol} not active"}
        
        # 거래소 선택
        if exchange_type:
            if exchange_type not in self.symbol_exchanges.get(symbol, []):
                return {"status": "error", "message": f"Exchange {exchange_type} not available for {symbol}"}
        else:
            # 기본 거래소 선택 (첫 번째)
            available_exchanges = self.symbol_exchanges.get(symbol, [])
            if not available_exchanges:
                return {"status": "error", "message": f"No exchanges available for {symbol}"}
            exchange_type = available_exchanges[0]
        
        # 포지션 업데이트
        position_service = PositionService(db)
        pnl = self._update_position_on_trade(position_service, symbol, side, price, quantity)
        
        # 거래 기록 저장
        trade = save_trade(db, symbol, side, price, quantity, pnl=pnl)
        
        return {
            "status": "ok",
            "trade_id": trade.id,
            "symbol": symbol,
            "exchange": exchange_type,
            "side": side,
            "price": price,
            "quantity": quantity,
            "pnl": pnl
        }
    
    def _update_position_on_trade(self, position_service: PositionService, 
                                symbol: str, side: str, price: float, 
                                quantity: float) -> float:
        """거래로 인한 포지션 업데이트"""
        position = position_service.get_position(symbol)
        realized_pnl = 0.0
        
        if not position or position.qty == 0 or position.side is None:
            # 새 포지션 생성
            position_service.create_or_update_position(symbol, side, quantity, price, price)
            return 0.0
        
        if side == position.side:
            # 포지션 증가
            new_qty = position.qty + quantity
            new_entry_price = (position.entry_price * position.qty + price * quantity) / new_qty
            position_service.create_or_update_position(symbol, side, new_qty, new_entry_price, price)
            return 0.0
        else:
            # 포지션 감소 또는 반전
            if quantity < position.qty:
                # 부분 청산
                if position.side == 'BUY':
                    realized_pnl = (price - position.entry_price) * quantity
                else:
                    realized_pnl = (position.entry_price - price) * quantity
                new_qty = position.qty - quantity
                position_service.create_or_update_position(symbol, position.side, new_qty, position.entry_price, price)
            elif quantity == position.qty:
                # 전체 청산
                if position.side == 'BUY':
                    realized_pnl = (price - position.entry_price) * quantity
                else:
                    realized_pnl = (position.entry_price - price) * quantity
                position_service.close_position(symbol, quantity)
            else:
                # 포지션 반전
                close_qty = position.qty
                if position.side == 'BUY':
                    realized_pnl = (price - position.entry_price) * close_qty
                else:
                    realized_pnl = (position.entry_price - price) * close_qty
                remaining = quantity - close_qty
                position_service.create_or_update_position(symbol, side, remaining, price, price)
        
        return realized_pnl
    
    async def get_symbol_positions(self, db: Session, symbol: str = None) -> Dict[str, any]:
        """심볼별 포지션 조회"""
        position_service = PositionService(db)
        
        if symbol:
            # 특정 심볼
            symbol = symbol.upper()
            position = position_service.get_position(symbol)
            return {symbol: position_service.to_dict(position)}
        else:
            # 모든 활성 심볼
            positions = {}
            for symbol in self.active_symbols:
                position = position_service.get_position(symbol)
                positions[symbol] = position_service.to_dict(position)
            return positions
    
    async def close_symbol_position(self, db: Session, symbol: str, 
                                  quantity: float = None) -> Dict[str, any]:
        """심볼 포지션 청산"""
        symbol = symbol.upper()
        position_service = PositionService(db)
        position = position_service.get_position(symbol)
        
        if not position or position.qty <= 0:
            return {"status": "error", "message": f"No active position for {symbol}"}
        
        # 청산 수량 결정
        close_qty = quantity if quantity else position.qty
        
        # 실현 손익 계산
        if position.side == 'BUY':
            realized_pnl = (position.latest_price - position.entry_price) * close_qty
        else:
            realized_pnl = (position.entry_price - position.latest_price) * close_qty
        
        # 포지션 청산
        position_service.close_position(symbol, close_qty)
        
        # 청산 거래 기록
        close_side = 'SELL' if position.side == 'BUY' else 'BUY'
        trade = save_trade(db, symbol, close_side, position.latest_price, close_qty, pnl=realized_pnl)
        
        return {
            "status": "ok",
            "trade_id": trade.id,
            "symbol": symbol,
            "closed_qty": close_qty,
            "realized_pnl": realized_pnl,
            "price": position.latest_price
        }
    
    async def start_price_monitoring(self):
        """가격 모니터링 시작"""
        self.running = True
        while self.running:
            try:
                # 모든 활성 심볼의 가격 업데이트
                for symbol in self.active_symbols:
                    if symbol in self.symbol_websockets:
                        for exchange, queue in self.symbol_websockets[symbol].items():
                            try:
                                # 비동기적으로 큐에서 메시지 가져오기
                                message = await asyncio.wait_for(queue.get(), timeout=0.1)
                                # 여기서 가격 업데이트 처리
                                # 예: 포지션의 미실현손익 업데이트 등
                            except asyncio.TimeoutError:
                                continue
                            except Exception as e:
                                print(f"Error processing {symbol} price from {exchange}: {e}")
                
                await asyncio.sleep(0.1)  # CPU 사용량 조절
            except Exception as e:
                print(f"Error in price monitoring: {e}")
                await asyncio.sleep(1)
    
    def stop_price_monitoring(self):
        """가격 모니터링 중지"""
        self.running = False

# 전역 인스턴스
multi_symbol_service = MultiSymbolService()
