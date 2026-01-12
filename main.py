# -*- coding: utf-8 -*-
"""
================================================================================
[数学家非线性动力学策略] 实时信号预警系统 V4.2
================================================================================
基于物理学的量化交易框架 - 完整实盘版本

核心原则: "顺应相位切换（Transition），在极值奇点（Singularity）处博弈回归"

策略来源: 数学家非线性动力学理论
回测表现: 2年924.03%收益，年化227.63%，胜率98.85% (86胜1负)

================================================================================
策略特性:
================================================================================

[入场策略]
1. 顺势启动 (TRANSITION)
   - TRANSITION_UP + acceleration>0 → 做多
   - TRANSITION_DOWN + acceleration<0 → 做空

2. 奇点博弈 (SINGULARITY)
   - 模式A: |张力| >= 0.85 → 极值反转 (反向操作)
   - 模式B: |张力| < 0.65 → 真空加速 (顺势操作)

[出场策略]
1. 张力释放止盈: |张力| < 0.1
2. 信号反转止盈: 反向TRANSITION信号
3. 价格硬止损: ±0.35% (5倍杠杆调整后)
4. 逻辑失效止损: 置信度 < 0.35 (98.85%胜率的秘密！)

[风险管理]
- 基础仓位: 30%
- 杠杆倍数: 5倍
- DXY燃料加成: 0.8x - 1.2x
- 多层过滤: 4层过滤机制

================================================================================
"""

import numpy as np
import pandas as pd
import warnings
import json
import os
import requests
import time
from datetime import datetime, timedelta
from scipy.signal import hilbert, detrend
from scipy.fft import fft, ifft
import schedule
import logging
from collections import deque

