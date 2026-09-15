"""多时间框架趋势过滤器"""
import time, sys, os
from collections import deque
import requests
from config import SYMBOL, TREND_EMA_FAST, TREND_EMA_SLOW, TREND_EMA_LONG, TREND_CONFIRM_BARS

API_BASE = 'https://api.binance.com/api/v3'

class TrendFilter:
    def __init__(self):
        self.h1_klines = deque(maxlen=TREND_EMA_LONG)
        self.h4_klines = deque(maxlen=TREND_EMA_LONG)
        self.last_h1_trend = 'unknown'
        self.last_h4_trend = 'unknown'
        self.trend_confirm_count = 0

    def fetch_klines(self, interval, limit=50):
        try:
            r = requests.get(f'{API_BASE}/klines', params={'symbol':SYMBOL,'interval':interval,'limit':limit}, timeout=8)
            if r.status_code == 200:
                return [{'open_time':k[0]/1000,'open':float(k[1]),'high':float(k[2]),'low':float(k[3]),'close':float(k[4]),'volume':float(k[5])} for k in r.json()]
        except: pass
        return []

    def update_trends(self):
        h1_data = self.fetch_klines('1h', 50)
        h4_data = self.fetch_klines('4h', 50)
        if h1_data: self.h1_klines.extend(h1_data)
        if h4_data: self.h4_klines.extend(h4_data)
        if len(self.h1_klines) >= TREND_EMA_LONG:
            self.last_h1_trend = self._calc_ema_trend(list(self.h1_klines))
        if len(self.h4_klines) >= TREND_EMA_LONG:
            self.last_h4_trend = self._calc_ema_trend(list(self.h4_klines))
        if (self.last_h1_trend in ['bullish','bearish'] and self.last_h4_trend == self.last_h1_trend):
            self.trend_confirm_count += 1
        else:
            self.trend_confirm_count = max(0, self.trend_confirm_count - 1)

    def _calc_ema_trend(self, klines):
        closes = [k['close'] for k in klines]
        ema_fast = self._ema(closes, TREND_EMA_FAST)
        ema_slow = self._ema(closes, TREND_EMA_SLOW)
        ema_long = self._ema(closes, TREND_EMA_LONG)
        if not all([ema_fast, ema_slow, ema_long]): return 'unknown'
        if ema_fast > ema_slow > ema_long: return 'bullish'
        elif ema_fast < ema_slow < ema_long: return 'bearish'
        elif abs(ema_fast - ema_slow) < abs(closes[-1])*0.001: return 'consolidation'
        return 'transition'

    @staticmethod
    def _ema(data, period):
        if len(data) < period: return None
        multiplier = 2/(period+1)
        ema = data[0]
        for price in data[1:]: ema = price*multiplier + ema*(1-multiplier)
        return ema

    def is_trend_valid(self, direction='long'):
        if direction == 'long':
            return self.last_h1_trend == 'bullish' and self.last_h4_trend == 'bullish' and self.trend_confirm_count >= TREND_CONFIRM_BARS
        elif direction == 'short':
            return self.last_h1_trend == 'bearish' and self.last_h4_trend == 'bearish' and self.trend_confirm_count >= TREND_CONFIRM_BARS
        return False

    def get_trend_info(self):
        return {'h1_trend':self.last_h1_trend,'h4_trend':self.last_h4_trend,'confirmed':self.trend_confirm_count>=TREND_CONFIRM_BARS,'confirm_count':self.trend_confirm_count,'h1_klines':len(self.h1_klines),'h4_klines':len(self.h4_klines)}
