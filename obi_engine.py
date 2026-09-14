"""Orderbook Imbalance (OBI) 计算引擎"""
import numpy as np
from collections import deque
from config import OBI_DEPTH_LEVELS, OBI_WINDOW_SIZE, OBI_CONFIRM_DURATION, OBI_THRESHOLD_LONG, OBI_THRESHOLD_SHORT

class OBIEngine:
    def __init__(self):
        self.depth_history = deque(maxlen=OBI_WINDOW_SIZE)
        self.last_depth = None
        self.obi_values = deque(maxlen=OBI_WINDOW_SIZE)

    def update_depth(self, bids, asks):
        self.last_depth = (bids, asks)
        bid_sum = sum(qty for _, qty in bids[:max(OBI_DEPTH_LEVELS)+1] if qty > 0)
        ask_sum = sum(qty for _, qty in asks[:max(OBI_DEPTH_LEVELS)+1] if qty > 0)
        total = bid_sum + ask_sum
        obi = (bid_sum - ask_sum) / total if total > 0 else 0.0
        self.obi_values.append(obi)
        self.depth_history.append({'bids': bids, 'asks': asks, 'obi': obi})
        return obi

    def get_obi(self):
        return self.obi_values[-1] if self.obi_values else 0.0

    def get_obi_moving_avg(self):
        return float(np.mean(list(self.obi_values))) if self.obi_values else 0.0

    def get_obi_trend(self):
        vals = list(self.obi_values)
        if len(vals) < 3: return 'neutral'
        recent = vals[-3:]
        avg_recent = np.mean(recent)
        avg_older = np.mean(vals[:-3]) if len(vals) > 3 else avg_recent
        if avg_recent > OBI_THRESHOLD_LONG and avg_recent > avg_older: return 'strengthening_buy'
        elif avg_recent > OBI_THRESHOLD_LONG and avg_recent <= avg_older: return 'weakening_buy'
        elif avg_recent < OBI_THRESHOLD_SHORT and avg_recent < avg_older: return 'strengthening_sell'
        elif avg_recent < OBI_THRESHOLD_SHORT and avg_recent >= avg_older: return 'weakening_sell'
        return 'neutral'

    def is_buy_pressure_dominant(self):
        vals = list(self.obi_values)
        return len(vals) >= OBI_CONFIRM_DURATION and all(v > OBI_THRESHOLD_LONG for v in vals[-OBI_CONFIRM_DURATION:])

    def is_sell_pressure_dominant(self):
        vals = list(self.obi_values)
        return len(vals) >= OBI_CONFIRM_DURATION and all(v < OBI_THRESHOLD_SHORT for v in vals[-OBI_CONFIRM_DURATION:])

    def get_depth_snapshot(self):
        if self.last_depth:
            bids, asks = self.last_depth
            return {
                'best_bid': bids[0][0] if bids else None,
                'best_ask': asks[0][0] if asks else None,
                'bid_depth_5': sum(qty for _, qty in bids[:5]),
                'ask_depth_5': sum(qty for _, qty in asks[:5]),
                'spread': asks[0][0] - bids[0][0] if (bids and asks) else None,
            }
        return {}


def parse_binance_depth(msg):
    """解析Binance深度消息"""
    bids = [(float(b[0]), float(b[1])) for b in msg.get('b', [])]
    asks = [(float(a[0]), float(a[1])) for a in msg.get('a', [])]
    return bids, asks
