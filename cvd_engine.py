"""Cumulative Volume Delta (CVD) 计算引擎"""
import time
from collections import deque
from config import CVD_LOOKBACK_SECONDS, CVD_CONFIRM_RATIO

class CVDEngine:
    def __init__(self):
        self.trade_log = deque()
        self._total_buy = 0.0
        self._total_sell = 0.0

    def add_trade(self, quantity, is_buyer_maker, timestamp=None):
        if timestamp is None: timestamp = time.time()
        self.trade_log.append((timestamp, quantity, is_buyer_maker))
        if not is_buyer_maker: self._total_buy += quantity
        else: self._total_sell += quantity
        self._cleanup_old_trades(timestamp)
        return self.get_cvd()

    def _cleanup_old_trades(self, current_time):
        cutoff = current_time - CVD_LOOKBACK_SECONDS
        while self.trade_log and self.trade_log[0][0] < cutoff:
            ts, qty, is_maker = self.trade_log.popleft()
            if not is_maker: self._total_buy -= qty
            else: self._total_sell -= qty

    def get_cvd(self): return self._total_buy - self._total_sell

    def get_recent_cvd_ratio(self):
        total = self._total_buy + self._total_sell
        return self._total_buy / total if total > 0 else 0.5

    def is_buy_dominant_recent(self): return self.get_recent_cvd_ratio() > CVD_CONFIRM_RATIO
    def is_sell_dominant_recent(self): return self.get_recent_cvd_ratio() < (1 - CVD_CONFIRM_RATIO)

    def get_trade_flow_stats(self, seconds=30):
        cutoff = time.time() - seconds
        buy_qty = sum(qty for ts,qty,m in self.trade_log if ts>=cutoff and not m)
        sell_qty = sum(qty for ts,qty,m in self.trade_log if ts>=cutup and m)
        total = buy_qty + sell_qty
        return {'buy_qty':buy_qty,'sell_qty':sell_qty,'buy_ratio':buy_qty/total if total>0 else 0.5}
