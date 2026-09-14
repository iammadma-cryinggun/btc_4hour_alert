"""Signal Engine + Half-Kelly Risk Management"""
import time
from collections import deque
from config import MAX_POSITION_RISK, HARD_STOP_LOSS_PCT, PROFIT_TRIGGER_PCT, TIME_STOP_SECONDS, CIRCUIT_BREAKER_LOSSES, CIRCUIT_BREAKER_LOSS_CUT, KELLY_FRACTION, MIN_HISTORY_TRADES

class KellyCalculator:
    def __init__(self): self.trade_history = deque(maxlen=200)
    def add_trade_result(self, won, pnl_pct): self.trade_history.append((won, pnl_pct))
    def calculate_kelly_fraction(self):
        if len(self.trade_history) < MIN_HISTORY_TRADES: return 0.01
        wins = sum(1 for w,_ in self.trade_history if w); p = wins/len(self.trade_history); q = 1-p
        avg_win = sum(pnl for _,pnl in self.trade_history if pnl>0)/max(sum(1 for _,pnl in self.trade_history if pnl>0),1)
        avg_loss = abs(sum(pnl for _,pnl in self.trade_history if pnl<0)/max(sum(1 for _,pnl in self.trade_history if pnl<0),1))
        if avg_loss==0: return 0.01
        b = avg_win/avg_loss
        return max(min((p*b-q)/b*KELLY_FRACTION, MAX_POSITION_RISK), 0.01)
    def get_stats(self):
        if not self.trade_history: return {'trades':0,'win_rate':0,'kelly_fraction':0}
        wins = sum(1 for w,_ in self.trade_history if w)
        return {'trades':len(self.trade_history),'win_rate':wins/len(self.trade_history),'kelly_fraction':self.calculate_kelly_fraction()}

class CircuitBreaker:
    def __init__(self): self.consecutive_losses = 0; self.cooldown_until = 0
    def record_trade(self, won):
        if won: self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            if self.consecutive_losses >= CIRCUIT_BREAKER_LOSSES:
                self.cooldown_until = time.time() + 86400; return True
        return False
    def should_reduce(self): return self.consecutive_losses >= CIRCUIT_BREAKER_LOSS_CUT
    def in_cooldown(self): return time.time() < self.cooldown_until
    def status(self): return {'consecutive_losses':self.consecutive_losses,'in_cooldown':self.in_cooldown()}

class RiskManager:
    def __init__(self): self.kelly = KellyCalculator(); self.circuit_breaker = CircuitBreaker(); self.open_positions = []
    def can_trade(self): return not self.circuit_breaker.in_cooldown()
    def calc_position_size(self, balance):
        base = self.kelly.calculate_kelly_fraction()
        return base*0.5 if self.circuit_breaker.should_reduce() else base
    def check_exit(self, pos, current_price):
        if not pos: return 'hold', None
        entry = pos['entry_price']; direction = pos['direction']
        pnl = (current_price-entry)/entry if direction=='long' else (entry-current_price)/entry
        if pnl <= -HARD_STOP_LOSS_PCT: return 'exit', 'HARD_STOP_LOSS'
        if pnl >= PROFIT_TRIGGER_PCT and current_price <= pos.get('breakeven_price', entry): return 'exit', 'BE_PRECISE_LOCK'
        if time.time()-pos.get('entry_time', time.time()) > TIME_STOP_SECONDS: return 'exit', 'TIME_STOP'
        return 'hold', None
    def record_result(self, won, pnl_pct): self.kelly.add_trade_result(won, pnl_pct); self.circuit_breaker.record_trade(won)
    def get_status(self): return {'circuit_breaker': self.circuit_breaker.status(), 'kelly_stats': self.kelly.get_stats()}