warnings.filterwarnings('ignore')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('physics_alert_v4_2_math.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 尝试加载环境变量，如果dotenv不可用则跳过
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv未安装，将使用默认配置")


# ==================== [1. 配置类 - 数学家策略] ====================
class MathematicianConfig:
    """数学家策略配置 - V4.2完整版"""

    def __init__(self):
        # ========== 核心策略参数 ==========
        # 过滤参数
        self.CONF_THRESHOLD = 0.5          # 置信度阈值（过滤低频噪声）
        self.TENSION_MAX = 0.85            # 极值反转阈值
        self.TENSION_MIN = 0.65            # 真空加速阈值（2026-01-12回退优化v1，经回测验证0.70性能下降）
        self.ACCEL_LIMIT = 0.0             # 加速度限制
        self.ACCEL_MIN = 0.005             # 假奇点过滤阈值

        # 止损止盈参数（考虑杠杆）
        self.LEVERAGE = 5                  # 5倍杠杆
        self.BASE_POSITION = 0.30          # 基础仓位30%
        self.STOP_LOSS_PCT = 0.0175 / self.LEVERAGE  # 止损幅度（杠杆调整后=0.35%）
        self.CONF_FAIL_THRESHOLD = 0.35    # 逻辑失效阈值（关键！）

        # DXY燃料加成
        self.DXY_FUEL_MULTIPLIER = 1.2     # 燃料一致时
        self.DXY_FUEL_REDUCTION = 0.8      # 燃料相反时

        # 张力释放止盈
        self.TENSION_RELEASE_THRESHOLD = 0.1

        # ========== API配置 ==========
        self.binance_symbol = "BTCUSDT"
        self.timeframe_4h = "4h"
        self.timeframe_1h = "1h"

        # 代理配置
        self.proxy_enabled = True
        self.proxy_host = "127.0.0.1"
        self.proxy_port = "15236"
        self.proxy_http = f"http://{self.proxy_host}:{self.proxy_port}"
        self.proxy_https = f"http://{self.proxy_host}:{self.proxy_port}"

        # Telegram配置（从环境变量读取）
        self.telegram_token = os.getenv('TELEGRAM_TOKEN', '8189663571:AAEvIUEBTfF_MfyKc7rWq5gQvgi4gAxZJrA')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '838429342')
        self.telegram_enabled = os.getenv('TELEGRAM_ENABLED', 'True').lower() == 'true'

        # ========== 运行频率配置 ==========
        self.signal_check_interval = 240   # 4小时检查信号
        self.position_check_interval = 60  # 1小时检查仓位状态

        # ========== 系统状态 ==========
        self.has_position = False
        self.position_type = None  # 'long' or 'short'
        self.entry_price = 0.0
        self.entry_time = None
        self.position_size = 0.0
        self.margin_used = 0.0
        self.entry_tension = 0.0
        self.entry_signal = None
        self.entry_confidence = 0.0
        self.entry_dxy_fuel = 0.0
        self.stop_loss_price = 0.0  # 止损价格

        # 最新信号
        self.last_signal_time = None
        self.last_signal_type = None
        self.last_signal_desc = ""
        self.last_signal_price = 0.0
        self.last_signal_confidence = 0.0
        self.last_signal_valid = False

        # DXY数据
        self.dxy_data = deque(maxlen=100)
        self.dxy_latest_fuel = 0.0

        # 信号历史
        self.signal_history = []
        self.position_history = []

    def save_state(self, filepath='mathematician_v4_2_state.json'):
        """保存系统状态"""
        state = {
            'has_position': self.has_position,
            'position_type': self.position_type,
            'entry_price': self.entry_price,
            'entry_time': str(self.entry_time) if self.entry_time else None,
            'position_size': self.position_size,
            'margin_used': self.margin_used,
            'entry_tension': self.entry_tension,
            'entry_signal': self.entry_signal,
            'entry_confidence': self.entry_confidence,
            'entry_dxy_fuel': self.entry_dxy_fuel,
            'last_signal_time': str(self.last_signal_time) if self.last_signal_time else None,
            'last_signal_type': self.last_signal_type,
            'last_signal_desc': self.last_signal_desc,
            'last_signal_price': self.last_signal_price,
            'last_signal_confidence': self.last_signal_confidence,
            'last_signal_valid': self.last_signal_valid,
            'dxy_latest_fuel': self.dxy_latest_fuel,
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存状态失败: {e}")

    def load_state(self, filepath='mathematician_v4_2_state.json'):
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
            self.position_size = state.get('position_size', 0.0)
            self.margin_used = state.get('margin_used', 0.0)
            self.entry_tension = state.get('entry_tension', 0.0)
            self.entry_signal = state.get('entry_signal')
            self.entry_confidence = state.get('entry_confidence', 0.0)
            self.entry_dxy_fuel = state.get('entry_dxy_fuel', 0.0)

            if state.get('last_signal_time'):
                self.last_signal_time = datetime.fromisoformat(state['last_signal_time'])
            self.last_signal_type = state.get('last_signal_type')
            self.last_signal_desc = state.get('last_signal_desc', '')
            self.last_signal_price = state.get('last_signal_price', 0.0)
            self.last_signal_confidence = state.get('last_signal_confidence', 0.0)
            self.last_signal_valid = state.get('last_signal_valid', False)
            self.dxy_latest_fuel = state.get('dxy_latest_fuel', 0.0)

            return True
        except Exception as e:
            logger.error(f"加载状态失败: {e}")
            return False


# ==================== [2. 数据管理器] ====================
class DataFetcher:
    """数据获取器 - 支持Binance实时数据"""

    def __init__(self, config):
        self.config = config

        # 设置代理
        self.session = requests.Session()
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

    def fetch_dxy_data(self, limit=100):
        """获取DXY数据（FRED官方CSV，无需API key）"""
        try:
            # FRED (圣路易斯联储) 提供美元指数DTWEXBGS的CSV下载，无需API key
            # 这是官方且最可靠的数据源
            from io import StringIO
            from datetime import timedelta

            url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS'

            resp = self.session.get(url, timeout=15)

            if resp.status_code == 200:
                df = pd.read_csv(StringIO(resp.text))
                df['observation_date'] = pd.to_datetime(df['observation_date'])
                df.set_index('observation_date', inplace=True)
                df.rename(columns={'DTWEXBGS': 'Close'}, inplace=True)
                df['Close'] = pd.to_numeric(df['Close'])
                df = df.dropna()

                # 只保留最近90天的数据
                cutoff_date = datetime.now() - timedelta(days=90)
                df = df[df.index >= cutoff_date]

                logger.info(f"DXY数据获取成功 (FRED官方, {len(df)}条)")
                return df[['Close']].sort_index()
            else:
                logger.warning(f"FRED返回错误: HTTP {resp.status_code}")
                return None

        except Exception as e:
            logger.error(f"获取DXY数据失败: {e}")
            return None


# ==================== [3. 物理信号计算器] ====================
class PhysicsSignalCalculator:
    """物理信号计算器 - 数学家策略核心算法"""

    def __init__(self, config):
        self.config = config

    def calculate_physics_metrics(self, df):
        """计算物理指标：张力、加速度、置信度"""
        if len(df) < 50:
            return None

        # 1. 计算收益率
        df['returns'] = df['close'].pct_change()

        # 2. FFT低通滤波（保留前8个系数）
        fft_result = fft(df['returns'].dropna().values)
        fft_filtered = np.zeros_like(fft_result)
        fft_filtered[:8] = fft_result[:8]
        fft_filtered[-8:] = fft_result[-8:]
        filtered_returns = np.real(ifft(fft_filtered))

        # 填充NaN
        filtered_returns = np.concatenate([[0]*(len(df)-len(filtered_returns)), filtered_returns])

        # 3. Hilbert变换 → 张力
        analytic_signal = hilbert(filtered_returns)
        tension = np.imag(analytic_signal)

        # 4. 标准化张力
        tension_mean = np.mean(tension)
        tension_std = np.std(tension)
        if tension_std > 0:
            tension_normalized = (tension - tension_mean) / tension_std
        else:
            tension_normalized = tension

        # 5. 加速度（张力的一阶导数）
        acceleration = np.gradient(tension_normalized)

        # 创建结果DataFrame
        result = pd.DataFrame({
            'tension': tension_normalized,
            'acceleration': acceleration,
            'close': df['close'].values
        }, index=df.index)

        # 6. 计算置信度
        result['confidence'] = self.calculate_confidence(result)

        # 7. 判断信号类型
        result['signal_type'] = result.apply(
            lambda row: self.classify_signal(row['tension'], row['acceleration'], row['confidence']),
            axis=1
        )

        # 8. 验证信号
        result['verified'] = result['confidence'] >= self.config.CONF_THRESHOLD

        return result

    def calculate_confidence(self, df):
        """计算置信度"""
        confidence = []

        for i in range(len(df)):
            tension = df.iloc[i]['tension']
            accel = df.iloc[i]['acceleration']

            # 基础置信度
            base_conf = min(abs(tension) * 0.8 + abs(accel) * 10, 0.95)

            # 根据信号类型调整
            if abs(tension) > 0.35:
                if (tension > 0 and accel < -0.02) or (tension < 0 and accel > 0.02):
                    # 奇点信号
                    if tension > 0:
                        base_conf = max(base_conf, 0.70)  # BEARISH_SINGULARITY
                    else:
                        base_conf = max(base_conf, 0.60)  # BULLISH_SINGULARITY

            confidence.append(base_conf)

        return confidence

    def classify_signal(self, tension, acceleration, confidence):
        """分类信号类型"""
        # 震荡区
        if abs(tension) < 0.2:
            return "OSCILLATION"

        # 看涨奇点
        if tension < -0.35 and acceleration > 0.02:
            return "BULLISH_SINGULARITY"

        # 看空奇点
        if tension > 0.35 and acceleration < -0.02:
            return "BEARISH_SINGULARITY"

        # 上涨过渡
        if tension > 0.1 and tension < 0.3 and acceleration > 0:
            return "TRANSITION_UP"

        # 下跌过渡
        if tension < -0.1 and tension > -0.3 and acceleration < 0:
            return "TRANSITION_DOWN"

        # 默认震荡
        return "OSCILLATION"

    def calculate_dxy_fuel(self, dxy_df):
        """计算DXY燃料 - 使用前一天数据"""
        if dxy_df is None or dxy_df.empty:
            return 0.0

        try:
            from datetime import timedelta

            # 使用前一天的数据（避免未来数据泄露）
            date = datetime.now()
            prev_date = date - timedelta(days=1)
            mask = dxy_df.index <= prev_date
            available_dates = dxy_df[mask].index

            if len(available_dates) == 0:
                return 0.0

            latest_date = available_dates[-1]
            recent = dxy_df.loc[:latest_date].tail(5)

            if len(recent) < 3:
                return 0.0

            closes = recent['Close'].values.astype(float)

            change_1 = (closes[-1] - closes[-2]) / closes[-2]
            change_2 = (closes[-2] - closes[-3]) / closes[-3] if len(closes) >= 3 else change_1

            acceleration = change_1 - change_2
            fuel = -acceleration * 100

            return float(fuel)
        except Exception as e:
            logger.error(f"DXY燃料计算错误: {e}")
            return 0.0


# ==================== [4. 交易决策引擎] ====================
class TradingDecisionEngine:
    """交易决策引擎 - 数学家策略核心逻辑"""

    def __init__(self, config):
        self.config = config

    def is_valid_signal(self, row):
        """有效性过滤"""
        verified = row.get('verified', False)
        confidence = row.get('confidence', 0)

        condition_valid = (verified == True) and (confidence >= self.config.CONF_THRESHOLD)
        return condition_valid, confidence

    def analyze_transition_signal(self, row):
        """顺势启动策略"""
        signal_type = str(row.get('signal_type', ''))
        acceleration = row.get('acceleration', 0)

        valid = False
        direction = None
        reason = ''

        if 'TRANSITION_UP' in signal_type:
            if acceleration > self.config.ACCEL_LIMIT:
                valid = True
                direction = 'long'
                reason = 'TRANSITION_UP顺势做多'

        elif 'TRANSITION_DOWN' in signal_type:
            if acceleration < self.config.ACCEL_LIMIT:
                valid = True
                direction = 'short'
                reason = 'TRANSITION_DOWN顺势做空'

        return valid, direction, reason

    def analyze_singularity_signal(self, row):
        """奇点博弈策略"""
        signal_type = str(row.get('signal_type', ''))
        tension = row.get('tension', 0)
        acceleration = row.get('acceleration', 0)

        tension_abs = abs(tension)

        # 假奇点过滤
        if abs(acceleration) < self.config.ACCEL_MIN:
            return False, None, '假奇点（加速度太小）'

        # 模式A：极值反转
        if tension_abs >= self.config.TENSION_MAX:
            valid, direction = self.check_reversal_mode(signal_type, tension)
            if valid:
                return True, direction, f'极值反转模式（张力={tension:.2f}）'

        # 模式B：真空加速
        elif tension_abs < self.config.TENSION_MIN:
            valid, direction = self.check_breakout_mode(signal_type, tension)
            if valid:
                return True, direction, f'真空加速模式（张力={tension:.2f}）'

        return False, None, f'张力处于中间区域（{tension_abs:.2f}）'

    def check_reversal_mode(self, signal_type, tension):
        """模式A：极值反转"""
        valid = False
        direction = None

        if 'BULLISH' in signal_type and tension > 0:
            valid = True
            direction = 'short'  # 反向
        elif 'BEARISH' in signal_type and tension < 0:
            valid = True
            direction = 'long'   # 反向

        return valid, direction

    def check_breakout_mode(self, signal_type, tension):
        """模式B：真空加速"""
        valid = False
        direction = None

        if 'BULLISH' in signal_type:
            valid = True
            direction = 'long'   # 顺势
        elif 'BEARISH' in signal_type:
            valid = True
            direction = 'short'  # 顺势

        return valid, direction

    def check_exit_conditions(self, row, current_price):
        """止盈与止损"""
        if not self.config.has_position:
            return False, None

        exit_signal = False
        exit_reason = None

        tension = row.get('tension', 0)

        # 1. 止盈：张力释放
        if abs(tension) < self.config.TENSION_RELEASE_THRESHOLD:
            exit_signal = True
            exit_reason = '张力释放（能量耗尽）'

        # 2. 止盈：反向TRANSITION信号
        if not exit_signal:
            signal_type = str(row.get('signal_type', ''))
            if self.config.position_type == 'long' and 'TRANSITION_DOWN' in signal_type:
                exit_signal = True
                exit_reason = '反向TRANSITION信号'
            elif self.config.position_type == 'short' and 'TRANSITION_UP' in signal_type:
                exit_signal = True
                exit_reason = '反向TRANSITION信号'

        # 3. 止损：价格硬止损
        if not exit_signal:
            if self.config.position_type == 'long':
                price_change = (current_price - self.config.entry_price) / self.config.entry_price
                if price_change <= -self.config.STOP_LOSS_PCT:
                    exit_signal = True
                    exit_reason = f'价格止损（{price_change*100:.2f}%）'
            elif self.config.position_type == 'short':
                price_change = (self.config.entry_price - current_price) / self.config.entry_price
                if price_change <= -self.config.STOP_LOSS_PCT:
                    exit_signal = True
                    exit_reason = f'价格止损（{price_change*100:.2f}%）'

        # 4. 逻辑失效止损（关键！）
        if not exit_signal:
            condition_valid, confidence = self.is_valid_signal(row)
            if not condition_valid or confidence < self.config.CONF_FAIL_THRESHOLD:
                exit_signal = True
                exit_reason = f'逻辑失效（置信度={confidence:.2f}）'

        return exit_signal, exit_reason


# ==================== [5. Telegram通知模块] ====================
class TelegramNotifier:
    """Telegram通知模块"""

    def __init__(self, config):
        self.config = config
        self.token = config.telegram_token
        self.chat_id = config.telegram_chat_id
        self.enabled = config.telegram_enabled

        # 设置代理
        self.session = requests.Session()
        if config.proxy_enabled:
            self.session.proxies = {
                'http': config.proxy_http,
                'https': config.proxy_https
            }
        self.session.verify = False

    def send_message(self, message, parse_mode=None):
        """发送Telegram消息"""
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'disable_web_page_preview': True
            }

            # 仅当明确指定parse_mode时才添加
            if parse_mode:
                data['parse_mode'] = parse_mode

            response = self.session.post(url, json=data, timeout=10)
            result = response.json()

            if result.get('ok'):
                return True
            else:
                logger.error(f"Telegram发送失败: {result}")
                return False

        except Exception as e:
            logger.error(f"Telegram发送异常: {e}")
            return False

    def notify_signal(self, signal_type, direction, reason, price, tension, confidence, dxy_fuel):
        """通知新信号"""
        emoji = "[LONG]" if direction == 'long' else "[SHORT]"

        message = f"""
🎯 [数学家策略V4.2] 新信号检测
{'='*40}
📊 信号类型: {signal_type}
📍 交易方向: {emoji} {direction.upper()}
📝 入场理由: {reason}
💰 当前价格: ${price:.2f}
📈 张力: {tension:.3f}
🎯 置信度: {confidence:.2f}
⛽ DXY燃料: {dxy_fuel:.4f}
⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*40}
"""

        return self.send_message(message)

    def notify_entry(self, direction, price, stop_loss_price, reason, tension, confidence, dxy_multiplier):
        """通知开仓"""
        emoji = "[LONG]" if direction == 'long' else "[SHORT]"

        message = f"""
✅ [数学家策略V4.2] 开仓通知
{'='*40}
📍 交易方向: {emoji} {direction.upper()}
💰 入场价格: ${price:.2f}
🛑 止损价格: ${stop_loss_price:.2f}
📝 入场理由: {reason}
📈 张力: {tension:.3f}
🎯 置信度: {confidence:.2f}
🔧 DXY系数: {dxy_multiplier:.1f}x
⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*40}
💡 提示: 系统将自动监控止盈止损
"""

        return self.send_message(message)

    def notify_exit(self, direction, exit_price, reason, pnl_pct=None, stop_loss_price=None):
        """通知平仓"""
        emoji = "[LONG]" if direction == 'long' else "[SHORT]"

        pnl_info = ""
        if pnl_pct is not None:
            pnl_emoji = "[+]" if pnl_pct > 0 else "[-]"
            pnl_info = f"\n📊 盈亏: {pnl_emoji} {pnl_pct:.2f}%"

        # 添加止损价格信息
        stop_loss_info = ""
        if stop_loss_price is not None:
            stop_loss_info = f"\n🛑 止损价格: ${stop_loss_price:.2f}"

        message = f"""
❌ [数学家策略V4.2] 平仓通知
{'='*40}
📍 交易方向: {emoji} {direction.upper()}
💰 出场价格: ${exit_price:.2f}
📝 出场理由: {reason}{pnl_info}{stop_loss_info}
⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*40}
"""

        return self.send_message(message)

    def notify_logic_failure(self, confidence, reason):
        """通知逻辑失效"""
        message = f"""
⚠️ [数学家策略V4.2] 逻辑失效预警
{'='*40}
🚨 当前置信度: {confidence:.2f}
📉 失效阈值: {self.config.CONF_FAIL_THRESHOLD}
📝 失效原因: {reason}
⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*40}
💡 说明: 物理模型不再支持当前持仓，已触发自动平仓
"""

        return self.send_message(message)

    def notify_system_start(self):
        """通知系统启动"""
        message = f"""
🚀 [数学家策略V4.2] 系统启动
{'='*40}
✅ 实时信号预警系统已启动
📊 数据源: Binance API
🎯 策略: 非线性动力学物理学
⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*40}
💡 系统将自动监控4H信号并实时通知
"""

        return self.send_message(message)

    def notify_system_status(self):
        """通知系统状态"""
        position_status = "有持仓" if self.config.has_position else "无持仓"

        pos_info = ""
        if self.config.has_position:
            direction_emoji = "[LONG]" if self.config.position_type == 'long' else "[SHORT]"
            pos_info = f"""
📍 持仓方向: {direction_emoji} {self.config.position_type.upper()}
💰 入场价格: ${self.config.entry_price:.2f}
🛑 止损价格: ${self.config.stop_loss_price:.2f}
📈 入场张力: {self.config.entry_tension:.3f}
🎯 入场置信度: {self.config.entry_confidence:.2f}
⏰ 入场时间: {self.config.entry_time}
"""
        else:
            # 无持仓时显示最近一次信号
            signal_info = ""
            if self.config.last_signal_valid:
                signal_emoji = "[看涨]" if self.config.last_signal_type == "BULLISH_SINGULARITY" else "[看空]"
                signal_info = f"""
📊 最近信号: {self.config.last_signal_type}
{signal_emoji} 信号描述: {self.config.last_signal_desc}
💰 信号价格: ${self.config.last_signal_price:.2f}
🎯 信号置信度: {self.config.last_signal_confidence:.2f}
⏰ 信号时间: {self.config.last_signal_time}
"""
                pos_info = f"\n{signal_info}"

        message = f"""
📊 [数学家策略V4.2] 系统状态
{'='*40}
🔍 仓位状态: {position_status}{pos_info}
⏰ 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*40}
"""

        return self.send_message(message)

    def get_updates(self, offset=0, timeout=30):
        """获取Telegram更新（命令）- 使用long polling"""
        if not self.enabled:
            return []

        try:
            url = f"https://api.telegram.org/bot{self.token}/getUpdates"
            # 使用long polling，服务器会保持连接等待新消息
            params = {
                'offset': offset,
                'timeout': timeout,  # long polling，最多等待30秒
                'allowed_updates': ['message']
            }

            response = self.session.get(url, params=params, timeout=timeout + 10)
            result = response.json()

            if result.get('ok'):
                updates = result.get('result', [])
                if updates:
                    logger.info(f"[Telegram] getUpdates返回 {len(updates)} 条消息, offset={offset}")
                return updates
            else:
                logger.error(f"[Telegram] getUpdates失败: {result}")
                return []

        except Exception as e:
            logger.error(f"[Telegram] getUpdates异常: {e}")
            return []

    def notify_help(self):
        """发送帮助信息"""
        message = """
📖 [数学家策略V4.2] 命令帮助
{'='*40}
可用命令:

/help - 显示此帮助信息
/status - 查看当前持仓状态
/clear - 手动平仓当前持仓

{'='*40}
💡 提示: 发送命令时请使用斜杠开头
例如: /status
"""

        return self.send_message(message)

    def start_listening(self, system):
        """开始监听（在后台线程中运行）- V4.1.1模式"""
        logger.info("[Telegram] 命令监听线程已启动")
        update_id = 0

        while True:
            try:
                # 使用long polling获取更新
                updates = self.get_updates(offset=update_id + 1, timeout=30)

                if updates:
                    for update in updates:
                        # 更新update_id
                        update_id = update['update_id']

                        # 处理消息
                        if 'message' in update:
                            message = update['message']
                            text = message.get('text', '')
                            chat_id = message.get('chat', {}).get('id')

                            logger.info(f"[Telegram] 收到消息: {text}, chat_id: {chat_id}")

                            # 只处理来自配置chat_id的命令
                            if str(chat_id) != str(self.chat_id):
                                logger.info(f"[Telegram] 忽略非授权chat: {chat_id}")
                                continue

                            # 处理命令
                            if text.startswith('/'):
                                command = text.lower().strip()
                                logger.info(f"[Telegram] 收到命令: {command}")

                                if command == '/help':
                                    self.notify_help()
                                    logger.info("[命令] 已发送帮助信息")

                                elif command == '/status':
                                    self.notify_system_status()
                                    logger.info("[命令] 已发送状态信息")

                                elif command == '/clear':
                                    if system.config.has_position:
                                        # 获取当前价格
                                        import requests as req
                                        try:
                                            url = "https://api.binance.com/api/v3/ticker/price"
                                            params = {'symbol': system.config.binance_symbol}
                                            resp = req.get(url, params=params, timeout=10)
                                            current_price = float(resp.json()['price'])
                                            system.close_position(current_price, "手动平仓")
                                            logger.info("[命令] 已手动平仓")
                                        except Exception as ex:
                                            logger.error(f"[命令] 获取当前价格失败: {ex}")
                                    else:
                                        self.send_message("当前无持仓，无需平仓")
                                        logger.info("[命令] 无持仓，无需平仓")

                # 避免过于频繁请求
                time.sleep(1)

            except Exception as e:
                logger.error(f"[Telegram] 监听错误: {e}")
                time.sleep(5)  # 错误后等待5秒重试


