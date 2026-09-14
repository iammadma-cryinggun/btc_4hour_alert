"""
信号验证系统 (Signal Validator)
==================================
验证Micro-Apex生成的每个信号的准确率
- 记录信号：时间戳、方向、OBI、CVD、置信度
- 事后回测：N分钟后检查价格是否按预测方向移动
- 统计输出：胜率、EV、准确率趋势

核心逻辑：
- 信号触发时记录当前价格作为基准
- X分钟后获取K线收盘价
- 对比预测方向与实际走势
"""
import time, sys, os, json
from datetime import datetime, timezone
from collections import deque, defaultdict
import requests

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)
from config import SYMBOL, API_BASE, SIGNAL_VALIDATION_WINDOW_MINUTES, SIGNAL_VALIDATION_TICKS


class SignalRecord:
    """单笔信号记录"""
    def __init__(self, signal_type, confidence, obi, obi_ma, cvd_ratio, obi_trend,
                 entry_price, timestamp, direction):
        self.signal_type = signal_type          # LONG_BREAKOUT / SHORT_BREAKOUT / SPOOF_REVERSAL
        self.confidence = confidence            # 0~1
        self.obi = obi                          # 订单簿失衡率
        self.obi_ma = obi_ma                    # OBI移动平均
        self.cvd_ratio = cvd_ratio              # CVD买方占比
        self.obi_trend = obi_trend              # OBI趋势方向
        self.entry_price = entry_price          # 信号触发时的价格
        self.timestamp = timestamp              # 触发时间戳
        self.direction = direction              # 'long' / 'short'
        self.outcome = None                     # None=pending, 'win'/'loss'
        self.pnl_pct = 0.0                      # 盈亏百分比
        self.validation_time = None             # 验证时间

    def to_dict(self):
        return {
            'type': self.signal_type,
            'confidence': self.confidence,
            'obi': self.obi,
            'cvd_ratio': self.cvd_ratio,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'timestamp': self.timestamp,
            'outcome': self.outcome,
            'pnl_pct': self.pnl_pct,
            'validation_time': self.validation_time
        }


class SignalValidator:
    """信号验证引擎"""

    def __init__(self):
        self.records = deque(maxlen=1000)        # 信号记录
        self.pending = {}                         # 未验证的信号 {signal_id: SignalRecord}
        self.stats = {
            'total_signals': 0,
            'validated': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
        }
        self.accuracy_history = []                # 滚动胜率历史
        self.win_rate_by_confidence = defaultdict(list)  # 按置信度分组的胜率
        self.win_rate_by_obi = defaultdict(list)        # 按OBI分组的胜率

    def record_signal(self, signal_data, current_price):
        """
        记录一笔新信号
        signal_data: {type, confidence, obi, obi_ma, cvd_ratio, obi_trend, ts}
        current_price: 信号触发时的当前价格
        """
        direction = 'long' if 'LONG' in signal_data['type'] else 'short'
        record = SignalRecord(
            signal_type=signal_data['type'],
            confidence=signal_data['confidence'],
            obi=signal_data.get('obi', 0),
            obi_ma=signal_data.get('obi_ma', 0),
            cvd_ratio=signal_data.get('cvd_ratio', 0),
            obi_trend=signal_data.get('obi_trend', 'neutral'),
            entry_price=current_price,
            timestamp=signal_data.get('ts', datetime.now(timezone.utc).isoformat()),
            direction=direction
        )
        self.pending[id(record)] = record
        self.stats['total_signals'] += 1
        return id(record)

    def validate_signal(self, signal_id, current_price, current_time=None):
        """
        验证一笔信号的结果
        比较信号触发后的价格走势与预测方向
        """
        if signal_id not in self.pending:
            return None
        record = self.pending[signal_id]
        if current_time is None:
            current_time = time.time()

        # 计算盈亏百分比
        if record.direction == 'long':
            pnl = (current_price - record.entry_price) / record.entry_price
        else:
            pnl = (record.entry_price - current_price) / record.entry_price

        record.pnl_pct = pnl
        record.outcome = 'win' if pnl > 0 else 'loss'
        record.validation_time = current_time

        # 更新统计
        self.stats['validated'] += 1
        if record.outcome == 'win':
            self.stats['wins'] += 1
            self.stats['total_pnl'] += pnl
        else:
            self.stats['losses'] += 1
            self.stats['total_pnl'] += pnl

        # 移除pending
        del self.pending[signal_id]

        # 记录到历史
        self.records.append(record)
        self._update_accuracy_history()

        # 按置信度和OBI分组
        conf_bucket = round(record.confidence * 10) * 10  # 0, 10, 20...100
        obi_bucket = round(record.obi * 100) // 10 * 10   # -40, -30...40
        self.win_rate_by_confidence[conf_bucket].append(1 if record.outcome == 'win' else 0)
        self.win_rate_by_obi[obi_bucket].append(1 if record.outcome == 'win' else 0)

        return record.outcome, pnl

    def _update_accuracy_history(self):
        """更新滚动胜率历史"""
        if len(self.records) < 5:
            return
        recent = list(self.records)[-50:]  # 最近50笔
        wins = sum(1 for r in recent if r.outcome == 'win')
        self.accuracy_history.append({
            'time': datetime.now(timezone.utc).isoformat(),
            'rolling_win_rate': wins / len(recent),
            'total_win_rate': self.stats['wins'] / max(self.stats['validated'], 1)
        })

    def get_stats(self) -> dict:
        """获取统计摘要"""
        validated = self.stats['validated']
        if validated == 0:
            return {'validated': 0, 'pending': len(self.pending), 'total': self.stats['total_signals']}
        return {
            'total_signals': self.stats['total_signals'],
            'validated': validated,
            'pending': len(self.pending),
            'wins': self.stats['wins'],
            'losses': self.stats['losses'],
            'win_rate': self.stats['wins'] / validated,
            'total_pnl_pct': self.stats['total_pnl'],
            'avg_pnl_per_trade': self.stats['total_pnl'] / validated,
            'avg_win': sum(r.pnl_pct for r in self.records if r.outcome == 'win') / max(sum(1 for r in self.records if r.outcome == 'win'), 1),
            'avg_loss': sum(r.pnl_pct for r in self.records if r.outcome == 'loss') / max(sum(1 for r in self.records if r.outcome == 'loss'), 1),
        }

    def get_accuracy_by_confidence(self) -> dict:
        """按置信度分组查看胜率"""
        result = {}
        for conf, outcomes in sorted(self.win_rate_by_confidence.items()):
            wins = sum(outcomes)
            total = len(outcomes)
            if total >= 5:
                result[f'{conf}%'] = f'{wins/total:.1%} ({wins}/{total})'
        return result

    def get_dashboard(self) -> str:
        """获取仪表盘文本"""
        stats = self.get_stats()
        os.system('cls' if os.name == 'nt' else 'clear')
        print('=' * 70)
        print('  Micro-Apex Signal Validator — 信号准确率监控')
        print('=' * 70)
        if stats['validated'] == 0:
            print('  等待信号验证... (已产生 {} 个信号)'.format(stats['total_signals']))
        else:
            print(f'  总信号: {stats["total_signals"]} | 已验证: {stats["validated"]} | 待验证: {stats["pending"]}')
            print(f'  胜: {stats["wins"]} | 负: {stats["losses"]}')
            print(f'  >>> 胜率: {stats["win_rate"]:.1%}')
            print(f'  平均盈亏: {stats["avg_pnl_per_trade"]:+.3%}')
            print(f'  平均赢: {stats["avg_win"]:+.3%} | 平均输: {stats["avg_loss"]:+.3%}')
            print(f'  累计EV: {stats["total_pnl_pct"]:+.3%}')
            print('-' * 70)
            conf_stats = self.get_accuracy_by_confidence()
            if conf_stats:
                print('  按置信度分组的胜率:')
                for k, v in conf_stats.items():
                    print(f'    置信度{k}: {v}')
        print('=' * 70)
        return stats


