"""Iceberg & Spoofing Detection Engine"""
import time
from collections import deque, defaultdict
from config import SPOOF_RATIO, SPOOF_WINDOW_SECONDS, ICEBERG_MAX_PRICE_MOVE, ICEBERG_LOOKBACK_SECONDS

class SpoofDetector:
    def __init__(self): self._depth_history = []
    def record_depth_snapshot(self, timestamp, bids, asks):
        self._depth_history.append((timestamp, {p:q for p,q in bids}, {p:q for p,q in asks}))
        cutoff = timestamp - SPOOF_WINDOW_SECONDS
        self._depth_history = [(ts,b,a) for ts,b,a in self._depth_history if ts > cutoff]
    def detect_fake_walls(self, current_bids, current_asks):
        fake_walls = []
        if len(self._depth_history) < 3: return fake_walls
        level_stats = defaultdict(lambda: {'total':0,'count':0})
        for ts, bids_dict, asks_dict in self._depth_history:
            for price, qty in bids_dict.items(): level_stats[('bid',price)]['total'] += qty; level_stats[('bid',price)]['count'] += 1
            for price, qty in asks_dict.items(): level_stats[('ask',price)]['total'] += qty; level_stats[('ask',price)]['count'] += 1
        for (side, price), stats in level_stats.items():
            if stats['count'] < 2: continue
            avg = stats['total'] / stats['count']
            if avg == 0: continue
            current_levels = current_bids if side=='bid' else current_asks
            current_size = next((q for p,q in current_levels if p==price), 0)
            if current_size > avg * SPOOF_RATIO:
                confidence = min(current_size/(avg*SPOOF_RATIO), 1.0)
                fake_walls.append({'side':side,'price':price,'size':current_size,'confidence':confidence,'likely_spoof':confidence>0.8})
        return fake_walls

class IcebergDetector:
    def __init__(self): self.price_movement_log = deque(maxlen=100); self.trade_at_same_price = defaultdict(list)
    def record_trade(self, price, quantity, timestamp=None):
        if timestamp is None: timestamp = time.time()
        self.trade_at_same_price[price].append(timestamp)
        self.price_movement_log.append((timestamp, price))
        cutoff = timestamp - ICEBERG_LOOKBACK_SECONDS
        self.price_movement_log = [(ts,p) for ts,p in self.price_movement_log if ts > cutoff]
        for p in list(self.trade_at_same_price.keys()):
            self.trade_at_same_price[p] = [t for t in self.trade_at_same_price[p] if t > cutoff]
            if not self.trade_at_same_price[p]: del self.trade_at_same_price[p]
    def detect_iceberg(self, current_bids, current_asks):
        icebergs = []; current_time = time.time()
        for price, timestamps in self.trade_at_same_price.items():
            recent = [t for t in timestamps if current_time-t < ICEBERG_LOOKBACK_SECONDS]
            if len(recent) >= 3 and self.price_movement_log:
                price_range = max(p for _,p in self.price_movement_log) - min(p for _,p in self.price_movement_log)
                if price_range < ICEBERG_MAX_PRICE_MOVE:
                    icebergs.append({'side':'buy','price':price,'strength':min(len(recent)/5.0,1.0),'trade_count':len(recent)})
        return icebergs
