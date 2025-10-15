from typing import Dict, Optional
from exchange_interface import ExchangeInterface, ExchangeType
from exchanges.binance_exchange import BinanceExchange
from exchanges.bybit_exchange import BybitExchange

class ExchangeFactory:
    """거래소 팩토리"""
    
    _exchanges: Dict[str, ExchangeInterface] = {}
    
    @classmethod
    def get_exchange(cls, exchange_type: str, api_key: str = None, 
                    api_secret: str = None, testnet: bool = True) -> ExchangeInterface:
        """거래소 인스턴스 반환"""
        cache_key = f"{exchange_type}_{testnet}"
        
        if cache_key not in cls._exchanges:
            if exchange_type == ExchangeType.BINANCE.value:
                cls._exchanges[cache_key] = BinanceExchange(api_key, api_secret, testnet)
            elif exchange_type == ExchangeType.BYBIT.value:
                cls._exchanges[cache_key] = BybitExchange(api_key, api_secret, testnet)
            else:
                raise ValueError(f"Unsupported exchange type: {exchange_type}")
        
        return cls._exchanges[cache_key]
    
    @classmethod
    def get_available_exchanges(cls) -> list[str]:
        """사용 가능한 거래소 목록 반환"""
        return [exchange.value for exchange in ExchangeType]
    
    @classmethod
    def clear_cache(cls):
        """캐시 초기화"""
        cls._exchanges.clear()