def get_current_price():
    """获取当前BTCUSDT价格"""
    try:
        r = requests.get(f'{API_BASE}/ticker/price', params={'symbol': SYMBOL}, timeout=5)
        if r.status_code == 200:
            return float(r.json()['price'])
    except:
        pass
    return None


def get_kline_data(symbol=SYMBOL, interval='1m', limit=5):
    """获取K线数据"""
    try:
        r = requests.get(f'{API_BASE}/klines', params={'symbol': symbol, 'interval': interval, 'limit': limit}, timeout=5)
        if r.status_code == 200:
            return [float(k[4]) for k in r.json()]  # 返回close prices
    except:
        pass
    return []


async def run_validator(system, validation_window_seconds=300):
    """
    运行信号验证循环
    每 validation_window_seconds 秒检查待验证信号的结果
    """
    print(f'Signal Validator starting... (validation window: {validation_window_seconds}s)')
    last_validation = 0
    last_dash = 0

    while True:
        now = time.time()

        # 定期验证待验证信号
        if now - last_validation >= validation_window_seconds / 2:
            for signal_id, record in list(system.validator.pending.items()):
                current_price = get_current_price()
                if current_price:
                    system.validator.validate_signal(signal_id, current_price, now)
            last_validation = now

        # 定期刷新仪表盘
        if now - last_dash >= 10:
            system.validator.get_dashboard()
            last_dash = now

        await __import__('asyncio').sleep(5)


if __name__ == '__main__':
    import asyncio
    from micro_apex import MicroApexSystem

    system = MicroApexSystem()
    system.validator = SignalValidator()

    async def main_loop():
        # 模拟运行
        while True:
            # 获取价格
            price = get_current_price()
            if price:
                # 模拟记录一个信号(测试用)
                signal_data = {'type': 'LONG_BREAKOUT', 'confidence': 0.8, 'obi': 0.5,
                               'obi_ma': 0.4, 'cvd_ratio': 0.7, 'obi_trend': 'strengthening_buy',
                               'ts': datetime.now(timezone.utc).isoformat()}
                system.validator.record_signal(signal_data, price)

            await asyncio.sleep(30)

    asyncio.run(main_loop())
