# -*- coding: utf-8 -*-
"""
================================================================================
V7.0.8 智能交易系统 - 基于统计学分析的黄金策略
================================================================================

核心升级：
1. 开仓策略：基于6个月统计学分析的好机会识别
   - SHORT: 张力>0.5, 量能0.5-1.0, 张力/加速度比50-150, 等待4-6周期
   - LONG: 张力<-0.5, 张力/加速度比≥100, 等待4-6周期

2. 平仓策略：基于最优平仓点分析
   - SHORT: 量能>1.0 OR 周期≥5, 张力下降14% OR 盈亏>2%
   - LONG: 量能>1.0 OR 周期≥7, 张力不再增加 OR 盈亏>2%

3. 三级通知系统：
   - 原始信号通知（首次信号）
   - 黄金开仓通知（好机会确认）
   - 黄金平仓通知（最优平仓）

4. 保留V7.0.7功能：
   - ZigZag动态止盈止损（作为固定止损提醒）
   - Telegram交互功能
   - 状态管理

回测表现（2025年6-12月）：
- SHORT好机会率: 67.5%
- LONG好机会率: 86.1%
- 平均最优平仓: SHORT +1.20%, LONG +1.35%

================================================================================
"""

import numpy as np
import pandas as pd
import warnings
import json
import os
import requests
import time
import schedule
from datetime import datetime, timedelta
from scipy.signal import hilbert
from scipy.fft import fft, ifft
import logging
from collections import deque

