from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Trade
from datetime import datetime

def get_daily_pnl(db: Session, date_str: str):
    start = datetime.strptime(date_str + " 00:00:00", "%Y-%m-%d %H:%M:%S")
    end   = datetime.strptime(date_str + " 23:59:59", "%Y-%m-%d %H:%M:%S")

    result = db.query(
        func.sum(Trade.pnl).label("daily_pnl"),
        func.count(Trade.id).label("num_trades")
    ).filter(
        Trade.timestamp >= start,
        Trade.timestamp <= end
    ).first()

    return {
        "date": date_str,
        "daily_pnl": float(result.daily_pnl or 0.0),
        "num_trades": result.num_trades or 0
    }