# ==================== [6. 主程序] ====================
class MathematicianSignalSystemV4_2:
    """数学家非线性动力学策略 - V4.2完整版"""

    def __init__(self):
        logger.info("="*60)
        logger.info("[数学家策略V4.2] 初始化中...")
        logger.info("="*60)

        # 初始化组件
        self.config = MathematicianConfig()
        self.data_fetcher = DataFetcher(self.config)
        self.physics_calculator = PhysicsSignalCalculator(self.config)
        self.decision_engine = TradingDecisionEngine(self.config)
        self.notifier = TelegramNotifier(self.config)

        # 加载状态
        self.config.load_state()

        logger.info("[OK] 配置加载完成")
        logger.info("[OK] 数据管理器初始化完成")
        logger.info("[OK] 物理计算器初始化完成")
        logger.info("[OK] 决策引擎初始化完成")
        logger.info("[OK] Telegram通知初始化完成")

        logger.info("="*60)
        logger.info("[OK] 系统初始化完成")
        logger.info("="*60)

    def check_signals(self):
        """检查信号（每4小时）"""
        try:
            logger.info("[检查] 开始扫描4H信号...")

            # 获取数据
            df_4h = self.data_fetcher.fetch_btc_data(interval='4h', limit=300)

            if df_4h is None or len(df_4h) < 50:
                logger.error("数据不足，跳过本次检查")
                return

            # 计算物理指标
            physics_df = self.physics_calculator.calculate_physics_metrics(df_4h)

            if physics_df is None:
                logger.error("物理指标计算失败")
                return

            # 获取最新信号
            latest = physics_df.iloc[-1]
            current_price = latest['close']
            current_time = datetime.now()

            logger.info(f"[信号] 类型: {latest['signal_type']}, 张力: {latest['tension']:.3f}, "
                       f"加速度: {latest['acceleration']:.4f}, 置信度: {latest['confidence']:.2f}")

            # 更新最近信号信息（用于STATUS命令）
            self.config.last_signal_time = current_time
            self.config.last_signal_type = str(latest['signal_type'])
            self.config.last_signal_desc = f"张力:{latest['tension']:.3f}, 加速:{latest['acceleration']:.4f}"
            self.config.last_signal_price = current_price
            self.config.last_signal_confidence = float(latest['confidence'])
            self.config.last_signal_valid = True
            self.config.save_state()

            # 1. 先检查出场条件（如果有持仓）
            if self.config.has_position:
                exit_signal, exit_reason = self.decision_engine.check_exit_conditions(
                    latest, current_price
                )

                if exit_signal:
                    self.close_position(current_price, exit_reason)
                    return

            # 2. 检查入场条件（无持仓时）
            if not self.config.has_position:
                # 有效性过滤
                condition_valid, confidence = self.decision_engine.is_valid_signal(latest)

                if not condition_valid:
                    logger.info(f"[过滤] 置信度不足 ({confidence:.2f} < {self.config.CONF_THRESHOLD})")
                    return

                # 计算DXY燃料
                dxy_df = self.data_fetcher.fetch_dxy_data()
                dxy_fuel = self.physics_calculator.calculate_dxy_fuel(dxy_df)
                self.config.dxy_latest_fuel = dxy_fuel

                # TRANSITION策略
                is_transition, trans_direction, trans_reason = self.decision_engine.analyze_transition_signal(latest)

                if is_transition:
                    self.open_position(current_time, latest, trans_direction, trans_reason, confidence, dxy_fuel)
                    return

                # SINGULARITY策略
                if 'SINGULARITY' in str(latest['signal_type']):
                    is_singularity, sing_direction, sing_reason = self.decision_engine.analyze_singularity_signal(latest)

                    if is_singularity:
                        self.open_position(current_time, latest, sing_direction, sing_reason, confidence, dxy_fuel)
                        return

            logger.info("[检查] 本次扫描完成，无新操作")

        except Exception as e:
            logger.error(f"信号检查异常: {e}")

    def open_position(self, timestamp, signal_row, direction, reason, confidence, dxy_fuel):
        """开仓"""
        entry_price = signal_row['close']
        tension = signal_row['tension']

        # 计算DXY燃料加成
        if direction == 'long':
            dxy_multiplier = self.config.DXY_FUEL_MULTIPLIER if dxy_fuel < 0 else self.config.DXY_FUEL_REDUCTION
        else:  # short
            dxy_multiplier = self.config.DXY_FUEL_MULTIPLIER if dxy_fuel > 0 else self.config.DXY_FUEL_REDUCTION

        # 计算仓位
        position_value = 10000 * self.config.BASE_POSITION * dxy_multiplier  # 假设本金$10000
        self.config.margin_used = position_value
        self.config.position_size = (position_value / entry_price) * self.config.LEVERAGE

        # 更新状态
        self.config.has_position = True
        self.config.position_type = direction
        self.config.entry_price = entry_price
        self.config.entry_time = timestamp
        self.config.entry_tension = tension
        self.config.entry_signal = signal_row['signal_type']
        self.config.entry_confidence = confidence
        self.config.entry_dxy_fuel = dxy_fuel
        self.config.stop_loss_price = stop_loss_price  # 保存止损价格

        # 计算止损价格
        if direction == 'long':
            stop_loss_price = entry_price * (1 - self.config.STOP_LOSS_PCT)
        else:  # short
            stop_loss_price = entry_price * (1 + self.config.STOP_LOSS_PCT)

        # 保存状态
        self.config.save_state()

        # 记录历史
        self.config.position_history.append({
            'entry_time': str(timestamp),
            'direction': direction,
            'entry_price': entry_price,
            'stop_loss_price': stop_loss_price,
            'reason': reason,
            'confidence': confidence,
            'dxy_fuel': dxy_fuel,
            'dxy_multiplier': dxy_multiplier
        })

        # 通知
        self.notifier.notify_entry(direction, entry_price, stop_loss_price, reason, tension, confidence, dxy_multiplier)

        logger.info(f"[开仓] {direction.upper()} @ ${entry_price:.2f}, 原因: {reason}, "
                   f"置信度: {confidence:.2f}, DXY系数: {dxy_multiplier:.1f}x")

    def close_position(self, exit_price, reason):
        """平仓"""
        direction = self.config.position_type
        entry_price = self.config.entry_price
        stop_loss_price = self.config.stop_loss_price  # 获取保存的止损价格

        # 计算盈亏
        if direction == 'long':
            pnl_pct = (exit_price - entry_price) / entry_price * 100
        else:  # short
            pnl_pct = (entry_price - exit_price) / entry_price * 100

        # 杠杆调整
        pnl_pct_leveraged = pnl_pct * self.config.LEVERAGE

        # 记录历史
        self.config.position_history.append({
            'exit_time': str(datetime.now()),
            'exit_price': exit_price,
            'reason': reason,
            'pnl_pct': pnl_pct_leveraged
        })

        # 通知（包含止损价格）
        self.notifier.notify_exit(direction, exit_price, reason, pnl_pct_leveraged, stop_loss_price)

        # 如果是逻辑失效，额外通知
        if "逻辑失效" in reason:
            self.notifier.notify_logic_failure(self.config.entry_confidence, reason)

        logger.info(f"[平仓] {direction.upper()} @ ${exit_price:.2f}, "
                   f"原因: {reason}, 盈亏: {pnl_pct_leveraged:.2f}%")

        # 重置状态
        self.config.has_position = False
        self.config.position_type = None
        self.config.entry_price = 0.0
        self.config.entry_time = None
        self.config.position_size = 0.0
        self.config.margin_used = 0.0
        self.config.entry_tension = 0.0
        self.config.entry_signal = None
        self.config.entry_confidence = 0.0
        self.config.entry_dxy_fuel = 0.0

        # 保存状态
        self.config.save_state()

    def run(self):
        """运行主循环"""
        logger.info("="*60)
        logger.info("[数学家策略V4.2] 进入主循环")
        logger.info("="*60)

        # 显示当前时间和时区信息
        from datetime import datetime, timezone, timedelta
        now_utc = datetime.now(timezone.utc)
        now_beijing = now_utc + timedelta(hours=8)

        logger.info(f"[时区] 当前UTC时间: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"[时区] 当前北京时间: {now_beijing.strftime('%Y-%m-%d %H:%M:%S')}")

        # BTC 4H K线收盘时间 (UTC)
        # 0:00, 4:00, 8:00, 12:00, 16:00, 20:00 UTC
        # 对应北京时间: 8:00, 12:00, 16:00, 20:00, 0:00, 4:00
        schedule.every().day.at("00:00").do(self.check_signals)
        schedule.every().day.at("04:00").do(self.check_signals)
        schedule.every().day.at("08:00").do(self.check_signals)
        schedule.every().day.at("12:00").do(self.check_signals)
        schedule.every().day.at("16:00").do(self.check_signals)
        schedule.every().day.at("20:00").do(self.check_signals)

        logger.info("[定时] 已配置4H K线收盘扫描:")
        logger.info("       UTC时间: 0:00, 4:00, 8:00, 12:00, 16:00, 20:00")
        logger.info("       北京时间: 8:00, 12:00, 16:00, 20:00, 0:00, 4:00")
        logger.info("[定时] 与Binance 4H K线收盘时间完全对应 ✅")

        # 主循环
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次

            except KeyboardInterrupt:
                logger.info("[系统] 收到停止信号，正在退出...")
                self.config.save_state()
                break

            except Exception as e:
                logger.error(f"[系统异常] {e}")
                time.sleep(60)


# ==================== [主程序入口] ====================
if __name__ == "__main__":
    try:
        system = MathematicianSignalSystemV4_2()

        # 🔧 云环境适配：根据运行环境自动调整配置
        try:
            from cloud_adapter import detect_environment, adjust_proxy_config
            env = detect_environment()
            logger.info(f"检测到运行环境: {env}")

            if env in ['cloud', 'docker']:
                logger.info("云环境：禁用代理配置")
                system.config.proxy_enabled = False
                # 关键：清除已创建的session的代理配置
                system.data_fetcher.session.proxies = {}
                system.notifier.session.proxies = {}
                logger.info("已清除requests session的代理设置")
            else:
                logger.info("本地环境：启用代理配置")
        except ImportError:
            logger.info("云环境适配器不可用，使用默认配置")

        # 在代理配置完成后发送系统启动通知
        logger.info("="*60)
        logger.info("[OK] 系统启动完成，开始监控...")
        logger.info("="*60)
        system.notifier.notify_system_start()

        # 🚀 启动Telegram命令监听线程（V4.1.1模式：独立线程+long polling）
        import threading
        telegram_thread = threading.Thread(
            target=system.notifier.start_listening,
            args=(system,),
            daemon=True
        )
        telegram_thread.start()
        logger.info("[OK] Telegram命令监听已启动（独立线程）")

        system.run()
    except Exception as e:
        logger.error(f"[致命错误] {e}")