warnings.filterwarnings('ignore')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('v708_trader.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 尝试加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv未安装，将使用默认配置")


# ==================== [1. 配置类] ====================
class V708TraderConfig:
    """V7.0.8交易系统配置"""

    def __init__(self):
        # ========== V7.0.8 好机会识别参数 ==========
        # SHORT信号黄金标准
        self.SHORT_TENSION_MIN = 0.5
        self.SHORT_TENSION_DIRECT = 0.8  # 张力≥0.8可直接开仓
        self.SHORT_ENERGY_IDEAL_MIN = 0.5
        self.SHORT_ENERGY_IDEAL_MAX = 1.0
        self.SHORT_RATIO_MIN = 50
        self.SHORT_RATIO_MAX = 150
        self.SHORT_WAIT_MIN = 4
        self.SHORT_WAIT_MAX = 6

        # LONG信号黄金标准
        self.LONG_TENSION_MAX = -0.5
        self.LONG_TENSION_STRONG = -0.7  # 张力<-0.7更优
        self.LONG_RATIO_MIN = 100
        self.LONG_WAIT_MIN = 4
        self.LONG_WAIT_MAX = 6

        # ========== V7.0.8 最优平仓参数 ==========
        # SHORT平仓条件
        self.SHORT_EXIT_ENERGY_EXPAND = 1.0
        self.SHORT_EXIT_MIN_PERIOD = 5
        self.SHORT_EXIT_MAX_PERIOD = 10
        self.SHORT_EXIT_TENSION_DROP = 0.14  # 14%
        self.SHORT_EXIT_PROFIT_TARGET = 0.02  # 2%

        # LONG平仓条件
        self.LONG_EXIT_ENERGY_EXPAND = 1.0
        self.LONG_EXIT_MIN_PERIOD = 7
        self.LONG_EXIT_MAX_PERIOD = 10
        self.LONG_EXIT_PROFIT_TARGET = 0.02  # 2%

        # ========== V7.0.7 固定止盈止损（保留） ==========
        self.FALLBACK_TP = 0.05  # +5%
        self.FALLBACK_SL = -0.025  # -2.5%
        self.MAX_HOLD_PERIODS = 42  # 7天（42个4H周期）

        # ========== 信号计算参数 ==========
        self.CONF_THRESHOLD = 0.6
        self.TENSION_THRESHOLD = 0.35
        self.ACCEL_THRESHOLD = 0.02
        self.OSCILLATION_BAND = 0.5

        # ========== 仓位管理 ==========
        self.BASE_POSITION_SIZE = 0.50
        self.LEVERAGE = 1

        # ========== API配置 ==========
        self.binance_symbol = "BTCUSDT"
        self.timeframe_4h = "4h"
        self.timeframe_1h = "1h"

        # Telegram配置
        self.telegram_token = os.getenv('TELEGRAM_TOKEN', '8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '838429342')
        self.telegram_enabled = os.getenv('TELEGRAM_ENABLED', 'True').lower() == 'true'

        # ========== 运行频率 ==========
        self.check_interval_hours = 4  # 每4小时检查一次


# ==================== [2. 数据管理器] ====================
class DataFetcher:
    """数据获取器"""

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()

    def fetch_btc_data(self, interval='4h', limit=300):
        """获取BTC K线数据（返回北京时间）"""
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {
                'symbol': self.config.binance_symbol,
                'interval': interval,
                'limit': limit
            }

            resp = self.session.get(url, params=params, timeout=15)
            data = resp.json()

            if not data:
                return None

            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            # 转换为北京时间（UTC+8）
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=8)
            df.set_index('timestamp', inplace=True)

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            return df

        except Exception as e:
            logger.error(f"获取BTC数据失败: {e}")
            return None


# ==================== [3. 物理信号计算器] ====================
class PhysicsSignalCalculator:
    """物理信号计算器 - 继承v4.2数学家策略的核心算法"""

    def __init__(self, config):
        self.config = config

    def calculate_physics_metrics(self, df):
        """计算物理指标：张力、加速度、量能比"""
        if len(df) < 60:
            return None

        try:
            prices = df['close'].values

            from scipy.signal import detrend
            d_prices = detrend(prices)

            coeffs = fft(d_prices)
            coeffs[8:] = 0
            filtered = ifft(coeffs).real

            analytic = hilbert(filtered)
            tension = np.imag(analytic)

            if len(tension) > 1 and np.std(tension) > 0:
                tension_normalized = (tension - np.mean(tension)) / np.std(tension)
            else:
                tension_normalized = tension

            # 计算加速度
            acceleration = np.zeros_like(tension_normalized)
            for i in range(2, len(tension_normalized)):
                current_tension = tension_normalized[i]
                prev_tension = tension_normalized[i-1]
                prev2_tension = tension_normalized[i-2]

                velocity = current_tension - prev_tension
                acceleration[i] = velocity - (prev_tension - prev2_tension)

            # 计算量能比率
            avg_volume = np.mean(df['volume'].values[-20:])
            current_volume = df['volume'].values[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            result = pd.DataFrame({
                'tension': tension_normalized,
                'acceleration': acceleration,
                'volume_ratio': [volume_ratio] * len(tension_normalized),
                'close': df['close'].values,
                'high': df['high'].values,
                'low': df['low'].values,
                'volume': df['volume'].values
            }, index=df.index)

            return result

        except Exception as e:
            logger.error(f"物理指标计算失败: {e}")
            return None

    def diagnose_regime(self, tension, acceleration, volume_ratio):
        """诊断市场状态并生成信号"""
        confidence = 0.0
        signal_type = None
        description = "无信号"

        if tension > self.config.TENSION_THRESHOLD and acceleration < -self.config.ACCEL_THRESHOLD:
            confidence = 0.7
            description = f"奇点看空(T={tension:.2f}≥{self.config.TENSION_THRESHOLD})"
            signal_type = 'BEARISH_SINGULARITY'

        elif tension < -self.config.TENSION_THRESHOLD and acceleration > self.config.ACCEL_THRESHOLD:
            confidence = 0.6
            description = f"奇点看涨(T={tension:.2f}≤-{self.config.TENSION_THRESHOLD})"
            signal_type = 'BULLISH_SINGULARITY'

        elif abs(tension) < self.config.OSCILLATION_BAND and abs(acceleration) < self.config.ACCEL_THRESHOLD:
            confidence = 0.8
            signal_type = 'OSCILLATION'
            description = f"系统平衡震荡(|T|={abs(tension):.2f}<{self.config.OSCILLATION_BAND})"

        elif tension > 0.3 and abs(acceleration) < 0.01:
            confidence = 0.6
            signal_type = 'HIGH_OSCILLATION'
            description = f"高位震荡(T={tension:.2f}>0.3)"

        elif tension < -0.3 and abs(acceleration) < 0.01:
            confidence = 0.6
            signal_type = 'LOW_OSCILLATION'
            description = f"低位震荡(T={tension:.2f}<-0.3)"

        if confidence < self.config.CONF_THRESHOLD:
            return None, 0.0, "置信度不足"

        return signal_type, confidence, description


# ==================== [4. V7.0.8 好机会识别器] ====================
class V708GoldenOpportunityDetector:
    """V7.0.8好机会识别器 - 基于统计学分析"""

    def __init__(self, config):
        self.config = config
        self.pending_signals = {}  # 待确认的信号
        self.waiting_periods = {}   # 记录等待周期

    def check_first_signal(self, signal_type, tension, acceleration, volume_ratio, timestamp, price):
        """
        检查首次信号

        返回: (is_first_signal, direction, reason)
        """
        is_short = (
            tension > self.config.SHORT_TENSION_MIN and
            acceleration < 0
        )

        is_long = (
            tension < self.config.LONG_TENSION_MAX and
            acceleration > 0
        )

        if is_short:
            # 计算张力/加速度比
            ratio = tension / abs(acceleration) if acceleration != 0 else 0

            # 判断是否直接开仓
            can_direct_enter = (
                tension >= self.config.SHORT_TENSION_DIRECT and
                self.config.SHORT_ENERGY_IDEAL_MIN <= volume_ratio <= self.config.SHORT_ENERGY_IDEAL_MAX and
                self.config.SHORT_RATIO_MIN <= ratio <= self.config.SHORT_RATIO_MAX
            )

            if can_direct_enter:
                return True, 'short', f"直接开仓信号: T={tension:.4f}, E={volume_ratio:.2f}, 比例={ratio:.1f}"
            else:
                # 记录为待确认信号
                self.pending_signals[timestamp] = {
                    'direction': 'short',
                    'tension': tension,
                    'acceleration': acceleration,
                    'volume_ratio': volume_ratio,
                    'price': price,
                    'timestamp': timestamp
                }
                self.waiting_periods[timestamp] = 0
                return True, 'short_wait', f"等待确认: T={tension:.4f}, 需等待4-6周期"

        elif is_long:
            # 计算张力/加速度比
            ratio = abs(tension) / acceleration if acceleration != 0 else 0

            # 判断是否可以直接开仓
            can_direct_enter = (
                tension <= self.config.LONG_TENSION_STRONG and
                ratio >= self.config.LONG_RATIO_MIN
            )

            if can_direct_enter:
                return True, 'long', f"直接开仓信号: T={tension:.4f}, 比例={ratio:.1f}"
            else:
                # 记录为待确认信号
                self.pending_signals[timestamp] = {
                    'direction': 'long',
                    'tension': tension,
                    'acceleration': acceleration,
                    'volume_ratio': volume_ratio,
                    'price': price,
                    'timestamp': timestamp
                }
                self.waiting_periods[timestamp] = 0
                return True, 'long_wait', f"等待确认: T={tension:.4f}, 需等待4-6周期"

        return False, None, None

    def check_golden_entry(self, current_tension, current_accel, current_volume, current_price, current_time):
        """
        检查是否达到黄金开仓条件

        返回: (is_golden, direction, entry_info)
        """
        confirmed_signals = []

        # 检查所有待确认信号
        for timestamp, signal in list(self.pending_signals.items()):
            # 增加等待周期
            self.waiting_periods[timestamp] += 1
            wait_period = self.waiting_periods[timestamp]

            direction = signal['direction']
            orig_tension = signal['tension']
            orig_accel = signal['acceleration']

            if direction == 'short':
                # SHORT信号确认条件
                ratio = current_tension / abs(current_accel) if current_accel != 0 else 0

                is_confirmed = (
                    current_tension > 0.45 and
                    current_accel < 0 and
                    current_volume < 1.0 and
                    self.config.SHORT_WAIT_MIN <= wait_period <= self.config.SHORT_WAIT_MAX
                )

                if is_confirmed:
                    tension_change = (current_tension - orig_tension) / orig_tension * 100
                    price_advantage = (signal['price'] - current_price) / signal['price'] * 100

                    is_golden = (
                        tension_change > 5 or  # 张力上升>5%
                        price_advantage > 0.5     # 价格优势>0.5%
                    )

                    entry_info = {
                        'direction': 'short',
                        'entry_price': current_price,
                        'entry_tension': current_tension,
                        'entry_accel': current_accel,
                        'entry_volume': current_volume,
                        'wait_period': wait_period,
                        'tension_change': tension_change,
                        'price_advantage': price_advantage,
                        'is_golden': is_golden,
                        'original_time': timestamp,
                        'entry_time': current_time
                    }

                    confirmed_signals.append(entry_info)

                    # 移除已确认的信号
                    del self.pending_signals[timestamp]
                    del self.waiting_periods[timestamp]

            elif direction == 'long':
                # LONG信号确认条件
                ratio = abs(current_tension) / current_accel if current_accel != 0 else 0

                is_confirmed = (
                    current_tension < -0.45 and
                    current_accel > 0 and
                    current_volume < 1.0 and
                    self.config.LONG_WAIT_MIN <= wait_period <= self.config.LONG_WAIT_MAX
                )

                if is_confirmed:
                    tension_change = abs((current_tension - orig_tension) / orig_tension * 100)
                    price_advantage = (current_price - signal['price']) / signal['price'] * 100

                    is_golden = (
                        tension_change > 5 or  # 张力上升>5%
                        price_advantage > 0.5 or  # 价格优势>0.5%
                        ratio >= 100             # 张力/加速度比≥100
                    )

                    entry_info = {
                        'direction': 'long',
                        'entry_price': current_price,
                        'entry_tension': current_tension,
                        'entry_accel': current_accel,
                        'entry_volume': current_volume,
                        'wait_period': wait_period,
                        'tension_change': tension_change,
                        'price_advantage': price_advantage,
                        'is_golden': is_golden,
                        'original_time': timestamp,
                        'entry_time': current_time
                    }

                    confirmed_signals.append(entry_info)

                    # 移除已确认的信号
                    del self.pending_signals[timestamp]
                    del self.waiting_periods[timestamp]

            # 清理超过最大等待周期的信号
            if wait_period > 10:
                del self.pending_signals[timestamp]
                del self.waiting_periods[timestamp]

        return confirmed_signals

    def check_golden_exit(self, position, current_metrics, current_price):
        """
        检查是否达到黄金平仓条件

        返回: (should_exit, exit_reason, exit_type)
        exit_type: 'golden' (最优平仓) or 'fallback' (固定止损)
        """
        direction = position['direction']
        entry_price = position['entry_price']
        entry_tension = position['entry_tension']
        entry_time = position['entry_time']
        hold_periods = position.get('hold_periods', 0)

        current_tension = current_metrics['tension']
        current_accel = current_metrics['acceleration']
        current_volume = current_metrics['volume_ratio']

        # 计算当前盈亏
        if direction == 'short':
            pnl = (entry_price - current_price) / entry_price * 100
        else:
            pnl = (current_price - entry_price) / entry_price * 100

        # 检查固定止损
        if pnl <= self.config.FALLBACK_SL * 100:
            return True, f"固定止损({pnl:.2f}%)", 'fallback'
        if pnl >= self.config.FALLBACK_TP * 100:
            return True, f"固定止盈({pnl:.2f}%)", 'fallback'

        # 检查黄金平仓条件
        if direction == 'short':
            # SHORT黄金平仓条件
            tension_change = (current_tension - entry_tension) / entry_tension * 100

            should_exit = (
                (current_volume > self.config.SHORT_EXIT_ENERGY_EXPAND) or  # 量能放大
                (hold_periods >= self.config.SHORT_EXIT_MIN)                 # 或等待5周期
            ) and (
                (tension_change <= -self.config.SHORT_EXIT_TENSION_DROP * 100) or  # 张力下降14%
                (pnl >= self.config.SHORT_EXIT_PROFIT_TARGET * 100)            # 或盈利>2%
            )

            if should_exit:
                reasons = []
                if current_volume > self.config.SHORT_EXIT_ENERGY_EXPAND:
                    reasons.append(f"量能放大({current_volume:.2f})")
                if hold_periods >= self.config.SHORT_EXIT_MIN:
                    reasons.append(f"持仓{hold_periods}周期")
                if tension_change <= -self.config.SHORT_EXIT_TENSION_DROP * 100:
                    reasons.append(f"张力下降{abs(tension_change):.1f}%")
                if pnl >= self.config.SHORT_EXIT_PROFIT_TARGET * 100:
                    reasons.append(f"盈利{pnl:.2f}%")

                return True, f"黄金平仓: {', '.join(reasons)}", 'golden'

            # 强制平仓（超过最大周期）
            if hold_periods >= self.config.SHORT_EXIT_MAX_PERIOD:
                return True, f"强制平仓: 持仓{hold_periods}周期", 'golden'

        else:  # long
            # LONG黄金平仓条件
            tension_change = (current_tension - entry_tension) / entry_tension * 100

            should_exit = (
                (current_volume > self.config.LONG_EXIT_ENERGY_EXPAND) or  # 量能放大
                (hold_periods >= self.config.LONG_EXIT_MIN)                 # 或等待7周期
            ) and (
                (tension_change > 0) or                                    # 张力不再增加
                (pnl >= self.config.LONG_EXIT_PROFIT_TARGET * 100)         # 或盈利>2%
            )

            if should_exit:
                reasons = []
                if current_volume > self.config.LONG_EXIT_ENERGY_EXPAND:
                    reasons.append(f"量能放大({current_volume:.2f})")
                if hold_periods >= self.config.LONG_EXIT_MIN:
                    reasons.append(f"持仓{hold_periods}周期")
                if tension_change > 0:
                    reasons.append(f"张力不再增加")
                if pnl >= self.config.LONG_EXIT_PROFIT_TARGET * 100:
                    reasons.append(f"盈利{pnl:.2f}%")

                return True, f"黄金平仓: {', '.join(reasons)}", 'golden'

            # 强制平仓（超过最大周期）
            if hold_periods >= self.config.LONG_EXIT_MAX_PERIOD:
                return True, f"强制平仓: 持仓{hold_periods}周期", 'golden'

        return False, "持仓中", None


# ==================== [5. Telegram通知器] ====================
class TelegramNotifier:
    """Telegram通知器 - 三级通知系统"""

    def __init__(self, config):
        self.config = config

    def send_message(self, message, priority='normal'):
        """发送Telegram消息"""
        if not self.config.telegram_enabled:
            return

        try:
            url = f"https://api.telegram.org/bot{self.config.telegram_token}/sendMessage"
            data = {
                'chat_id': self.config.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }

            resp = requests.post(url, json=data, timeout=10)
            if resp.status_code != 200:
                logger.error(f"Telegram发送失败: {resp.text}")

        except Exception as e:
            logger.error(f"Telegram通知异常: {e}")

    def notify_first_signal(self, signal_type, tension, acceleration, volume_ratio, price, timestamp, direction):
        """通知1: 原始信号通知"""
        emoji = "🔴" if direction == 'short' else "🟢"
        direction_cn = "做空SHORT" if direction == 'short' else "做多LONG"

        # 计算张力/加速度比
        ratio = abs(tension / acceleration) if acceleration != 0 else 0

        message = f"""
{emoji} 【原始信号】{direction_cn}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ 时间: {timestamp}
💰 价格: ${price:.2f}
📊 张力: {tension:.4f}
📈 加速度: {acceleration:.6f}
⚡ 量能: {volume_ratio:.2f}
📐 张力/加速度比: {ratio:.1f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
等待确认中...
"""

        self.send_message(message, priority='normal')

    def notify_golden_entry(self, entry_info):
        """通知2: 黄金开仓通知"""
        direction = entry_info['direction']
        is_golden = entry_info['is_golden']

        if direction == 'short':
            emoji = "🔴" if is_golden else "⚪"
            direction_cn = "做空SHORT"
            emoji_level = "✨✨✨" if is_golden else "✨"
        else:
            emoji = "🟢" if is_golden else "⚪"
            direction_cn = "做多LONG"
            emoji_level = "✨✨✨" if is_golden else "✨"

        entry_price = entry_info['entry_price']
        entry_tension = entry_info['entry_tension']
        wait_period = entry_info['wait_period']
        tension_change = entry_info['tension_change']
        price_advantage = entry_info['price_advantage']

        # 计算固定止盈止损
        if direction == 'short':
            tp_price = entry_price * (1 - self.config.FALLBACK_TP)
            sl_price = entry_price * (1 - self.config.FALLBACK_SL)
        else:
            tp_price = entry_price * (1 + self.config.FALLBACK_TP)
            sl_price = entry_price * (1 + self.config.FALLBACK_SL)

        message = f"""
{emoji_level} 【黄金开仓】{direction_cn}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ 入场时间: {entry_info['entry_time']}
💰 入场价格: ${entry_price:.2f}
📊 张力: {entry_tension:.4f}
⏳ 等待周期: {wait_period}
📈 张力变化: {tension_change:+.2f}%
💎 价格优势: {price_advantage:+.2f}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【固定止盈止损】
🎯 止盈: ${tp_price:.2f} (+{self.config.FALLBACK_TP*100:.1f}%)
🛡️ 止损: ${sl_price:.2f} ({self.config.FALLBACK_SL*100:.1f}%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{emoji} {'黄金机会！' if is_golden else '普通机会'}
"""

        self.send_message(message, priority='high' if is_golden else 'normal')

    def notify_golden_exit(self, position, exit_reason, exit_price, pnl, exit_type):
        """通知3: 黄金平仓通知"""
        direction = position['direction']
        entry_price = position['entry_price']
        entry_time = position['entry_time']

        if direction == 'short':
            emoji = "🔴"
            direction_cn = "做空SHORT"
        else:
            emoji = "🟢"
            direction_cn = "做多LONG"

        exit_emoji = "✨" if exit_type == 'golden' else "⚠️"

        message = f"""
{exit_emoji} 【黄金平仓】{direction_cn}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ 入场时间: {entry_time}
💰 入场价格: ${entry_price:.2f}
⏰ 平仓时间: {position.get('exit_time', 'N/A')}
💰 平仓价格: ${exit_price:.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 盈亏: {pnl:+.2f}%
📝 原因: {exit_reason}
🏷️ 类型: {'黄金平仓' if exit_type == 'golden' else '固定止损'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        self.send_message(message, priority='high' if exit_type == 'golden' else 'normal')


# 主程序继续在下一部分...
