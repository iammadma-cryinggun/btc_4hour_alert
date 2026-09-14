"""Micro-Apex V1.0 — 核心入口"""
import asyncio, json, time, sys, os, signal, argparse
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
import requests
from obi_engine import OBIEngine, parse_binance_depth
from cvd_engine import CVDEngine
from iceberg_spoof_detector import SpoofDetector, IcebergDetector
from trend_filter import TrendFilter
from signal_engine import RiskManager
from config import SYMBOL, DEBUG_MODE, POLL_INTERVAL_SECONDS, SIGNAL_LOG, OBI_THRESHOLD_LONG, OBI_THRESHOLD_SHORT, API_BASE

def _log(level, msg, **kwargs):
    entry = {"_msg": msg, "level": level, "ts": datetime.now(timezone.utc).isoformat()}
    entry.update(kwargs)
    print(json.dumps(entry, ensure_ascii=False))

def log_info(msg, **kwargs): _log("INFO", msg, **kwargs)
def log_error(msg, **kwargs): _log("ERROR", msg, **kwargs)

class MicroApexSystem:
    def __init__(self):
        self.obi = OBIEngine(); self.cvd = CVDEngine()
        self.spoof = SpoofDetector(); self.iceberg = IcebergDetector()
        self.trend = TrendFilter(); self.risk = RiskManager()
        self.signals = []; self.start_time = time.time(); self.buy_dom = False; self.sell_dom = False
        self.stats = {'polls':0,'trades':0,'spoofs':0}
        log_info("Micro-Apex system initialized", symbol=SYMBOL)

    def fetch_depth(self):
        try:
            r = requests.get(f'{API_BASE}/depth', params={'symbol':SYMBOL,'limit':20}, timeout=8)
            if r.status_code == 200:
                d = r.json()
                return [(float(b[0]),float(b[1])) for b in d['bids']], [(float(a[0]),float(a[1])) for a in d['asks']]
            else:
                log_error("fetch_depth_failed", status_code=r.status_code, symbol=SYMBOL)
        except Exception as e:
            log_error("fetch_depth_exception", error=str(e))
        return None, None

    def fetch_trades(self, limit=50):
        try:
            r = requests.get(f'{API_BASE}/trades', params={'symbol':SYMBOL,'limit':limit}, timeout=8)
            if r.status_code == 200: return r.json()
            else:
                log_error("fetch_trades_failed", status_code=r.status_code, symbol=SYMBOL)
        except Exception as e:
            log_error("fetch_trades_exception", error=str(e))
        return []

    def on_depth(self, bids, asks):
        self.obi.update_depth(bids, asks); self.stats['polls'] += 1
        self.spoof.record_depth_snapshot(time.time(), bids, asks)
        for fw in self.spoof.detect_fake_walls(bids, asks):
            if fw['likely_spoof']: self.stats['spoofs'] += 1

    def on_trade(self, trades):
        for trade in trades:
            qty = float(trade.get('q',0)); price = float(trade.get('p',0)); is_maker = trade.get('m',False)
            ts = trade.get('T',time.time())/1000.0
            self.cvd.add_trade(qty, is_maker, ts); self.iceberg.record_trade(price, qty, ts)
            self.stats['trades'] += 1

    def check_signals(self):
        obi, obi_ma, obi_t = self.obi.get_obi(), self.obi.get_obi_moving_avg(), self.obi.get_obi_trend()
        self.buy_dom, self.sell_dom = self.obi.is_buy_pressure_dominant(), self.obi.is_sell_pressure_dominant()
        cr, cb, cs = self.cvd.get_recent_cvd_ratio(), self.cvd.is_buy_dominant_recent(), self.cvd.is_sell_dominant_recent()
        d = self.obi.get_depth_snapshot()
        bids = self.obi.last_depth[0] if self.obi.last_depth else []
        asks = self.obi.last_depth[1] if self.obi.last_depth else []
        sigs = []
        if self.buy_dom and cb and obi > OBI_THRESHOLD_LONG and cr > 0.55:
            sigs.append({'type':'LONG_BREAKOUT','confidence':round(min((obi+cr)/2,1.0),4),'obi':round(obi,4),'obi_ma':round(obi_ma,4),'cvd_ratio':round(cr,4),'obi_trend':obi_t,'ts':datetime.now(timezone.utc).isoformat()})
        if self.sell_dom and cs and obi < OBI_THRESHOLD_SHORT and cr < 0.45:
            sigs.append({'type':'SHORT_BREAKOUT','confidence':round(min((-obi+(1-cr))/2,1.0),4),'obi':round(obi,4),'obi_ma':round(obi_ma,4),'cvd_ratio':round(cr,4),'obi_trend':obi_t,'ts':datetime.now(timezone.utc).isoformat()})
        for fw in self.spoof.detect_fake_walls(bids, asks):
            if fw['likely_spoof']:
                t = 'SHORT_SPOOF_REVERSAL' if fw['side']=='bid' else 'LONG_SPOOF_REVERSAL'
                sigs.append({'type':t,'confidence':round(fw['confidence'],4),'wall_price':fw['price'],'ts':datetime.now(timezone.utc).isoformat()})
        for s in sigs: self.signals.append(s)
        return sigs

    def dashboard(self):
        obi, cr = self.obi.get_obi(), self.cvd.get_recent_cvd_ratio()
        d = self.obi.get_depth_snapshot(); ti = self.trend.get_trend_info()
        log_info("dashboard", uptime=int(time.time()-self.start_time), polls=self.stats['polls'],
                 obi=round(obi,4), obi_ma=round(self.obi.get_obi_moving_avg(),4), obi_trend=self.obi.get_obi_trend(),
                 cvd_ratio=round(cr*100,2), cvd=round(self.cvd.get_cvd(),2),
                 h1=ti["h1_trend"], h4=ti["h4_trend"], confirmed=ti["confirmed"],
                 spread=d.get("spread",0), buy_dom=self.buy_dom, sell_dom=self.sell_dom,
                 signals=len(self.signals), spoofs=self.stats['spoofs'],
                 circuit_breaker=self.risk.circuit_breaker.in_cooldown())

    def run(self):
        log_info("Micro-Apex starting", symbol=SYMBOL.upper(), project="D Drive Project")
        last_dash, last_trade = 0, 0
        try:
            while True:
                now = time.time()
                bids, asks = self.fetch_depth()
                if bids and asks: self.on_depth(bids, asks)
                if now - last_trade >= POLL_INTERVAL_SECONDS*3:
                    trades = self.fetch_trades(50)
                    if trades: self.on_trade(trades)
                    last_trade = now
                new_signals = self.check_signals()
                if new_signals:
                    for s in new_signals:
                        icon = 'T' if 'LONG' in s['type'] else 'S'
                        log_info("signal", type=s['type'], confidence=s.get('confidence',0),
                                 obi=s.get('obi',0), cvd_ratio=s.get('cvd_ratio',0), icon=icon)
                if now - last_dash >= 3: self.dashboard(); last_dash = now
                time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            log_info("stopped", signals=len(self.signals))
        except Exception as e:
            log_error("fatal", error=str(e))
            import traceback; print(traceback.format_exc())

def main():
    p = argparse.ArgumentParser(description='Micro-Apex V1.0')
    args = p.parse_args()
    system = MicroApexSystem()
    signal.signal(signal.SIGINT, lambda s,f: sys.exit(f'\nStopped. {len(system.signals)} signals.'))
    system.run()

if __name__ == '__main__': main()
