# -*- coding: utf-8 -*-
"""
================================================================================
V7.0.7 智能交易系统 - 实盘版本
================================================================================
基于V7.0.5过滤器 + V7.0.7 ZigZag动态止盈止损

核心特性：
- 信号计算：继承v4.2数学家策略的FFT+Hilbert物理计算
- 入场过滤：V7.0.5过滤器（量能、EMA、趋势）
- 出场策略：V7.0.7 ZigZag动态止盈止损（1H K线转折点）
- 交互功能：Telegram通知和命令
- 状态管理：持久化存储

回测表现（12月-1月）：+90.55%收益，60.4%胜率，完美过滤1月13-14日错误信号

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
        logging.FileHandler('v707_trader.log', encoding='utf-8'),
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
class V707TraderConfig:
    """V7.0.7交易系统配置"""

    def __init__(self):
        # ========== V7.0.5过滤器参数 ==========
        self.BULLISH_VOLUME_THRESHOLD = 0.95
        self.HIGH_OSC_EMA_THRESHOLD = 0.02
        self.HIGH_OSC_VOLUME_THRESHOLD = 1.1
        self.BEARISH_EMA_THRESHOLD = -0.05

        # ========== V7.0.7 ZigZag出场参数 ==========
        self.ZIGZAG_DEPTH = 12
        self.ZIGZAG_DEVIATION = 5
        self.MAX_HOLD_PERIODS = 42  # 7天（42个4H周期）

        # 回退止盈止损
        self.FALLBACK_TP = 0.05  # +5%
        self.FALLBACK_SL = -0.025  # -2.5%

        # ========== 信号计算参数 ==========
        self.CONF_THRESHOLD = 0.6
        self.USE_DXY_FUEL = False

        # ========== 仓位管理 ==========
        self.BASE_POSITION_SIZE = 0.50
        self.LEVERAGE = 1

        # ========== API配置 ==========
        self.binance_symbol = "BTCUSDT"
        self.timeframe_4h = "4h"
        self.timeframe_1h = "1h"

        # 代理配置（云端部署不需要代理）
        self.proxy_enabled = False
        self.proxy_host = None
        self.proxy_port = None
        self.proxy_http = None
        self.proxy_https = None

        # Telegram配置 ⭐ 已更新为V4.4专用token
        self.telegram_token = os.getenv('TELEGRAM_TOKEN', '8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '838429342')
        self.telegram_enabled = os.getenv('TELEGRAM_ENABLED', 'True').lower() == 'true'

        # ========== 运行频率 ==========
        self.signal_check_interval = 240      # 4小时检查信号
        self.position_check_interval = 60     # 1小时检查仓位

        # ========== 系统状态 ==========
        self.has_position = False
        self.position_type = None
        self.entry_price = None
        self.entry_time = None
        self.entry_index = 0
        self.position_size = 0.0
        self.entry_signal_type = None
        self.entry_confidence = 0.0

        # V7.0.7 ZigZag出场状态
        self.take_profit_price = None
        self.stop_loss_price = None
        self.df_1h_klines = None  # 1H K线数据缓存

        # 最新信号
        self.last_signal_time = None
        self.last_signal_type = None
        self.last_signal_desc = ""
        self.last_signal_price = 0.0
        self.last_signal_confidence = 0.0

        # 信号历史
        self.signal_history = []
        self.position_history = []

        # 统计数据
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0

    def save_state(self, filepath='v707_trader_state.json'):
        """保存系统状态"""
        state = {
            'has_position': self.has_position,
            'position_type': self.position_type,
            'entry_price': self.entry_price,
            'entry_time': str(self.entry_time) if self.entry_time else None,
            'entry_index': self.entry_index,
            'position_size': self.position_size,
            'entry_signal_type': self.entry_signal_type,
            'entry_confidence': self.entry_confidence,
            'take_profit_price': self.take_profit_price,
            'stop_loss_price': self.stop_loss_price,
            'last_signal_time': str(self.last_signal_time) if self.last_signal_time else None,
            'last_signal_type': self.last_signal_type,
            'last_signal_desc': self.last_signal_desc,
            'last_signal_price': self.last_signal_price,
            'last_signal_confidence': self.last_signal_confidence,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_pnl': self.total_pnl
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info(f"[状态] 系统状态已保存")
        except Exception as e:
            logger.error(f"保存状态失败: {e}")

    def load_state(self, filepath='v707_trader_state.json'):
        """加载系统状态"""
        if not os.path.exists(filepath):
            logger.warning(f"[状态] 状态文件不存在: {filepath}")
            return False

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)

            self.has_position = state.get('has_position', False)
            self.position_type = state.get('position_type')
            self.entry_price = state.get('entry_price')
            self.entry_time = datetime.fromisoformat(state['entry_time']) if state.get('entry_time') else None
            self.entry_index = state.get('entry_index', 0)
            self.position_size = state.get('position_size', 0.0)
            self.entry_signal_type = state.get('entry_signal_type')
            self.entry_confidence = state.get('entry_confidence', 0.0)
            self.take_profit_price = state.get('take_profit_price')
            self.stop_loss_price = state.get('stop_loss_price')

            if state.get('last_signal_time'):
                self.last_signal_time = datetime.fromisoformat(state['last_signal_time'])
            self.last_signal_type = state.get('last_signal_type')
            self.last_signal_desc = state.get('last_signal_desc', '')
            self.last_signal_price = state.get('last_signal_price', 0.0)
            self.last_signal_confidence = state.get('last_signal_confidence', 0.0)

            self.total_trades = state.get('total_trades', 0)
            self.winning_trades = state.get('winning_trades', 0)
            self.losing_trades = state.get('losing_trades', 0)
            self.total_pnl = state.get('total_pnl', 0.0)

            logger.info(f"[状态] 系统状态已加载")
            return True
        except Exception as e:
            logger.error(f"加载状态失败: {e}")
            return False


# ==================== [2. 数据管理器] ====================
class DataFetcher:
    """数据获取器"""

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()

    def fetch_btc_data(self, interval='4h', limit=300):
        """获取BTC K线数据"""
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

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
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
        """计算物理指标：张力、加速度、置信度"""
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

            acceleration = np.zeros_like(tension_normalized)
            for i in range(2, len(tension_normalized)):
                current_tension = tension_normalized[i]
                prev_tension = tension_normalized[i-1]
                prev2_tension = tension_normalized[i-2]

                velocity = current_tension - prev_tension
                acceleration[i] = velocity - (prev_tension - prev2_tension)

            result = pd.DataFrame({
                'tension': tension_normalized,
                'acceleration': acceleration,
                'close': df['close'].values,
                'high': df['high'].values,
                'low': df['low'].values,
                'volume': df['volume'].values
            }, index=df.index)

            return result

        except Exception as e:
            logger.error(f"物理指标计算失败: {e}")
            return None

    def diagnose_regime(self, tension, acceleration):
        """诊断市场状态并生成信号"""
        confidence = 0.0
        signal_type = None
        description = "无信号"

        TENSION_THRESHOLD = 0.35
        ACCEL_THRESHOLD = 0.02
        OSCILLATION_BAND = 0.5

        if tension > TENSION_THRESHOLD and acceleration < -ACCEL_THRESHOLD:
            confidence = 0.7
            description = f"奇点看空(T={tension:.2f}≥{TENSION_THRESHOLD})"
            signal_type = 'BEARISH_SINGULARITY'

        elif tension < -TENSION_THRESHOLD and acceleration > ACCEL_THRESHOLD:
            confidence = 0.6
            description = f"奇点看涨(T={tension:.2f}≤-{TENSION_THRESHOLD})"
            signal_type = 'BULLISH_SINGULARITY'

        elif abs(tension) < OSCILLATION_BAND and abs(acceleration) < ACCEL_THRESHOLD:
            confidence = 0.8
            signal_type = 'OSCILLATION'
            description = f"系统平衡震荡(|T|={abs(tension):.2f}<{OSCILLATION_BAND})"

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


# ==================== [4. V7.0.5 入场过滤器] ====================
class V705EntryFilter:
    """V7.0.5入场过滤器"""

    def __init__(self, config):
        self.config = config

    def calculate_ema(self, prices, period=20):
        """计算EMA"""
        if len(prices) < period:
            return prices[-1]
        return pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1]

    def apply_filter(self, signal_type, acceleration, volume_ratio, price_vs_ema, df_metrics):
        """
        V7.0.5过滤器

        返回: (should_pass, reason)
        """
        if signal_type == 'HIGH_OSCILLATION':
            if price_vs_ema > self.config.HIGH_OSC_EMA_THRESHOLD:
                return False, f"牛市回调(价格>EMA {price_vs_ema*100:.1f}%)"

            if acceleration >= 0:
                return False, f"无向下动能(a={acceleration:.3f})"

            if volume_ratio > self.config.HIGH_OSC_VOLUME_THRESHOLD:
                return False, f"高位放量({volume_ratio:.2f})"

            return True, "通过V7.0.5"

        elif signal_type == 'LOW_OSCILLATION':
            return True, "通过V7.0.5"

        elif signal_type == 'BULLISH_SINGULARITY':
            if volume_ratio > self.config.BULLISH_VOLUME_THRESHOLD:
                return False, f"量能放大({volume_ratio:.2f})"

            if price_vs_ema > 0.05:
                return False, f"主升浪(偏离{price_vs_ema*100:.1f}%)"

            return True, "通过V7.0.5"

        elif signal_type == 'BEARISH_SINGULARITY':
            if price_vs_ema < self.config.BEARISH_EMA_THRESHOLD:
                return False, f"主跌浪(偏离{price_vs_ema*100:.1f}%)"

            return True, "通过V7.0.5"

        return True, "通过V7.0.5"


# ==================== [5. V7.0.7 ZigZag出场管理器] ====================
class V707ZigZagExitManager:
    """V7.0.7 ZigZag动态止盈止损管理器"""

    def __init__(self, config):
        self.config = config

    def detect_zigzag(self, df):
        """检测ZigZag转折点"""
        pivots = []
        highs = df['high'].values
        lows = df['low'].values

        for i in range(self.config.ZIGZAG_DEPTH, len(df) - self.config.ZIGZAG_DEPTH):
            is_high = True
            for j in range(1, self.config.ZIGZAG_DEPTH + 1):
                if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                    is_high = False
                    break

            if is_high:
                pivots.append({
                    'index': i,
                    'price': highs[i],
                    'type': 'peak'
                })
                continue

            is_low = True
            for j in range(1, self.config.ZIGZAG_DEPTH + 1):
                if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                    is_low = False
                    break

            if is_low:
                pivots.append({
                    'index': i,
                    'price': lows[i],
                    'type': 'valley'
                })

        return pivots

    def calculate_tp_sl(self, df, entry_price, direction):
        """
        计算止盈止损

        返回: (take_profit_price, stop_loss_price)
        """
        pivots = self.detect_zigzag(df)

        if len(pivots) == 0:
            if direction == 'long':
                return entry_price * (1 + self.config.FALLBACK_TP), entry_price * (1 + self.config.FALLBACK_SL)
            else:
                return entry_price * (1 - self.config.FALLBACK_TP), entry_price * (1 - self.config.FALLBACK_SL)

        valleys = [p for p in pivots if p['type'] == 'valley']
        peaks = [p for p in pivots if p['type'] == 'peak']

        if direction == 'long':
            if len(valleys) > 0:
                recent_valley = None
                for valley in reversed(valleys):
                    if valley['price'] < entry_price:
                        recent_valley = valley
                        break

                if recent_valley:
                    sl_distance = (entry_price - recent_valley['price']) * 1.2
                    stop_loss = entry_price - sl_distance
                else:
                    stop_loss = entry_price * (1 + self.config.FALLBACK_SL)
            else:
                stop_loss = entry_price * (1 + self.config.FALLBACK_SL)

            if len(peaks) > 0:
                recent_peak = None
                for peak in peaks:
                    if peak['price'] > entry_price:
                        recent_peak = peak
                        break

                if recent_peak:
                    tp_distance = (recent_peak['price'] - entry_price) * 1.2
                    take_profit = entry_price + tp_distance
                else:
                    take_profit = entry_price * (1 + self.config.FALLBACK_TP)
            else:
                take_profit = entry_price * (1 + self.config.FALLBACK_TP)

        else:
            if len(peaks) > 0:
                recent_peak = None
                for peak in reversed(peaks):
                    if peak['price'] > entry_price:
                        recent_peak = peak
                        break

                if recent_peak:
                    sl_distance = (recent_peak['price'] - entry_price) * 0.5
                    stop_loss = entry_price + sl_distance

                    if sl_distance / entry_price > 0.03:
                        stop_loss = entry_price * (1 - self.config.FALLBACK_SL)
                else:
                    stop_loss = entry_price * (1 - self.config.FALLBACK_SL)
            else:
                stop_loss = entry_price * (1 - self.config.FALLBACK_SL)

            if len(valleys) > 0:
                recent_valley = None
                for valley in valleys:
                    if valley['price'] < entry_price:
                        recent_valley = valley
                        break

                if recent_valley:
                    tp_distance = (entry_price - recent_valley['price']) * 1.2
                    take_profit = entry_price - tp_distance
                else:
                    take_profit = entry_price * (1 - self.config.FALLBACK_TP)
            else:
                take_profit = entry_price * (1 - self.config.FALLBACK_TP)

        return take_profit, stop_loss

    def check_exit(self, df, entry_price, direction):
        """
        检查出场条件

        返回: (should_exit, reason, exit_price)
        """
        take_profit, stop_loss = self.calculate_tp_sl(df, entry_price, direction)
        current_price = df.iloc[-1]['close']

        if direction == 'long':
            if current_price <= stop_loss:
                return True, f"ZigZag止损(${stop_loss:.2f})", stop_loss
            elif current_price >= take_profit:
                return True, f"ZigZag止盈(${take_profit:.2f})", take_profit
        else:
            if current_price >= stop_loss:
                return True, f"ZigZag止损(${stop_loss:.2f})", stop_loss
            elif current_price <= take_profit:
                return True, f"ZigZag止盈(${take_profit:.2f})", take_profit

        return False, "持仓中", None


# 主程序部分继续在下一条消息...


import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ==================== [Telegram通知模块] ====================
class TelegramNotifier:
    """Telegram通知和交互模块"""

    def __init__(self, config):
        self.config = config
        self.base_url = f"https://api.telegram.org/bot{config.telegram_token}"

    def send_message(self, message, parse_mode='Markdown'):
        """发送Telegram消息"""
        if not self.config.telegram_enabled:
            return

        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.config.telegram_chat_id,
                'text': message,
                'parse_mode': parse_mode
            }

            resp = requests.post(url, json=data, timeout=10)

            if resp.status_code == 200:
                logger.info(f"[Telegram] 消息已发送")
            else:
                logger.warning(f"[Telegram] 发送失败: HTTP {resp.status_code}")

        except Exception as e:
            logger.error(f"[Telegram] 发送消息异常: {e}")

    def notify_signal(self, signal_type, confidence, description, price, tension, acceleration):
        """通知新信号"""
        message = f"""
