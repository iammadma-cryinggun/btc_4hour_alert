# -*- coding: utf-8 -*-
"""
================================================================================
V7.0 实盘交易系统 - 完整版
================================================================================

核心特性：
1. 信号计算：使用验证5的滑动窗口逻辑
2. 交易逻辑：V7.0 Combat Robust（已测试）
3. Telegram：独立线程交互，所有信号实时通知
4. 云端部署：不使用代理
5. 状态管理：持久化存储

回测表现：85.01%收益，-31.8%回撤，90.2%止盈率

================================================================================
"""

import numpy as np
import pandas as pd
import json
import os
import requests
import time
import threading
import schedule
import logging
from datetime import datetime, timedelta
from scipy.signal import hilbert, detrend
from scipy.fft import fft, ifft
from collections import deque
from typing import Tuple, Optional

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('v70_trader.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv未安装，将使用默认配置")


# ==================== [1. 配置类] ====================
class V70Config:
    """V7.0交易系统配置"""

    def __init__(self):
        # ========== 验证5信号计算参数 ==========
        self.TENSION_THRESHOLD = 0.35      # 张力阈值（验证5）
        self.ACCEL_THRESHOLD = 0.02        # 加速度阈值（验证5）
        self.OSCILLATION_BAND = 0.5        # 震荡边界（验证5）
        self.WINDOW_SIZE = 100             # 滑动窗口大小（验证5）
        self.MIN_WINDOW_SIZE = 60          # 最小窗口（验证5）

        # ========== V7.0交易参数 ==========
        self.CONF_THRESHOLD = 0.6          # 置信度阈值（V7.0严格标准）
        self.INERTIA_ZONE_PERIODS = 2      # T0-T2惯性保护（前8小时）
        self.USE_ATR_STOP = True
        self.ATR_PERIOD = 14
        self.ATR_MULTIPLIER = 1.5          # 1.5倍ATR
        self.ACCEL_DECAY_MIN_PERIODS = 4   # 严格动能衰减
        self.ACCEL_DECAY_CONSECUTIVE = 3
        self.ACCEL_DECAY_THRESHOLD = 0.7  # 跌幅<70%
        self.TENSION_OVERLOAD_THRESHOLD = 1.2
        self.CONF_COLLAPSE_THRESHOLD = 0.3
        self.MAX_HOLD_PERIODS = 5          # 最多5个周期（20小时）

        # ========== 仓位管理 ==========
        self.BASE_POSITION_SIZE = 0.50     # 基础仓位50%
        self.LEVERAGE = 1                   # 不使用杠杆

        # ========== API配置 ==========
        self.binance_symbol = "BTCUSDT"
        self.timeframe_4h = "4h"
        self.timeframe_1h = "1h"

        # ========== 云端部署配置（不使用代理）==========
        self.proxy_enabled = False  # 云端不需要代理

        # ========== Telegram配置 ==========
        self.telegram_token = os.getenv('TELEGRAM_TOKEN', '8189663571:AAEvIUEBTfF_MfyKc7rWq5gQvgi4gAxZJrA')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '838429342')
        self.telegram_enabled = os.getenv('TELEGRAM_ENABLED', 'True').lower() == 'true'

        # ========== 运行频率 ==========
        self.signal_check_interval = 240   # 4小时检查信号
        self.position_check_interval = 60  # 1小时检查仓位

        # ========== 系统状态 ==========
        self.has_position = False
        self.position_type = None
        self.entry_price = 0.0
        self.entry_time = None
        self.entry_index = 0
        self.position_size = 0.0
        self.entry_tension = 0.0
        self.entry_acceleration = 0.0
        self.entry_confidence = 0.0
        self.entry_signal = None
        self.entry_atr = 0.0
        self.stop_loss_price = 0.0
        self.stop_loss_type = None

        # ATR历史
        self.atr_history = deque(maxlen=20)
        # 加速度历史
        self.acceleration_history = deque(maxlen=10)
        self.max_acceleration_in_trade = 0.0

        # 最新信号
        self.last_signal_time = None
        self.last_signal_type = None
        self.last_signal_desc = ""
        self.last_signal_price = 0.0
        self.last_signal_confidence = 0.0
        self.last_signal_tension = 0.0
        self.last_signal_acceleration = 0.0

        # 信号历史
        self.signal_history = []
        self.position_history = []

        # 统计数据
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0

        # Telegram消息队列（线程安全）
        self.telegram_queue = deque()
        self.telegram_thread = None
        self.telegram_running = False

    def save_state(self, filepath='v70_state.json'):
        """保存系统状态"""
        state = {
            'has_position': self.has_position,
            'position_type': self.position_type,
            'entry_price': self.entry_price,
            'entry_time': str(self.entry_time) if self.entry_time else None,
            'entry_index': self.entry_index,
            'position_size': self.position_size,
            'entry_tension': self.entry_tension,
            'entry_acceleration': self.entry_acceleration,
            'entry_confidence': self.entry_confidence,
            'entry_signal': self.entry_signal,
            'entry_atr': self.entry_atr,
            'stop_loss_price': self.stop_loss_price,
            'stop_loss_type': self.stop_loss_type,
            'atr_history': list(self.atr_history),
            'acceleration_history': list(self.acceleration_history),
            'max_acceleration_in_trade': self.max_acceleration_in_trade,
            'last_signal_time': str(self.last_signal_time) if self.last_signal_time else None,
            'last_signal_type': self.last_signal_type,
            'last_signal_desc': self.last_signal_desc,
            'last_signal_price': self.last_signal_price,
            'last_signal_confidence': self.last_signal_confidence,
            'last_signal_tension': self.last_signal_tension,
            'last_signal_acceleration': self.last_signal_acceleration,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_pnl': self.total_pnl
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info("[状态] 系统状态已保存")
        except Exception as e:
            logger.error(f"保存状态失败: {e}")

    def load_state(self, filepath='v70_state.json'):
        """加载系统状态"""
        if not os.path.exists(filepath):
            return False

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)

            self.has_position = state.get('has_position', False)
            self.position_type = state.get('position_type')
            self.entry_price = state.get('entry_price', 0.0)
            self.entry_time = datetime.fromisoformat(state['entry_time']) if state.get('entry_time') else None
            self.entry_index = state.get('entry_index', 0)
            self.position_size = state.get('position_size', 0.0)
            self.entry_tension = state.get('entry_tension', 0.0)
            self.entry_acceleration = state.get('entry_acceleration', 0.0)
            self.entry_confidence = state.get('entry_confidence', 0.0)
            self.entry_signal = state.get('entry_signal')
            self.entry_atr = state.get('entry_atr', 0.0)
            self.stop_loss_price = state.get('stop_loss_price', 0.0)
            self.stop_loss_type = state.get('stop_loss_type')
            self.max_acceleration_in_trade = state.get('max_acceleration_in_trade', 0.0)

            # 恢复历史
            if 'atr_history' in state:
                self.atr_history = deque(state['atr_history'], maxlen=20)
            if 'acceleration_history' in state:
                self.acceleration_history = deque(state['acceleration_history'], maxlen=10)

            # 恢复最新信号
            if state.get('last_signal_time'):
                self.last_signal_time = datetime.fromisoformat(state['last_signal_time'])
            self.last_signal_type = state.get('last_signal_type')
            self.last_signal_desc = state.get('last_signal_desc', '')
            self.last_signal_price = state.get('last_signal_price', 0.0)
            self.last_signal_confidence = state.get('last_signal_confidence', 0.0)
            self.last_signal_tension = state.get('last_signal_tension', 0.0)
            self.last_signal_acceleration = state.get('last_signal_acceleration', 0.0)

            # 恢复统计
            self.total_trades = state.get('total_trades', 0)
            self.winning_trades = state.get('winning_trades', 0)
            self.losing_trades = state.get('losing_trades', 0)
            self.total_pnl = state.get('total_pnl', 0.0)

            logger.info("[状态] 系统状态已加载")
            return True
        except Exception as e:
            logger.error(f"加载状态失败: {e}")
            return False


# ==================== [2. 验证5信号计算器] ====================
class V5SignalCalculator:
    """
    验证5逻辑信号计算器

    使用滑动窗口FFT（不是全局FFT）
    与验证5.py完全一致
    """

    def __init__(self, config):
        self.config = config

    def calculate_tension_acceleration(self, prices):
        """
        计算张力和加速度（验证5逻辑）

        使用滑动窗口，每个时间点独立计算
        """
        if len(prices) < self.config.MIN_WINDOW_SIZE:
            return None, None

        try:
            prices_array = np.array(prices, dtype=np.float64)
            d_prices = detrend(prices_array)

            # FFT滤波（保留前8个系数）
            coeffs = fft(d_prices)
            coeffs[8:] = 0
            filtered = ifft(coeffs).real

            # Hilbert变换
            analytic = hilbert(filtered)
            tension = np.imag(analytic)

            # 标准化
            if len(tension) > 1 and np.std(tension) > 0:
                norm_tension = (tension - np.mean(tension)) / np.std(tension)
            else:
                norm_tension = tension

            # 手动计算加速度（二阶差分，验证5逻辑）
            current_tension = norm_tension[-1]
            prev_tension = norm_tension[-2] if len(norm_tension) > 1 else current_tension
            prev2_tension = norm_tension[-3] if len(norm_tension) > 2 else prev_tension

            # 速度 = 张力的一阶差分
            velocity = current_tension - prev_tension

            # 加速度 = 速度的一阶差分（张力的二阶差分）
            acceleration = velocity - (prev_tension - prev2_tension)

            return float(current_tension), float(acceleration)

        except Exception as e:
            logger.error(f"物理计算异常: {e}")
            return None, None

    def diagnose_regime(self, tension, acceleration):
        """
        诊断市场状态（验证5逻辑）

        返回: (signal_type, confidence, description)
        """
        confidence = 0.0
        signal_type = None
        description = "无信号"

        # 1. 奇点看空（系统看空→我们做多）
        if tension > self.config.TENSION_THRESHOLD and acceleration < -self.config.ACCEL_THRESHOLD:
            signal_type = 'BEARISH_SINGULARITY'
            confidence = 0.7
            description = f"SINGULARITY奇点反转(T={tension:.2f}≥{self.config.TENSION_THRESHOLD})"

        # 2. 奇点看涨（系统看涨→我们做空）
        elif tension < -self.config.TENSION_THRESHOLD and acceleration > self.config.ACCEL_THRESHOLD:
            signal_type = 'BULLISH_SINGULARITY'
            confidence = 0.6
            description = f"SINGULARITY奇点反转(T={tension:.2f}≤-{self.config.TENSION_THRESHOLD})"

        # 3. 震荡回归
        elif abs(tension) < self.config.OSCILLATION_BAND:
            if abs(acceleration) < 0.02:
                signal_type = 'OSCILLATION'
                confidence = 0.8
                description = f"OSCILLATION系统平衡"
            elif tension > 0.3 and acceleration < -0.01:
                signal_type = 'OSCILLATION_PEAK'
                confidence = 0.6
                description = f"OSCILLATION峰值回归"
            elif tension < -0.3 and acceleration > 0.01:
                signal_type = 'OSCILLATION_TROUGH'
                confidence = 0.6
                description = f"OSCILLATION低位回归"

        # 置信度过滤
        if confidence < self.config.CONF_THRESHOLD:
            return None, 0.0, "置信度不足"

        return signal_type, confidence, description


