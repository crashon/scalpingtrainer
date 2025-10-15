from typing import Dict, Optional, Any, List
from sqlalchemy.orm import Session
from exchange_factory import ExchangeFactory
from trading_config import TradingManager, TradingConfig, TradingMode
from position_service import PositionService
from trade_service import save_trade
import asyncio
from datetime import datetime

class RealTradingService:
    """실제 거래 서비스"""
    
    def __init__(self, trading_manager: TradingManager):
        self.trading_manager = trading_manager
    
    async def place_real_order(self, db: Session, exchange_type: str, symbol: str, 
                             side: str, quantity: float, price: float = None, 
                             order_type: str = "MARKET") -> Dict[str, Any]:
        """실제 주문 실행"""
        
        # 거래 가능 여부 확인
        if not self.trading_manager.can_place_order(exchange_type):
            return {
                "status": "error", 
                "message": f"Trading not enabled for {exchange_type}"
            }
        
        # 리스크 한도 확인
        order_value = quantity * (price or 0)
        if not self.trading_manager.check_risk_limits(exchange_type, order_value):
            return {
                "status": "error",
                "message": "Risk limits exceeded"
            }
        
        try:
            # 거래소 인스턴스 가져오기
            exchange_config = self.trading_manager.config.exchanges.get(exchange_type)
            if not exchange_config:
                return {"status": "error", "message": f"Exchange {exchange_type} not configured"}
            
            exchange = ExchangeFactory.get_exchange(
                exchange_type, 
                exchange_config.api_key, 
                exchange_config.api_secret, 
                exchange_config.testnet
            )
            
            # 실제 주문 실행
            if self.trading_manager.is_live_trading():
                # 라이브 거래
                order_result = await exchange.place_order(
                    symbol, side, order_type, quantity, price
                )
            else:
                # 페이퍼 트레이딩 (시뮬레이션)
                order_result = await exchange.place_order(
                    symbol, side, order_type, quantity, price
                )
            
            # 주문 결과 처리
            if order_result.get("status") in ["FILLED", "Filled"]:
                # 주문 성공
                filled_price = float(order_result.get("price", price or 0))
                filled_quantity = float(order_result.get("origQty", quantity))
                
                # 포지션 업데이트
                position_service = PositionService(db)
                pnl = self._update_position_on_real_trade(
                    position_service, symbol, side, filled_price, filled_quantity
                )
                
                # 거래 기록 저장
                trade = save_trade(
                    db, symbol, side, filled_price, filled_quantity, pnl=pnl
                )
                
                # 일일 통계 업데이트
                self.trading_manager.record_trade(exchange_type, pnl)
                
                return {
                    "status": "ok",
                    "trade_id": trade.id,
                    "order_id": order_result.get("orderId"),
                    "price": filled_price,
                    "quantity": filled_quantity,
                    "pnl": pnl,
                    "exchange": exchange_type,
                    "mode": "live" if self.trading_manager.is_live_trading() else "paper"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Order failed: {order_result.get('status', 'Unknown error')}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Trading error: {str(e)}"
            }
    
    def _update_position_on_real_trade(self, position_service: PositionService, 
                                     symbol: str, side: str, price: float, 
                                     quantity: float) -> float:
        """실제 거래로 인한 포지션 업데이트"""
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
    
    async def cancel_real_order(self, exchange_type: str, symbol: str, order_id: str) -> Dict[str, Any]:
        """실제 주문 취소"""
        try:
            exchange_config = self.trading_manager.config.exchanges.get(exchange_type)
            if not exchange_config:
                return {"status": "error", "message": f"Exchange {exchange_type} not configured"}
            
            exchange = ExchangeFactory.get_exchange(
                exchange_type,
                exchange_config.api_key,
                exchange_config.api_secret,
                exchange_config.testnet
            )
            
            result = await exchange.cancel_order(symbol, order_id)
            return {
                "status": "ok",
                "order_id": order_id,
                "result": result
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Cancel error: {str(e)}"
            }
    
    async def get_real_positions(self, exchange_type: str) -> List[Dict[str, Any]]:
        """실제 포지션 조회"""
        try:
            exchange_config = self.trading_manager.config.exchanges.get(exchange_type)
            if not exchange_config:
                return []
            
            exchange = ExchangeFactory.get_exchange(
                exchange_type,
                exchange_config.api_key,
                exchange_config.api_secret,
                exchange_config.testnet
            )
            
            positions = await exchange.get_positions()
            return positions
        except Exception as e:
            return []
    
    async def get_real_account_info(self, exchange_type: str) -> Dict[str, Any]:
        """실제 계좌 정보 조회"""
        try:
            exchange_config = self.trading_manager.config.exchanges.get(exchange_type)
            if not exchange_config:
                return {}
            
            exchange = ExchangeFactory.get_exchange(
                exchange_type,
                exchange_config.api_key,
                exchange_config.api_secret,
                exchange_config.testnet
            )
            
            account_info = await exchange.get_account_info()
            return account_info
        except Exception as e:
            return {}
    
    def get_trading_stats(self) -> Dict[str, Any]:
        """거래 통계 조회"""
        return {
            "mode": self.trading_manager.config.mode.value,
            "enabled_exchanges": [
                name for name, config in self.trading_manager.config.exchanges.items() 
                if config.enabled
            ],
            "daily_stats": self.trading_manager.get_daily_stats()
        }
