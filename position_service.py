from sqlalchemy.orm import Session
from models import Position
from datetime import datetime
from typing import Optional, Dict, Any

class PositionService:
    def __init__(self, db: Session):
        self.db = db

    def get_position(self, symbol: str) -> Optional[Position]:
        """심볼에 대한 포지션 조회"""
        return self.db.query(Position).filter(
            Position.symbol == symbol.upper(),
            Position.is_active == True
        ).first()

    def create_or_update_position(self, symbol: str, side: str, qty: float, 
                                entry_price: float, latest_price: float = None) -> Position:
        """포지션 생성 또는 업데이트"""
        position = self.get_position(symbol)
        
        if not position:
            # 새 포지션 생성
            position = Position(
                symbol=symbol.upper(),
                side=side,
                qty=qty,
                entry_price=entry_price,
                latest_price=latest_price or entry_price,
                unrealized_pnl=0.0
            )
            self.db.add(position)
        else:
            # 기존 포지션 업데이트
            position.side = side
            position.qty = qty
            position.entry_price = entry_price
            if latest_price:
                position.latest_price = latest_price
            position.updated_at = datetime.utcnow()
        
        # 미실현손익 계산
        if latest_price and side and qty > 0:
            if side == 'BUY':
                position.unrealized_pnl = (latest_price - entry_price) * qty
            else:  # SELL
                position.unrealized_pnl = (entry_price - latest_price) * qty
        
        self.db.commit()
        self.db.refresh(position)
        return position

    def update_position_price(self, symbol: str, latest_price: float) -> Optional[Position]:
        """포지션의 최신 가격 업데이트"""
        position = self.get_position(symbol)
        if not position:
            return None
        
        position.latest_price = latest_price
        position.updated_at = datetime.utcnow()
        
        # 미실현손익 재계산
        if position.side and position.qty > 0:
            if position.side == 'BUY':
                position.unrealized_pnl = (latest_price - position.entry_price) * position.qty
            else:  # SELL
                position.unrealized_pnl = (position.entry_price - latest_price) * position.qty
        
        self.db.commit()
        self.db.refresh(position)
        return position

    def close_position(self, symbol: str, qty: float = None) -> Optional[Position]:
        """포지션 청산 (부분 또는 전체)"""
        position = self.get_position(symbol)
        if not position or position.qty <= 0:
            return None
        
        if qty is None or qty >= position.qty:
            # 전체 청산
            position.qty = 0.0
            position.side = None
            position.entry_price = 0.0
            position.unrealized_pnl = 0.0
        else:
            # 부분 청산
            position.qty -= qty
        
        position.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(position)
        return position

    def deactivate_position(self, symbol: str) -> bool:
        """포지션 비활성화"""
        position = self.get_position(symbol)
        if not position:
            return False
        
        position.is_active = False
        position.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def get_all_positions(self) -> list[Position]:
        """모든 활성 포지션 조회"""
        return self.db.query(Position).filter(
            Position.is_active == True,
            Position.qty > 0
        ).all()

    def to_dict(self, position: Position) -> Dict[str, Any]:
        """포지션을 딕셔너리로 변환"""
        if not position:
            return {
                "side": None,
                "qty": 0.0,
                "entry_price": None,
                "latest_price": None,
                "unrealized_pnl": 0.0
            }
        
        return {
            "side": position.side if position.qty > 0 else None,
            "qty": round(position.qty, 6),
            "entry_price": round(position.entry_price, 2) if position.qty > 0 else None,
            "latest_price": round(position.latest_price, 2) if position.latest_price else None,
            "unrealized_pnl": round(position.unrealized_pnl, 2),
            "created_at": position.created_at.isoformat() if position.created_at else None,
            "updated_at": position.updated_at.isoformat() if position.updated_at else None
        }
