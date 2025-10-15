from sqlalchemy.orm import Session
from models import Trade

def save_trade(db: Session, symbol, side, price, qty, pnl=0.0):
    trade = Trade(
        symbol=symbol,
        side=side,
        price=price,
        qty=qty,
        pnl=pnl
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade
