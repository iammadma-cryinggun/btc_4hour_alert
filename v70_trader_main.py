# -*- coding: utf-8 -*-
"""
================================================================================
V7.0 非线性动力学策略 - 实盘交易系统
================================================================================
基于V7.0回测逻辑的完整实盘版本

核心特性：
- 信号计算：继承v4.2数学家策略的FFT+Hilbert物理计算
- 交易逻辑：V7.0 Combat Robust策略
  - T0-T2惯性保护（前8小时只触发ATR硬止损）
  - 1.5×ATR动态止损
  - 严格动能衰减判断
  - 时间窗口到期（5周期自动平仓）
- 交互功能：Telegram通知和命令
- 状态管理：持久化存储

回测表现：85.01%收益，-31.8%最大回撤，90.2%止盈率

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
        logging.FileHandler('v70_trader.log', encoding='utf-8'),
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
class V70TraderConfig:
    """V7.0交易系统配置"""

    def __init__(self):
        # ========== V7.0核心策略参数 ==========
        # 信号过滤
        self.CONF_THRESHOLD = 0.6          # 置信度阈值（V7.0严格标准）
        self.USE_DXY_FUEL = False          # ⚠️ 是否使用DXY燃料（默认False以匹配V7.0回测）

        # 惯性保护
        self.INERTIA_ZONE_PERIODS = 2       # T0-T2惯性保护区（前8小时）

        # ATR止损
        self.USE_ATR_STOP = True
        self.ATR_PERIOD = 14
        self.ATR_MULTIPLIER = 1.5

        # 动能衰减
        self.ACCEL_DECAY_MIN_PERIODS = 4           # 最少连续4个周期
        self.ACCEL_DECAY_CONSECUTIVE = 3           # 连续3个下降
        self.ACCEL_DECAY_THRESHOLD = 0.7          # 跌幅<70%

        # 张力过载/置信度崩塌
        self.TENSION_OVERLOAD_THRESHOLD = 1.2
        self.CONF_COLLAPSE_THRESHOLD = 0.3

        # 时间窗口
        self.MAX_HOLD_PERIODS = 5             # 最多持有5个周期（20小时）

        # ========== 仓位管理 ==========
        self.BASE_POSITION_SIZE = 0.50        # 基础仓位50%（保守起见）
        self.LEVERAGE = 1                      # 不使用杠杆（V7.0回测是1倍杠杆）

        # ========== API配置 ==========
        self.binance_symbol = "BTCUSDT"
        self.timeframe_4h = "4h"

        # 代理配置（云端部署不需要代理）
        self.proxy_enabled = False
        self.proxy_host = None
        self.proxy_port = None
        self.proxy_http = None
        self.proxy_https = None

        # Telegram配置
        self.telegram_token = os.getenv('TELEGRAM_TOKEN', '8189663571:AAEvIUEBTfF_MfyKc7rWq5gQvgi4gAxZJrA')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '838429342')
        self.telegram_enabled = os.getenv('TELEGRAM_ENABLED', 'True').lower() == 'true'

        # ========== 运行频率 ==========
        self.signal_check_interval = 240      # 4小时检查信号（在K线收盘时）
        self.position_check_interval = 60     # 1小时检查仓位状态

        # ========== 系统状态 ==========
        self.has_position = False
        self.position_type = None             # 'long' or 'short'
        self.entry_price = 0.0
        self.entry_time = None
        self.entry_index = 0                  # 入场时的信号索引
        self.position_size = 0.0
        self.entry_tension = 0.0
        self.entry_acceleration = 0.0
        self.entry_confidence = 0.0
        self.entry_signal = None
        self.entry_atr = 0.0

        # ATR历史
        self.atr_history = deque(maxlen=20)

        # 加速度历史
        self.acceleration_history = deque(maxlen=10)
        self.max_acceleration_in_trade = 0.0

        # 止损价格
        self.stop_loss_price = 0.0
        self.stop_loss_type = None  # 'ATR' or 'breakeven'

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

    def save_state(self, filepath='v70_trader_state.json'):
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
            logger.info(f"[状态] 系统状态已保存")
        except Exception as e:
            logger.error(f"保存状态失败: {e}")

    def load_state(self, filepath='v70_trader_state.json'):
        """加载系统状态"""
        if not os.path.exists(filepath):
            logger.warning(f"[状态] 状态文件不存在: {filepath}")
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

            # 恢复历史数据
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

            # 恢复统计数据
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

        # 设置会话
        self.session = requests.Session()

        # 云端部署不使用代理
        if config.proxy_enabled:
            self.session.proxies = {
                'http': config.proxy_http,
                'https': config.proxy_https
            }
            self.session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

    def fetch_dxy_data(self, limit=10):
        """
        获取DXY美元指数数据（实时，使用FRED官方API）

        返回: DataFrame with 'Close' column
        """
        try:
            from io import StringIO

            # FRED (圣路易斯联储) 提供美元指数DTWEXBGS的CSV下载，无需API key
            url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS'

            resp = self.session.get(url, timeout=15)

            if resp.status_code != 200:
                logger.warning(f"DXY数据获取失败: HTTP {resp.status_code}")
                return None

            # 解析CSV
            dxy_df = pd.read_csv(StringIO(resp.text))
            dxy_df['observation_date'] = pd.to_datetime(dxy_df['observation_date'])
            dxy_df.set_index('observation_date', inplace=True)
            dxy_df.rename(columns={'DTWEXBGS': 'Close'}, inplace=True)
            dxy_df = dxy_df.dropna()

            # 确保Close是float类型
            dxy_df['Close'] = pd.to_numeric(dxy_df['Close'], errors='coerce')

            # 只返回最近的数据
            if len(dxy_df) > limit:
                dxy_df = dxy_df.tail(limit)

            logger.info(f"[DXY] 获取成功: {len(dxy_df)} 条数据")
            return dxy_df

        except Exception as e:
            logger.error(f"获取DXY数据失败: {e}")
            return None


# ==================== [3. 物理信号计算器] ====================
class PhysicsSignalCalculator:
    """物理信号计算器 - 继承v4.2数学家策略的核心算法"""

    def __init__(self, config):
        self.config = config

    def calculate_physics_metrics(self, df):
        """
        计算物理指标：张力、加速度、置信度

        使用验证5的完全相同的逻辑（与generate_signals_with_v5logic.py一致）
        """
        if len(df) < 60:
            return None

        try:
            # 1. 获取价格数组（验证5逻辑：使用价格，不用收益率）
            prices = df['close'].values

            # 2. 去趋势（验证5逻辑：使用scipy.signal.detrend）
            from scipy.signal import detrend
            d_prices = detrend(prices)

            # 3. FFT滤波（保留前8个系数）
            coeffs = fft(d_prices)
            coeffs[8:] = 0
            filtered = ifft(coeffs).real

            # 4. Hilbert变换 → 张力
            analytic = hilbert(filtered)
            tension = np.imag(analytic)

            # 5. 标准化张力
            if len(tension) > 1 and np.std(tension) > 0:
                tension_normalized = (tension - np.mean(tension)) / np.std(tension)
            else:
                tension_normalized = tension

            # 6. 手动计算加速度（验证5逻辑：二阶差分）
            # 对每个时间点计算加速度
            acceleration = np.zeros_like(tension_normalized)
            for i in range(2, len(tension_normalized)):
                current_tension = tension_normalized[i]
                prev_tension = tension_normalized[i-1]
                prev2_tension = tension_normalized[i-2]

                # 速度 = 张力的一阶差分
                velocity = current_tension - prev_tension

                # 加速度 = 速度的一阶差分（张力的二阶差分）
                acceleration[i] = velocity - (prev_tension - prev2_tension)

            # 创建结果DataFrame
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

    def calculate_dxy_fuel(self, dxy_df, current_date):
        """
        计算DXY燃料（验证5逻辑）

        DXY的负加速度（失速）为BTC的正向燃料

        参数:
        - dxy_df: DXY数据DataFrame
        - current_date: 当前日期

        返回:
        - fuel: DXY燃料值（越大越好）
        """
        if dxy_df is None or dxy_df.empty:
            return 0.0

        try:
            # 获取当前日期之前的DXY数据
            mask = dxy_df.index <= current_date
            available = dxy_df[mask]

            if len(available) < 3:
                return 0.0

            # 取最近5个数据点
            recent = available.tail(5)

            if len(recent) < 3:
                return 0.0

            # 计算DXY的加速度（二阶差分）
            closes = recent['Close'].values.astype(float)

            # 价格变化率
            change_1 = (closes[-1] - closes[-2]) / closes[-2]
            change_2 = (closes[-2] - closes[-3]) / closes[-3] if len(closes) >= 3 else change_1

            # 加速度 = 变化率的变化
            acceleration = change_1 - change_2

            # 燃料定义：DXY的负加速度（失速）为正向燃料
            fuel = -acceleration * 100  # 放大系数

            return float(fuel)

        except Exception as e:
            logger.error(f"计算DXY燃料失败: {e}")
            return 0.0

    def diagnose_regime(self, tension, acceleration, dxy_fuel=0.0):
        """
        诊断市场状态并生成信号（验证5逻辑）

        返回: (signal_type, confidence, description)
        signal_type: 'BEARISH_SINGULARITY' | 'BULLISH_SINGULARITY' | 'OSCILLATION' | 'OSCILLATION_PEAK' | 'OSCILLATION_TROUGH' | None

        ⚠️ DXY燃料说明：
        - USE_DXY_FUEL=False（默认）：与V7.0回测保持一致，置信度0.6~0.8
        - USE_DXY_FUEL=True：使用完整验证5逻辑，置信度可达0.9~0.95
        """
        confidence = 0.0
        signal_type = None
        description = "无信号"

        # 验证5逻辑参数
        TENSION_THRESHOLD = 0.35
        ACCEL_THRESHOLD = 0.02
        OSCILLATION_BAND = 0.5

        # 1. 奇点看空（系统看空→我们做多）
        if tension > TENSION_THRESHOLD and acceleration < -ACCEL_THRESHOLD:
            if self.config.USE_DXY_FUEL and dxy_fuel > 0.1:
                confidence = 0.9
                description = f"强奇点看空(T={tension:.2f}≥{TENSION_THRESHOLD}, DXY_fuel={dxy_fuel:.2f})"
            else:
                confidence = 0.7
                description = f"奇点看空(T={tension:.2f}≥{TENSION_THRESHOLD})"
            signal_type = 'BEARISH_SINGULARITY'

        # 2. 奇点看涨（系统看涨→我们做空）
        elif tension < -TENSION_THRESHOLD and acceleration > ACCEL_THRESHOLD:
            if self.config.USE_DXY_FUEL and dxy_fuel > 0.2:
                confidence = 0.95
                description = f"超强奇点看涨(T={tension:.2f}≤-{TENSION_THRESHOLD}, DXY_fuel={dxy_fuel:.2f})"
            elif self.config.USE_DXY_FUEL and dxy_fuel > 0:
                confidence = 0.8
                description = f"强奇点看涨(T={tension:.2f}≤-{TENSION_THRESHOLD})"
            else:
                confidence = 0.6
                description = f"奇点看涨(T={tension:.2f}≤-{TENSION_THRESHOLD})"
            signal_type = 'BULLISH_SINGULARITY'

        # 3. 震荡区间（系统平衡）
        elif abs(tension) < OSCILLATION_BAND and abs(acceleration) < ACCEL_THRESHOLD:
            confidence = 0.8
            signal_type = 'OSCILLATION'
            description = f"系统平衡震荡(|T|={abs(tension):.2f}<{OSCILLATION_BAND})"

        # 4. 高位震荡（峰值回归）
        elif tension > 0.3 and abs(acceleration) < 0.01:
            confidence = 0.6
            signal_type = 'OSCILLATION_PEAK'
            description = f"高位震荡(T={tension:.2f}>0.3)"

        # 5. 低位震荡（低位回归）
        elif tension < -0.3 and abs(acceleration) < 0.01:
            confidence = 0.6
            signal_type = 'OSCILLATION_TROUGH'
            description = f"低位震荡(T={tension:.2f}<-0.3)"

        # 置信度过滤
        if confidence < self.config.CONF_THRESHOLD:
            return None, 0.0, "置信度不足"

        return signal_type, confidence, description


# ==================== [4. V7.0交易逻辑] ====================
class V70TradingEngine:
    """V7.0交易引擎 - Combat Robust策略"""

    def __init__(self, config):
        self.config = config

    def calculate_atr(self, high, low, close):
        """计算单个周期的真实波幅"""
        high_low = high - low
        high_close = abs(high - close)
        low_close = abs(low - close)
        return max(high_low, high_close, low_close)

    def get_current_atr(self):
        """获取当前ATR值（14周期平均）"""
        if len(self.config.atr_history) < self.config.ATR_PERIOD:
            # 如果历史不够，用入场价的2%估算
            return self.config.entry_price * 0.02 if self.config.entry_price > 0 else 500.0

        return sum(list(self.config.atr_history)[-self.config.ATR_PERIOD:]) / self.config.ATR_PERIOD

    def check_entry_signal(self, signal_type, confidence, current_price):
        """
        检查是否满足入场条件

        V7.0规则：
        1. 置信度≥0.6
        2. 当前无仓位
        3. 信号类型有效
        """
        # 必须有有效信号
        if signal_type is None:
            return False, "无有效信号"

        # 置信度过滤
        if confidence < self.config.CONF_THRESHOLD:
            return False, f"置信度不足({confidence:.2f}<{self.config.CONF_THRESHOLD})"

        # 检查是否已有仓位
        if self.config.has_position:
            return False, "已有持仓"

        return True, "满足入场条件"

    def get_entry_direction(self, signal_type):
        """根据信号类型确定入场方向（反向策略）"""
        if signal_type == 'BEARISH_SINGULARITY':
            # 系统看空（张力极正）→ 我们做多
            return 'long', "BEARISH_SINGULARITY反向做多"
        elif signal_type == 'BULLISH_SINGULARITY':
            # 系统看涨（张力极负）→ 我们做空
            return 'short', "BULLISH_SINGULARITY反向做空"
        elif signal_type == 'OSCILLATION_PEAK':
            # 峰值回归 → 做空
            return 'short', "OSCILLATION峰值做空"
        elif signal_type == 'OSCILLATION_TROUGH':
            # 低位回归 → 做多
            return 'long', "OSCILLATION低位做多"
        else:
            return None, f"未知信号类型({signal_type})"

    def open_position(self, direction, entry_price, current_time, signal_index,
                      signal_type, tension, acceleration, confidence, atr):
        """开仓"""
        self.config.has_position = True
        self.config.position_type = direction
        self.config.entry_price = entry_price
        self.config.entry_time = current_time
        self.config.entry_index = signal_index
        self.config.position_size = self.config.BASE_POSITION_SIZE
        self.config.entry_tension = tension
        self.config.entry_acceleration = acceleration
        self.config.entry_confidence = confidence
        self.config.entry_signal = signal_type
        self.config.entry_atr = atr

        # 初始化ATR历史
        self.config.atr_history.clear()
        self.config.atr_history.append(atr)

        # 初始化加速度历史
        self.config.acceleration_history.clear()
        self.config.acceleration_history.append(acceleration)
        self.config.max_acceleration_in_trade = abs(acceleration)

        # 设置初始止损（1.5×ATR）
        current_atr = self.get_current_atr()
        atr_stop_distance = current_atr * self.config.ATR_MULTIPLIER

        if direction == 'long':
            self.config.stop_loss_price = entry_price - atr_stop_distance
        else:  # short
            self.config.stop_loss_price = entry_price + atr_stop_distance

        self.config.stop_loss_type = 'ATR'

        logger.info(f"[开仓] {direction.upper()} @ ${entry_price:.2f} | "
                   f"{signal_type} | C={confidence:.2f} | T={tension:.2f} | "
                   f"止损=${self.config.stop_loss_price:.2f} ({self.config.stop_loss_type})")

        return True

    def has_tension_reversed_directionally(self, current_tension: float) -> bool:
        """
        检查张力是否方向性反转（V7.0回测逻辑）

        规则：
        - 必须先归零（|T|<0.1）
        - 方向改变（正→负 或 负→正）

        返回: True表示张力已反转
        """
        if self.config.entry_tension is None:
            return False

        # 必须先归零
        if abs(current_tension) > 0.1:
            return False

        # 检查方向改变
        if (self.config.entry_tension > 0 and current_tension < 0) or \
           (self.config.entry_tension < 0 and current_tension > 0):
            return True

        return False

    def check_exit_conditions(self, current_price, high_price, low_price,
                             current_tension, current_acceleration, current_confidence,
                             current_time, signal_index):
        """
        检查出场条件（V7.0 Combat Robust逻辑）

        返回: (should_exit, reason, exit_type)
        exit_type: 'take_profit' | 'stop_loss'
        """
        if not self.config.has_position:
            return False, None, None

        hold_periods = signal_index - self.config.entry_index

        # 更新最大加速度
        if abs(current_acceleration) > self.config.max_acceleration_in_trade:
            self.config.max_acceleration_in_trade = abs(current_acceleration)
        self.config.acceleration_history.append(current_acceleration)

        # ========== 阶段1: 惯性保护区 (0-2周期) ==========
        if hold_periods <= self.config.INERTIA_ZONE_PERIODS:
            # 只触发ATR硬止损
            if self.config.USE_ATR_STOP:
                current_atr = self.get_current_atr()
                atr_stop_distance = current_atr * self.config.ATR_MULTIPLIER

                if self.config.position_type == 'long':
                    max_adverse = self.config.entry_price - low_price
                    if max_adverse > atr_stop_distance:
                        loss_pct = (low_price - self.config.entry_price) / self.config.entry_price
                        return True, f"ATR硬止损({loss_pct:.2%})", 'stop_loss'
                else:  # short
                    max_adverse = high_price - self.config.entry_price
                    if max_adverse > atr_stop_distance:
                        loss_pct = (self.config.entry_price - high_price) / self.config.entry_price
                        return True, f"ATR硬止损({loss_pct:.2%})", 'stop_loss'

            return False, "惯性保护区（屏蔽所有熔断）", None

        # ========== 阶段2: 动能监控期 (2-5周期) ==========
        elif hold_periods <= self.config.MAX_HOLD_PERIODS:
            # 1. ATR跟踪止损
            if self.config.USE_ATR_STOP:
                current_atr = self.get_current_atr()
                atr_stop_distance = current_atr * self.config.ATR_MULTIPLIER

                if self.config.position_type == 'long':
                    max_adverse = self.config.entry_price - low_price
                    if max_adverse > atr_stop_distance:
                        loss_pct = (low_price - self.config.entry_price) / self.config.entry_price
                        return True, f"ATR止损({loss_pct:.2%})", 'stop_loss'
                else:  # short
                    max_adverse = high_price - self.config.entry_price
                    if max_adverse > atr_stop_distance:
                        loss_pct = (self.config.entry_price - high_price) / self.config.entry_price
                        return True, f"ATR止损({loss_pct:.2%})", 'stop_loss'

            # 2. ⭐ V7.0新增：张力方向性反转（优先级高于动能衰减）
            if self.has_tension_reversed_directionally(current_tension):
                return True, f"张力方向反转(T从{self.config.entry_tension:.2f}→{current_tension:.2f})", 'take_profit'

            # 3. ⭐ V7.0新增：动能阈值止盈（3周期后）
            if hold_periods > 3:
                if abs(current_acceleration) < 0.03:
                    return True, f"动能耗尽(|a|={abs(current_acceleration):.3f}<0.03)", 'take_profit'

            # 4. 严格动能衰减
            if len(self.config.acceleration_history) >= self.config.ACCEL_DECAY_MIN_PERIODS:
                recent = list(self.config.acceleration_history)[-self.config.ACCEL_DECAY_CONSECUTIVE:]
                is_decaying = all(abs(recent[i]) > abs(recent[i+1]) for i in range(len(recent)-1))
                decay_ratio = abs(current_acceleration) / self.config.max_acceleration_in_trade
                is_threshold_met = decay_ratio < self.config.ACCEL_DECAY_THRESHOLD

                if is_decaying and is_threshold_met:
                    return True, f"动能衰减({decay_ratio:.1%}<{self.config.ACCEL_DECAY_THRESHOLD*100:.0f}%)", 'take_profit'

            # 5. 张力过载
            if abs(current_tension) > self.config.TENSION_OVERLOAD_THRESHOLD:
                return True, f"张力过载(|T|={abs(current_tension):.2f})", 'take_profit'

            # 6. 置信度崩塌
            if current_confidence < self.config.CONF_COLLAPSE_THRESHOLD:
                return True, f"置信度崩塌({current_confidence:.2f})", 'take_profit'

            return False, "动能监控期", None

        # ========== 阶段3: 时间窗口到期 ==========
        else:
            return True, f"时间窗口到期(持仓{hold_periods}周期)", 'take_profit'

    def close_position(self, exit_price, exit_time, reason, exit_type):
        """平仓"""
        if not self.config.has_position:
            logger.warning("[平仓] 无持仓，无法平仓")
            return

        # 计算盈亏
        if self.config.position_type == 'long':
            pnl_pct = (exit_price - self.config.entry_price) / self.config.entry_price
        else:  # short
            pnl_pct = (self.config.entry_price - exit_price) / self.config.entry_price

        # 考虑仓位大小
        pnl_amount = self.config.entry_price * self.config.position_size * pnl_pct

        # 更新统计
        self.config.total_trades += 1
        if pnl_pct > 0:
            self.config.winning_trades += 1
        else:
            self.config.losing_trades += 1
        self.config.total_pnl += pnl_amount

        # 记录交易历史
        trade_record = {
            'entry_time': str(self.config.entry_time),
            'exit_time': str(exit_time),
            'direction': self.config.position_type,
            'entry_price': self.config.entry_price,
            'exit_price': exit_price,
            'pnl_pct': pnl_pct * 100,
            'pnl_amount': pnl_amount,
            'reason': reason,
            'exit_type': exit_type,
            'hold_periods': exit_time - self.config.entry_time,
            'entry_signal': self.config.entry_signal,
            'entry_confidence': self.config.entry_confidence
        }
        self.config.position_history.append(trade_record)

        logger.info(f"[平仓] {self.config.position_type.upper()} @ ${exit_price:.2f} | "
                   f"{'盈利' if pnl_pct > 0 else '亏损'} {pnl_pct*100:.2f}% | "
                   f"${pnl_amount:.2f} | {reason}")

        # 重置状态
        self.config.has_position = False
        self.config.position_type = None
        self.config.entry_price = 0.0
        self.config.entry_time = None
        self.config.entry_index = 0
        self.config.position_size = 0.0
        self.config.stop_loss_price = 0.0
        self.config.stop_loss_type = None
        self.config.atr_history.clear()
        self.config.acceleration_history.clear()
        self.config.max_acceleration_in_trade = 0.0


# ==================== [5. Telegram通知模块] ====================
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

            # 如果使用代理（云端部署不使用代理）
            proxies = None
            if self.config.proxy_enabled and self.config.proxy_http:
                proxies = {
                    'http': self.config.proxy_http,
                    'https': self.config.proxy_https
                }

            resp = requests.post(url, json=data, proxies=proxies, timeout=10)

            if resp.status_code == 200:
                logger.info(f"[Telegram] 消息已发送")
            else:
                logger.warning(f"[Telegram] 发送失败: HTTP {resp.status_code}")

        except Exception as e:
            logger.error(f"[Telegram] 发送消息异常: {e}")

    def notify_signal(self, signal_type, confidence, description, price, tension, acceleration):
        """通知新信号"""
        message = f"""
🎯 *V7.0新信号*

📊 *信号类型*: {signal_type}
📈 *置信度*: {confidence:.2f}
💡 *描述*: {description}
💰 *当前价格*: ${price:.2f}
📐 *张力*: {tension:.3f}
🚀 *加速度*: {acceleration:.3f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_message(message)

    def notify_entry(self, direction, price, signal_type, confidence, stop_loss):
        """通知开仓"""
        emoji = "📈" if direction == 'long' else "📉"
        message = f"""
{emoji} *V7.0开仓*

📍 *方向*: {direction.upper()}
💰 *入场价*: ${price:.2f}
🎯 *信号*: {signal_type}
📊 *置信度*: {confidence:.2f}
🛑 *止损*: ${stop_loss:.2f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_message(message)

    def notify_exit(self, direction, entry_price, exit_price, pnl_pct, reason, exit_type):
        """通知平仓"""
        emoji = "✅" if pnl_pct > 0 else "❌"
        exit_emoji = "止盈" if exit_type == 'take_profit' else "止损"
        message = f"""
{emoji} *V7.0平仓*

📍 *方向*: {direction.upper()}
💰 *入场*: ${entry_price:.2f}
💵 *出场*: ${exit_price:.2f}
📊 *盈亏*: {pnl_pct:+.2f}%
🎯 *原因*: {reason}
🏷 *类型*: {exit_emoji}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_message(message)

    def notify_status(self):
        """通知系统状态"""
        if self.config.has_position:
            hold_time = datetime.now() - self.config.entry_time
            message = f"""
📊 *V7.0持仓状态*

📍 *方向*: {self.config.position_type.upper()}
💰 *入场价*: ${self.config.entry_price:.2f}
🛑 *止损*: ${self.config.stop_loss_price:.2f} ({self.config.stop_loss_type})
⏱ *持仓时长*: {hold_time}
📊 *入场置信度*: {self.config.entry_confidence:.2f}

📈 *总交易*: {self.config.total_trades}
✅ *盈利*: {self.config.winning_trades}
❌ *亏损*: {self.config.losing_trades}
💵 *总盈亏*: {self.config.total_pnl:.2f}%
"""
        else:
            message = f"""
📊 *V7.0系统状态*

⭕ *当前状态*: 空仓
📈 *总交易*: {self.config.total_trades}
✅ *盈利*: {self.config.winning_trades}
❌ *亏损*: {self.config.losing_trades}
💵 *总盈亏*: {self.config.total_pnl:.2f}%

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_message(message)


# 由于代码较长，我将在下一条消息中继续创建主程序部分