🎯 *V7.0.7新信号*

📊 *信号类型*: {signal_type}
📈 *置信度*: {confidence:.2f}
💡 *描述*: {description}
💰 *当前价格*: ${price:.2f}
📐 *张力*: {tension:.3f}
🚀 *加速度*: {acceleration:.3f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_message(message)

    def notify_entry(self, direction, price, signal_type, confidence, tp, sl):
        """通知开仓"""
        emoji = "📈" if direction == 'long' else "📉"
        message = f"""
{emoji} *V7.0.7开仓*

📍 *方向*: {direction.upper()}
💰 *入场价*: ${price:.2f}
🎯 *信号*: {signal_type}
📊 *置信度*: {confidence:.2f}
🎯 *止盈*: ${tp:.2f}
🛑 *止损*: ${sl:.2f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_message(message)

    def notify_exit(self, direction, entry_price, exit_price, pnl_pct, reason):
        """通知平仓"""
        emoji = "✅" if pnl_pct > 0 else "❌"
        message = f"""
{emoji} *V7.0.7平仓*

📍 *方向*: {direction.upper()}
💰 *入场*: ${entry_price:.2f}
💵 *出场*: ${exit_price:.2f}
📊 *盈亏*: {pnl_pct:+.2f}%
🎯 *原因*: {reason}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_message(message)

    def notify_status(self):
        """通知系统状态"""
        if self.config.has_position:
            hold_time = datetime.now() - self.config.entry_time
            message = f"""
📊 *V7.0.7持仓状态*

📍 *方向*: {self.config.position_type.upper()}
💰 *入场价*: ${self.config.entry_price:.2f}
🎯 *止盈*: ${self.config.take_profit_price:.2f}
🛑 *止损*: ${self.config.stop_loss_price:.2f}
⏱ *持仓时长*: {hold_time}
📊 *入场置信度*: {self.config.entry_confidence:.2f}

📈 *总交易*: {self.config.total_trades}
✅ *盈利*: {self.config.winning_trades}
❌ *亏损*: {self.config.losing_trades}
💵 *总盈亏*: {self.config.total_pnl:.2f}%
"""
        else:
            message = f"""
📊 *V7.0.7系统状态*

⭕ *当前状态*: 空仓
📈 *总交易*: {self.config.total_trades}
✅ *盈利*: {self.config.winning_trades}
❌ *亏损*: {self.config.losing_trades}
💵 *总盈亏*: {self.config.total_pnl:.2f}%

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_message(message)