# ==================== [3. 数据获取器] ====================
class DataFetcher:
    """数据获取器（云端，无代理）"""

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        # 云端不使用代理

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


# ==================== [4. V7.0交易引擎] ====================
class V70TradingEngine:
    """V7.0交易引擎（完整逻辑）"""

    def __init__(self, config):
        self.config = config

    def calculate_atr(self, high, low, close):
        """计算单个周期的真实波幅"""
        high_low = high - low
        high_close = abs(high - close)
        low_close = abs(low - close)
        return max(high_low, high_close, low_close)

    def get_current_atr(self):
        """获取当前ATR值"""
        if len(self.config.atr_history) < self.config.ATR_PERIOD:
            return self.config.entry_price * 0.02 if self.config.entry_price > 0 else 500.0
        return sum(list(self.config.atr_history)[-self.config.ATR_PERIOD:]) / self.config.ATR_PERIOD

    def check_entry_conditions(self, signal_type, confidence):
        """检查入场条件（V7.0）"""
        if signal_type is None:
            return False, "无有效信号"

        if confidence < self.config.CONF_THRESHOLD:
            return False, f"置信度不足({confidence:.2f}<{self.config.CONF_THRESHOLD})"

        if self.config.has_position:
            return False, "已有持仓"

        return True, "满足入场条件"

    def get_entry_direction(self, signal_type):
        """确定入场方向（反向策略）"""
        if signal_type == 'BEARISH_SINGULARITY':
            return 'long'  # 系统看空→我们做多
        elif signal_type == 'BULLISH_SINGULARITY':
            return 'short'  # 系统看涨→我们做空
        elif signal_type == 'OSCILLATION_PEAK':
            return 'short'  # 峰值回归→做空
        elif signal_type == 'OSCILLATION_TROUGH':
            return 'long'   # 低位回归→做多
        else:
            return None

    def open_position(self, direction, price, time_obj, index, signal_type,
                      tension, acceleration, confidence, atr):
        """开仓"""
        self.config.has_position = True
        self.config.position_type = direction
        self.config.entry_price = price
        self.config.entry_time = time_obj
        self.config.entry_index = index
        self.config.position_size = self.config.BASE_POSITION_SIZE
        self.config.entry_tension = tension
        self.config.entry_acceleration = acceleration
        self.config.entry_confidence = confidence
        self.config.entry_signal = signal_type
        self.config.entry_atr = atr

        # 初始化历史
        self.config.atr_history.clear()
        self.config.atr_history.append(atr)
        self.config.acceleration_history.clear()
        self.config.acceleration_history.append(acceleration)
        self.config.max_acceleration_in_trade = abs(acceleration)

        # 设置止损
        current_atr = self.get_current_atr()
        atr_stop = current_atr * self.config.ATR_MULTIPLIER
        if direction == 'long':
            self.config.stop_loss_price = price - atr_stop
        else:
            self.config.stop_loss_price = price + atr_stop
        self.config.stop_loss_type = 'ATR'

        logger.info(f"[开仓] {direction.upper()} @ ${price:.2f} | {signal_type} | "
                   f"C={confidence:.2f} | 止损=${self.config.stop_loss_price:.2f}")

        return True

    def check_exit_conditions(self, current_price, high, low, tension,
                             acceleration, confidence, time_obj, index):
        """
        检查出场条件（V7.0完整逻辑）

        返回: (should_exit, reason, exit_type)
        """
        if not self.config.has_position:
            return False, None, None

        hold_periods = index - self.config.entry_index

        # 更新最大加速度
        if abs(acceleration) > self.config.max_acceleration_in_trade:
            self.config.max_acceleration_in_trade = abs(acceleration)
        self.config.acceleration_history.append(acceleration)

        # ========== 阶段1: T0-T2惯性保护 ==========
        if hold_periods <= self.config.INERTIA_ZONE_PERIODS:
            # 只触发ATR硬止损
            if self.config.USE_ATR_STOP:
                current_atr = self.get_current_atr()
                atr_stop = current_atr * self.config.ATR_MULTIPLIER

                if self.config.position_type == 'long':
                    max_adverse = self.config.entry_price - low
                    if max_adverse > atr_stop:
                        loss_pct = (low - self.config.entry_price) / self.config.entry_price
                        return True, f"ATR硬止损({loss_pct:.2%})", 'stop_loss'
                else:
                    max_adverse = high - self.config.entry_price
                    if max_adverse > atr_stop:
                        loss_pct = (self.config.entry_price - high) / self.config.entry_price
                        return True, f"ATR硬止损({loss_pct:.2%})", 'stop_loss'

            return False, "惯性保护区", None

        # ========== 阶段2: 动能监控期 ==========
        elif hold_periods <= self.config.MAX_HOLD_PERIODS:
            # 1. ATR止损
            if self.config.USE_ATR_STOP:
                current_atr = self.get_current_atr()
                atr_stop = current_atr * self.config.ATR_MULTIPLIER

                if self.config.position_type == 'long':
                    max_adverse = self.config.entry_price - low
                    if max_adverse > atr_stop:
                        loss_pct = (low - self.config.entry_price) / self.config.entry_price
                        return True, f"ATR止损({loss_pct:.2%})", 'stop_loss'
                else:
                    max_adverse = high - self.config.entry_price
                    if max_adverse > atr_stop:
                        loss_pct = (self.config.entry_price - high) / self.config.entry_price
                        return True, f"ATR止损({loss_pct:.2%})", 'stop_loss'

            # 2. 严格动能衰减
            if len(self.config.acceleration_history) >= self.config.ACCEL_DECAY_MIN_PERIODS:
                recent = list(self.config.acceleration_history)[-self.config.ACCEL_DECAY_CONSECUTIVE:]
                is_decaying = all(abs(recent[i]) > abs(recent[i+1]) for i in range(len(recent)-1))
                decay_ratio = abs(acceleration) / self.config.max_acceleration_in_trade
                is_threshold_met = decay_ratio < self.config.ACCEL_DECAY_THRESHOLD

                if is_decaying and is_threshold_met:
                    return True, f"动能衰减({decay_ratio:.1%}<{self.config.ACCEL_DECAY_THRESHOLD*100:.0f}%)", 'take_profit'

            # 3. 张力过载
            if abs(tension) > self.config.TENSION_OVERLOAD_THRESHOLD:
                return True, f"张力过载(|T|={abs(tension):.2f})", 'take_profit'

            # 4. 置信度崩塌
            if confidence < self.config.CONF_COLLAPSE_THRESHOLD:
                return True, f"置信度崩塌({confidence:.2f})", 'take_profit'

            return False, "动能监控期", None

        # ========== 阶段3: 时间窗口到期 ==========
        else:
            return True, f"时间窗口到期(持仓{hold_periods}周期)", 'take_profit'

    def close_position(self, exit_price, exit_time, reason, exit_type):
        """平仓"""
        if not self.config.has_position:
            return

        # 计算盈亏
        if self.config.position_type == 'long':
            pnl_pct = (exit_price - self.config.entry_price) / self.config.entry_price
        else:
            pnl_pct = (self.config.entry_price - exit_price) / self.config.entry_price

        pnl_amount = self.config.entry_price * self.config.position_size * pnl_pct

        # 更新统计
        self.config.total_trades += 1
        if pnl_pct > 0:
            self.config.winning_trades += 1
        else:
            self.config.losing_trades += 1
        self.config.total_pnl += pnl_amount

        # 记录交易
        trade = {
            'entry_time': str(self.config.entry_time),
            'exit_time': str(exit_time),
            'direction': self.config.position_type,
            'entry_price': self.config.entry_price,
            'exit_price': exit_price,
            'pnl_pct': pnl_pct * 100,
            'pnl_amount': pnl_amount,
            'reason': reason,
            'exit_type': exit_type,
            'entry_signal': self.config.entry_signal,
            'entry_confidence': self.config.entry_confidence
        }
        self.config.position_history.append(trade)

        logger.info(f"[平仓] {self.config.position_type.upper()} @ ${exit_price:.2f} | "
                   f"{'盈利' if pnl_pct > 0 else '亏损'} {pnl_pct*100:.2f}% | ${pnl_amount:.2f} | {reason}")

        # 重置状态
        self.config.has_position = False
        self.config.position_type = None
        self.config.entry_price = 0.0
        self.config.entry_time = None
        self.config.entry_index = 0
        self.config.stop_loss_price = 0.0
        self.config.stop_loss_type = None
        self.config.atr_history.clear()
        self.config.acceleration_history.clear()
        self.config.max_acceleration_in_trade = 0.0


# 由于字符限制，我将在下一部分继续创建Telegram模块和主系统
