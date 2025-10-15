import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import json
import math

class TechnicalIndicators:
    """기술적 지표 계산 클래스"""
    
    @staticmethod
    def sma(data: List[float], period: int) -> List[float]:
        """단순 이동평균"""
        if len(data) < period:
            return [0] * len(data)
        
        result = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(0)
            else:
                result.append(sum(data[i-period+1:i+1]) / period)
        return result
    
    @staticmethod
    def ema(data: List[float], period: int) -> List[float]:
        """지수 이동평균"""
        if len(data) < period:
            return [0] * len(data)
        
        multiplier = 2 / (period + 1)
        result = [0] * len(data)
        result[period-1] = sum(data[:period]) / period
        
        for i in range(period, len(data)):
            result[i] = (data[i] * multiplier) + (result[i-1] * (1 - multiplier))
        
        return result
    
    @staticmethod
    def rsi(data: List[float], period: int = 14) -> List[float]:
        """RSI (Relative Strength Index)"""
        if len(data) < period + 1:
            return [50] * len(data)
        
        deltas = [data[i] - data[i-1] for i in range(1, len(data))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gains = TechnicalIndicators.sma(gains, period)
        avg_losses = TechnicalIndicators.sma(losses, period)
        
        result = [50] * period
        for i in range(period, len(data)):
            if i < len(avg_losses) and avg_losses[i] == 0:
                result.append(100)
            elif i < len(avg_losses) and i < len(avg_gains):
                rs = avg_gains[i] / avg_losses[i]
                rsi = 100 - (100 / (1 + rs))
                result.append(rsi)
            else:
                result.append(50)
        
        return result
    
    @staticmethod
    def macd(data: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[float], List[float], List[float]]:
        """MACD 지표"""
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        
        macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(data))]
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        histogram = [macd_line[i] - signal_line[i] for i in range(len(data))]
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(data: List[float], period: int = 20, std_dev: float = 2) -> Tuple[List[float], List[float], List[float]]:
        """볼린저 밴드"""
        sma = TechnicalIndicators.sma(data, period)
        
        upper_band = []
        lower_band = []
        
        for i in range(len(data)):
            if i < period - 1:
                upper_band.append(data[i])
                lower_band.append(data[i])
            else:
                std = np.std(data[i-period+1:i+1])
                upper_band.append(sma[i] + (std * std_dev))
                lower_band.append(sma[i] - (std * std_dev))
        
        return upper_band, sma, lower_band
    
    @staticmethod
    def stochastic(high: List[float], low: List[float], close: List[float], k_period: int = 14, d_period: int = 3) -> Tuple[List[float], List[float]]:
        """스토캐스틱 지표"""
        k_percent = []
        d_percent = []
        
        for i in range(len(close)):
            if i < k_period - 1:
                k_percent.append(50)
            else:
                highest_high = max(high[i-k_period+1:i+1])
                lowest_low = min(low[i-k_period+1:i+1])
                if highest_high != lowest_low:
                    k = ((close[i] - lowest_low) / (highest_high - lowest_low)) * 100
                else:
                    k = 50
                k_percent.append(k)
        
        d_percent = TechnicalIndicators.sma(k_percent, d_period)
        
        return k_percent, d_percent
    
    @staticmethod
    def atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
        """ATR (Average True Range)"""
        if len(high) < 2:
            return [0] * len(high)
        
        true_ranges = []
        for i in range(1, len(high)):
            tr1 = high[i] - low[i]
            tr2 = abs(high[i] - close[i-1])
            tr3 = abs(low[i] - close[i-1])
            true_ranges.append(max(tr1, tr2, tr3))
        
        # ATR 계산
        atr_values = [0] * (len(high) - len(true_ranges))
        atr_values.extend(TechnicalIndicators.sma(true_ranges, period))
        
        return atr_values
    
    @staticmethod
    def williams_r(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
        """Williams %R"""
        williams_values = []
        
        for i in range(len(close)):
            if i < period - 1:
                williams_values.append(-50)
            else:
                highest_high = max(high[i-period+1:i+1])
                lowest_low = min(low[i-period+1:i+1])
                if highest_high != lowest_low:
                    wr = ((highest_high - close[i]) / (highest_high - lowest_low)) * -100
                else:
                    wr = -50
                williams_values.append(wr)
        
        return williams_values
    
    @staticmethod
    def cci(high: List[float], low: List[float], close: List[float], period: int = 20) -> List[float]:
        """CCI (Commodity Channel Index)"""
        cci_values = []
        
        for i in range(len(close)):
            if i < period - 1:
                cci_values.append(0)
            else:
                typical_price = (high[i] + low[i] + close[i]) / 3
                sma_tp = sum([(high[j] + low[j] + close[j]) / 3 for j in range(i-period+1, i+1)]) / period
                mean_deviation = sum([abs((high[j] + low[j] + close[j]) / 3 - sma_tp) for j in range(i-period+1, i+1)]) / period
                
                if mean_deviation == 0:
                    cci_values.append(0)
                else:
                    cci = (typical_price - sma_tp) / (0.015 * mean_deviation)
                    cci_values.append(cci)
        
        return cci_values
    
    @staticmethod
    def adx(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
        """ADX (Average Directional Index)"""
        if len(high) < 2:
            return [0] * len(high)
        
        # DM 계산
        dm_plus = []
        dm_minus = []
        
        for i in range(1, len(high)):
            high_diff = high[i] - high[i-1]
            low_diff = low[i-1] - low[i]
            
            if high_diff > low_diff and high_diff > 0:
                dm_plus.append(high_diff)
            else:
                dm_plus.append(0)
            
            if low_diff > high_diff and low_diff > 0:
                dm_minus.append(low_diff)
            else:
                dm_minus.append(0)
        
        # True Range 계산
        tr_values = []
        for i in range(1, len(high)):
            tr1 = high[i] - low[i]
            tr2 = abs(high[i] - close[i-1])
            tr3 = abs(low[i] - close[i-1])
            tr_values.append(max(tr1, tr2, tr3))
        
        # DI 계산
        di_plus = []
        di_minus = []
        
        for i in range(len(dm_plus)):
            if i < period - 1:
                di_plus.append(0)
                di_minus.append(0)
            else:
                dm_plus_sma = sum(dm_plus[i-period+1:i+1]) / period
                dm_minus_sma = sum(dm_minus[i-period+1:i+1]) / period
                tr_sma = sum(tr_values[i-period+1:i+1]) / period
                
                if tr_sma == 0:
                    di_plus.append(0)
                    di_minus.append(0)
                else:
                    di_plus.append((dm_plus_sma / tr_sma) * 100)
                    di_minus.append((dm_minus_sma / tr_sma) * 100)
        
        # ADX 계산
        adx_values = [0] * (len(high) - len(di_plus))
        
        for i in range(len(di_plus)):
            if i < period - 1:
                adx_values.append(0)
            else:
                dx = abs(di_plus[i] - di_minus[i]) / (di_plus[i] + di_minus[i]) * 100 if (di_plus[i] + di_minus[i]) > 0 else 0
                if i == period - 1:
                    adx_values.append(dx)
                else:
                    adx_values.append((adx_values[-1] * (period - 1) + dx) / period)
        
        return adx_values


class AITradingStrategy:
    """AI 트레이딩 전략 기본 클래스"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.indicators = TechnicalIndicators()
    
    def analyze_market(self, candles: List[Dict]) -> Dict:
        """시장 분석"""
        if len(candles) < 50:
            return {"confidence": 0.0, "signal": "HOLD", "reason": "Insufficient data"}
        
        closes = [float(c['close']) for c in candles]
        highs = [float(c['high']) for c in candles]
        lows = [float(c['low']) for c in candles]
        volumes = [float(c.get('volume', 0)) for c in candles]
        
        # 기술적 지표 계산
        sma_20 = self.indicators.sma(closes, 20)
        sma_50 = self.indicators.sma(closes, 50)
        ema_12 = self.indicators.ema(closes, 12)
        ema_26 = self.indicators.ema(closes, 26)
        rsi = self.indicators.rsi(closes, 14)
        macd_line, macd_signal, macd_hist = self.indicators.macd(closes)
        bb_upper, bb_middle, bb_lower = self.indicators.bollinger_bands(closes)
        stoch_k, stoch_d = self.indicators.stochastic(highs, lows, closes)
        atr = self.indicators.atr(highs, lows, closes)
        williams_r = self.indicators.williams_r(highs, lows, closes)
        cci = self.indicators.cci(highs, lows, closes)
        adx = self.indicators.adx(highs, lows, closes)
        
        # 현재 가격
        current_price = closes[-1]
        prev_price = closes[-2] if len(closes) > 1 else current_price
        
        # 신호 분석
        signals = self._analyze_signals(
            current_price, prev_price, sma_20, sma_50, ema_12, ema_26,
            rsi, macd_line, macd_signal, macd_hist, bb_upper, bb_lower,
            stoch_k, stoch_d, volumes, atr, williams_r, cci, adx
        )
        
        return signals
    
    def _analyze_signals(self, current_price, prev_price, sma_20, sma_50, ema_12, ema_26,
                        rsi, macd_line, macd_signal, macd_hist, bb_upper, bb_lower,
                        stoch_k, stoch_d, volumes, atr, williams_r, cci, adx) -> Dict:
        """신호 분석 (하위 클래스에서 구현)"""
        raise NotImplementedError


class HighRiskStrategy(AITradingStrategy):
    """고위험 트레이딩 전략 (1분 매매, 레버리지 10-50x)"""
    
    def _analyze_signals(self, current_price, prev_price, sma_20, sma_50, ema_12, ema_26,
                        rsi, macd_line, macd_signal, macd_hist, bb_upper, bb_lower,
                        stoch_k, stoch_d, volumes, atr, williams_r, cci, adx) -> Dict:
        """고위험 전략 신호 분석"""
        
        # 1분 매매를 위한 빠른 신호
        signals = []
        confidence_scores = []
        
        # 1. RSI 과매수/과매도 신호
        if rsi[-1] < 30:  # 과매도
            signals.append("BUY")
            confidence_scores.append(0.8)
        elif rsi[-1] > 70:  # 과매수
            signals.append("SELL")
            confidence_scores.append(0.8)
        
        # 2. MACD 크로스오버
        if len(macd_line) >= 2 and len(macd_signal) >= 2:
            if macd_line[-1] > macd_signal[-1] and macd_line[-2] <= macd_signal[-2]:
                signals.append("BUY")
                confidence_scores.append(0.7)
            elif macd_line[-1] < macd_signal[-1] and macd_line[-2] >= macd_signal[-2]:
                signals.append("SELL")
                confidence_scores.append(0.7)
        
        # 3. 볼린저 밴드 탄력
        if current_price <= bb_lower[-1]:
            signals.append("BUY")
            confidence_scores.append(0.6)
        elif current_price >= bb_upper[-1]:
            signals.append("SELL")
            confidence_scores.append(0.6)
        
        # 4. 스토캐스틱 신호
        if stoch_k[-1] < 20 and stoch_d[-1] < 20:
            signals.append("BUY")
            confidence_scores.append(0.5)
        elif stoch_k[-1] > 80 and stoch_d[-1] > 80:
            signals.append("SELL")
            confidence_scores.append(0.5)
        
        # 5. Williams %R 신호
        if williams_r[-1] < -80:  # 과매도
            signals.append("BUY")
            confidence_scores.append(0.6)
        elif williams_r[-1] > -20:  # 과매수
            signals.append("SELL")
            confidence_scores.append(0.6)
        
        # 6. CCI 신호
        if cci[-1] < -100:  # 과매도
            signals.append("BUY")
            confidence_scores.append(0.5)
        elif cci[-1] > 100:  # 과매수
            signals.append("SELL")
            confidence_scores.append(0.5)
        
        # 7. ADX 트렌드 강도
        if adx[-1] > 25:  # 강한 트렌드
            if current_price > sma_20[-1]:
                signals.append("BUY")
                confidence_scores.append(0.7)
            elif current_price < sma_20[-1]:
                signals.append("SELL")
                confidence_scores.append(0.7)
        
        # 8. ATR 기반 변동성 분석
        if len(atr) > 0 and atr[-1] > 0:
            atr_ratio = atr[-1] / current_price
            if atr_ratio > 0.01:  # 높은 변동성
                price_change = (current_price - prev_price) / prev_price
                if price_change > 0.001:  # 0.1% 이상 상승
                    signals.append("BUY")
                    confidence_scores.append(0.3)
                elif price_change < -0.001:  # 0.1% 이상 하락
                    signals.append("SELL")
                    confidence_scores.append(0.3)
        
        # 신호 집계
        buy_signals = signals.count("BUY")
        sell_signals = signals.count("SELL")
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        if buy_signals > sell_signals and avg_confidence >= self.config.get('confidence_threshold', 0.7):
            return {
                "confidence": avg_confidence,
                "signal": "BUY",
                "reason": f"High risk strategy: {buy_signals} buy signals, confidence: {avg_confidence:.2f}",
                "technical_indicators": {
                    "rsi": rsi[-1],
                    "macd": macd_line[-1],
                    "bb_position": (current_price - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1]),
                    "stoch_k": stoch_k[-1],
                    "stoch_d": stoch_d[-1],
                    "williams_r": williams_r[-1],
                    "cci": cci[-1],
                    "adx": adx[-1],
                    "atr": atr[-1] if len(atr) > 0 else 0
                }
            }
        elif sell_signals > buy_signals and avg_confidence >= self.config.get('confidence_threshold', 0.7):
            return {
                "confidence": avg_confidence,
                "signal": "SELL",
                "reason": f"High risk strategy: {sell_signals} sell signals, confidence: {avg_confidence:.2f}",
                "technical_indicators": {
                    "rsi": rsi[-1],
                    "macd": macd_line[-1],
                    "bb_position": (current_price - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1]),
                    "stoch_k": stoch_k[-1],
                    "stoch_d": stoch_d[-1],
                    "williams_r": williams_r[-1],
                    "cci": cci[-1],
                    "adx": adx[-1],
                    "atr": atr[-1] if len(atr) > 0 else 0
                }
            }
        else:
            return {
                "confidence": avg_confidence,
                "signal": "HOLD",
                "reason": f"High risk strategy: insufficient signals (buy: {buy_signals}, sell: {sell_signals})",
                "technical_indicators": {
                    "rsi": rsi[-1],
                    "macd": macd_line[-1],
                    "bb_position": (current_price - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1]),
                    "stoch_k": stoch_k[-1],
                    "stoch_d": stoch_d[-1],
                    "williams_r": williams_r[-1],
                    "cci": cci[-1],
                    "adx": adx[-1],
                    "atr": atr[-1] if len(atr) > 0 else 0
                }
            }


class MediumRiskStrategy(AITradingStrategy):
    """중위험 트레이딩 전략 (5분 매매, 레버리지 5-10x)"""
    
    def _analyze_signals(self, current_price, prev_price, sma_20, sma_50, ema_12, ema_26,
                        rsi, macd_line, macd_signal, macd_hist, bb_upper, bb_lower,
                        stoch_k, stoch_d, volumes, atr, williams_r, cci, adx) -> Dict:
        """중위험 전략 신호 분석"""
        
        signals = []
        confidence_scores = []
        
        # 1. 이동평균 크로스오버
        if len(sma_20) >= 2 and len(sma_50) >= 2:
            if sma_20[-1] > sma_50[-1] and sma_20[-2] <= sma_50[-2]:
                signals.append("BUY")
                confidence_scores.append(0.8)
            elif sma_20[-1] < sma_50[-1] and sma_20[-2] >= sma_50[-2]:
                signals.append("SELL")
                confidence_scores.append(0.8)
        
        # 2. EMA 크로스오버
        if len(ema_12) >= 2 and len(ema_26) >= 2:
            if ema_12[-1] > ema_26[-1] and ema_12[-2] <= ema_26[-2]:
                signals.append("BUY")
                confidence_scores.append(0.7)
            elif ema_12[-1] < ema_26[-1] and ema_12[-2] >= ema_26[-2]:
                signals.append("SELL")
                confidence_scores.append(0.7)
        
        # 3. RSI 중립 구간에서의 신호
        if 40 <= rsi[-1] <= 60:
            if current_price > sma_20[-1]:
                signals.append("BUY")
                confidence_scores.append(0.6)
            elif current_price < sma_20[-1]:
                signals.append("SELL")
                confidence_scores.append(0.6)
        
        # 4. 볼린저 밴드 + RSI 조합
        bb_position = (current_price - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1])
        if bb_position < 0.2 and rsi[-1] < 50:
            signals.append("BUY")
            confidence_scores.append(0.7)
        elif bb_position > 0.8 and rsi[-1] > 50:
            signals.append("SELL")
            confidence_scores.append(0.7)
        
        # 5. MACD 히스토그램 변화
        if len(macd_hist) >= 2:
            if macd_hist[-1] > 0 and macd_hist[-2] <= 0:
                signals.append("BUY")
                confidence_scores.append(0.6)
            elif macd_hist[-1] < 0 and macd_hist[-2] >= 0:
                signals.append("SELL")
                confidence_scores.append(0.6)
        
        # 6. Williams %R + RSI 조합
        if williams_r[-1] < -70 and rsi[-1] < 40:
            signals.append("BUY")
            confidence_scores.append(0.8)
        elif williams_r[-1] > -30 and rsi[-1] > 60:
            signals.append("SELL")
            confidence_scores.append(0.8)
        
        # 7. CCI + 볼린저 밴드 조합
        bb_position = (current_price - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1])
        if cci[-1] < -100 and bb_position < 0.3:
            signals.append("BUY")
            confidence_scores.append(0.7)
        elif cci[-1] > 100 and bb_position > 0.7:
            signals.append("SELL")
            confidence_scores.append(0.7)
        
        # 8. ADX + 이동평균 조합
        if adx[-1] > 20:  # 트렌드 존재
            if current_price > ema_12[-1] > ema_26[-1]:
                signals.append("BUY")
                confidence_scores.append(0.6)
            elif current_price < ema_12[-1] < ema_26[-1]:
                signals.append("SELL")
                confidence_scores.append(0.6)
        
        # 신호 집계
        buy_signals = signals.count("BUY")
        sell_signals = signals.count("SELL")
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        if buy_signals > sell_signals and avg_confidence >= self.config.get('confidence_threshold', 0.6):
            return {
                "confidence": avg_confidence,
                "signal": "BUY",
                "reason": f"Medium risk strategy: {buy_signals} buy signals, confidence: {avg_confidence:.2f}",
                "technical_indicators": {
                    "sma_20": sma_20[-1],
                    "sma_50": sma_50[-1],
                    "ema_12": ema_12[-1],
                    "ema_26": ema_26[-1],
                    "rsi": rsi[-1],
                    "macd": macd_line[-1],
                    "bb_position": bb_position
                }
            }
        elif sell_signals > buy_signals and avg_confidence >= self.config.get('confidence_threshold', 0.6):
            return {
                "confidence": avg_confidence,
                "signal": "SELL",
                "reason": f"Medium risk strategy: {sell_signals} sell signals, confidence: {avg_confidence:.2f}",
                "technical_indicators": {
                    "sma_20": sma_20[-1],
                    "sma_50": sma_50[-1],
                    "ema_12": ema_12[-1],
                    "ema_26": ema_26[-1],
                    "rsi": rsi[-1],
                    "macd": macd_line[-1],
                    "bb_position": bb_position
                }
            }
        else:
            return {
                "confidence": avg_confidence,
                "signal": "HOLD",
                "reason": f"Medium risk strategy: insufficient signals (buy: {buy_signals}, sell: {sell_signals})",
                "technical_indicators": {
                    "sma_20": sma_20[-1],
                    "sma_50": sma_50[-1],
                    "ema_12": ema_12[-1],
                    "ema_26": ema_26[-1],
                    "rsi": rsi[-1],
                    "macd": macd_line[-1],
                    "bb_position": bb_position
                }
            }


class LowRiskStrategy(AITradingStrategy):
    """저위험 트레이딩 전략 (시간 매매, 레버리지 1-5x)"""
    
    def _analyze_signals(self, current_price, prev_price, sma_20, sma_50, ema_12, ema_26,
                        rsi, macd_line, macd_signal, macd_hist, bb_upper, bb_lower,
                        stoch_k, stoch_d, volumes, atr, williams_r, cci, adx) -> Dict:
        """저위험 전략 신호 분석"""
        
        signals = []
        confidence_scores = []
        
        # 1. 장기 이동평균 트렌드
        if len(sma_20) >= 5 and len(sma_50) >= 5:
            sma_20_trend = sum(sma_20[-5:]) / 5 - sum(sma_20[-10:-5]) / 5 if len(sma_20) >= 10 else 0
            sma_50_trend = sum(sma_50[-5:]) / 5 - sum(sma_50[-10:-5]) / 5 if len(sma_50) >= 10 else 0
            
            if sma_20_trend > 0 and sma_50_trend > 0 and current_price > sma_20[-1] > sma_50[-1]:
                signals.append("BUY")
                confidence_scores.append(0.9)
            elif sma_20_trend < 0 and sma_50_trend < 0 and current_price < sma_20[-1] < sma_50[-1]:
                signals.append("SELL")
                confidence_scores.append(0.9)
        
        # 2. RSI 트렌드 분석
        if len(rsi) >= 10:
            rsi_trend = sum(rsi[-5:]) / 5 - sum(rsi[-10:-5]) / 5
            if 30 <= rsi[-1] <= 50 and rsi_trend > 0:
                signals.append("BUY")
                confidence_scores.append(0.7)
            elif 50 <= rsi[-1] <= 70 and rsi_trend < 0:
                signals.append("SELL")
                confidence_scores.append(0.7)
        
        # 3. MACD 장기 신호
        if len(macd_line) >= 5 and len(macd_signal) >= 5:
            macd_above_signal = sum([1 for i in range(-5, 0) if macd_line[i] > macd_signal[i]])
            if macd_above_signal >= 4 and macd_line[-1] > macd_signal[-1]:
                signals.append("BUY")
                confidence_scores.append(0.8)
            elif macd_above_signal <= 1 and macd_line[-1] < macd_signal[-1]:
                signals.append("SELL")
                confidence_scores.append(0.8)
        
        # 4. 볼린저 밴드 + 거래량 분석
        bb_position = (current_price - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1])
        if len(volumes) >= 10:
            avg_volume = sum(volumes[-10:]) / 10
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            if bb_position < 0.3 and volume_ratio > 1.2:
                signals.append("BUY")
                confidence_scores.append(0.6)
            elif bb_position > 0.7 and volume_ratio > 1.2:
                signals.append("SELL")
                confidence_scores.append(0.6)
        
        # 5. ATR 기반 변동성 분석
        if len(atr) > 0 and atr[-1] > 0:
            atr_ratio = atr[-1] / current_price
            if atr_ratio < 0.005:  # 낮은 변동성 (안정적)
                if current_price > sma_50[-1]:
                    signals.append("BUY")
                    confidence_scores.append(0.6)
                elif current_price < sma_50[-1]:
                    signals.append("SELL")
                    confidence_scores.append(0.6)
        
        # 6. ADX + Williams %R 조합 (장기 트렌드)
        if adx[-1] > 30:  # 강한 트렌드
            if williams_r[-1] < -50 and current_price > sma_50[-1]:
                signals.append("BUY")
                confidence_scores.append(0.8)
            elif williams_r[-1] > -50 and current_price < sma_50[-1]:
                signals.append("SELL")
                confidence_scores.append(0.8)
        
        # 7. CCI + MACD 조합 (장기 신호)
        if cci[-1] < -50 and macd_line[-1] > macd_signal[-1]:
            signals.append("BUY")
            confidence_scores.append(0.7)
        elif cci[-1] > 50 and macd_line[-1] < macd_signal[-1]:
            signals.append("SELL")
            confidence_scores.append(0.7)
        
        # 8. 거래량 + ATR 조합
        if len(volumes) >= 10:
            avg_volume = sum(volumes[-10:]) / 10
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            if volume_ratio > 1.5 and len(atr) > 0:  # 거래량 증가 + 변동성
                atr_ratio = atr[-1] / current_price
                if atr_ratio > 0.01:  # 높은 변동성
                    if current_price > sma_20[-1]:
                        signals.append("BUY")
                        confidence_scores.append(0.5)
                    elif current_price < sma_20[-1]:
                        signals.append("SELL")
                        confidence_scores.append(0.5)
        
        # 신호 집계
        buy_signals = signals.count("BUY")
        sell_signals = signals.count("SELL")
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        if buy_signals > sell_signals and avg_confidence >= self.config.get('confidence_threshold', 0.5):
            return {
                "confidence": avg_confidence,
                "signal": "BUY",
                "reason": f"Low risk strategy: {buy_signals} buy signals, confidence: {avg_confidence:.2f}",
                "technical_indicators": {
                    "sma_20": sma_20[-1],
                    "sma_50": sma_50[-1],
                    "rsi": rsi[-1],
                    "macd": macd_line[-1],
                    "bb_position": bb_position,
                    "williams_r": williams_r[-1],
                    "cci": cci[-1],
                    "adx": adx[-1],
                    "atr": atr[-1] if len(atr) > 0 else 0
                }
            }
        elif sell_signals > buy_signals and avg_confidence >= self.config.get('confidence_threshold', 0.5):
            return {
                "confidence": avg_confidence,
                "signal": "SELL",
                "reason": f"Low risk strategy: {sell_signals} sell signals, confidence: {avg_confidence:.2f}",
                "technical_indicators": {
                    "sma_20": sma_20[-1],
                    "sma_50": sma_50[-1],
                    "rsi": rsi[-1],
                    "macd": macd_line[-1],
                    "bb_position": bb_position,
                    "williams_r": williams_r[-1],
                    "cci": cci[-1],
                    "adx": adx[-1],
                    "atr": atr[-1] if len(atr) > 0 else 0
                }
            }
        else:
            return {
                "confidence": avg_confidence,
                "signal": "HOLD",
                "reason": f"Low risk strategy: insufficient signals (buy: {buy_signals}, sell: {sell_signals})",
                "technical_indicators": {
                    "sma_20": sma_20[-1],
                    "sma_50": sma_50[-1],
                    "rsi": rsi[-1],
                    "macd": macd_line[-1],
                    "bb_position": bb_position,
                    "williams_r": williams_r[-1],
                    "cci": cci[-1],
                    "adx": adx[-1],
                    "atr": atr[-1] if len(atr) > 0 else 0
                }
            }


def create_strategy(risk_level: str, config: Dict) -> AITradingStrategy:
    """위험도에 따른 전략 생성"""
    if risk_level.upper() == "HIGH":
        return HighRiskStrategy(config)
    elif risk_level.upper() == "MEDIUM":
        return MediumRiskStrategy(config)
    elif risk_level.upper() == "LOW":
        return LowRiskStrategy(config)
    else:
        raise ValueError(f"Unknown risk level: {risk_level}")

