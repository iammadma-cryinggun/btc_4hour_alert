# -*- coding: utf-8 -*-
"""
🎮 物理奇点实时预警系统 V4.1 Smart Ape Edition
🚀 基于V3.1完整功能 + Smart Ape动态风险管理
📊 核心特性：
   - 完整仓位追踪（V3.1的PositionTracker）
   - EMA21入场机制（V3.1的战备模式）
   - Telegram交互控制（V3.1的命令处理 + V4.1手动加仓）
   - Smart Ape动态风险管理（黄金阈值 + 逻辑失效止损 + 爆仓潮止盈）

💡 仓位配置（V4.1人机结合版）：
   - 基础仓位：30% = 首次15% + 手动加仓15%
   - Smart Ape黄金阈值：空单LS<2.0跳过（+4.5%收益）
   - 逻辑失效止损：LS变化±0.5 + OI下降-10%
   - 爆仓潮止盈：清算量>95分位（$7,020,640）
   - 回测收益：+803% (2年，Smart Ape版)

🎯 V4.1 Smart Ape升级亮点：
   ⭐ 黄金阈值过滤（空单LS<2.0跳过低胜率交易）
   ⭐ 逻辑失效止损（市场逻辑变化时及时退出）
   ⭐ 爆仓潮止盈（极端行情锁定利润）
   ⭐ 人机结合（首次自动15% + Telegram手动加仓15%）
   ⭐ 收益率提升4.5% (768% → 803%)
   ⭐ 完全移除无效的方案A2系统
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
        logging.FileHandler('physics_alert_v3_1_complete.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== [交易历史记录系统] ====================
class TradeHistoryTracker:
    """交易历史追踪器 - 记录所有已完成的交易"""

    def __init__(self, history_file='trade_history.json'):
        self.history_file = history_file
        self.trades = self.load_history()

    def load_history(self):
        """加载交易历史"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"   加载交易历史失败: {e}")
                return []
        return []

    def save_history(self):
        """保存交易历史"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.trades, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存交易历史失败: {e}")

    def add_trade(self, trade_id, entry_time, exit_time, signal_type, position_type,
                  entry_price, exit_price, profit_pct, profit_amount, exit_reason,
                  hold_hours, peak_profit_pct, tp1_hit, trailing_activated,
                  position_size_pct, initial_sl, final_sl, tp1_price, tp2_price):
        """添加一笔交易记录"""
        trade = {
            'trade_id': trade_id,
            'entry_time': entry_time.isoformat(),
            'exit_time': exit_time.isoformat(),
            'signal_type': signal_type,
            'position_type': position_type,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'profit_pct': round(profit_pct, 2),
            'profit_amount': round(profit_amount, 2),
            'exit_reason': exit_reason,
            'hold_hours': round(hold_hours, 2),
            'peak_profit_pct': round(peak_profit_pct, 2),
            'tp1_hit': tp1_hit,
            'trailing_activated': trailing_activated,
            'position_size_pct': position_size_pct,
            'initial_sl': initial_sl,
            'final_sl': final_sl,
            'tp1_price': tp1_price,
            'tp2_price': tp2_price
        }
        self.trades.append(trade)
        self.save_history()
        return trade

    def print_summary(self):
        """打印交易摘要"""
        if not self.trades:
            print("   暂无交易历史")
            return

        total = len(self.trades)
        wins = sum(1 for t in self.trades if t['profit_pct'] > 0)
        total_pct = sum(t['profit_pct'] for t in self.trades)
        avg_pct = total_pct / total

        print(f"\n{'='*80}")
        print(f"   交易历史统计: {total}笔 | 胜率: {wins/total*100:.1f}% | 总收益: {total_pct:+.2f}% | 平均: {avg_pct:+.2f}%")
        print(f"{'='*80}\n")

# ==================== [1. 配置类 - V4.1 Smart Ape版] ====================
class PhysicsSignalConfigV4_1:
    """物理奇点信号配置 - V4.1 Smart Ape版（V3.1完整功能 + Smart Ape动态风险管理）"""

    def __init__(self):
        # 🎯 物理参数（与回测完全一致）
        self.TENSION_THRESHOLD = 0.35
        self.ACCEL_THRESHOLD = 0.02
        self.OSCILLATION_BAND = 0.5

        # 🎯 V4.1人机结合版：30%仓位配置（15%首次 + 15%手动加仓）
        self.base_position_ratio = 0.30  # 基础仓位30%（15%首次 + 15%手动加仓）
        self.position_multiplier = 1.0     # 当前仓位乘数（暂不使用动态调整）

        # 🎯 V4.1：仓位计算逻辑（人机结合模式）
        # 首次开仓 = base_position_ratio × 0.5 = 30% × 0.5 = 15%
        # 手动加仓 = base_position_ratio × 0.5 = 30% × 0.5 = 15%（操作者通过Telegram手动加仓）
        # 总仓位 = base_position_ratio = 30%
        # 示例：首次开仓15% → Telegram提醒加仓 → 操作者手动加仓15% → 总30%

        # 🎯 止盈止损方案（与回测一致）
        self.sl_pct = 2.5
        self.tp1_pct = 5.0
        self.tp2_pct = 12.0
        self.trail_offset_pct = 1.5
        self.trail_after_tp1 = True
        self.flip_to_breakeven = False

        # 🎯 V3.1：三维动态风险阈值（从历史数据总结）
        # 第一级：极端异常（0%仓位）
        self.oi_growth_extreme = 0.20   # OI增长率20%
        self.funding_monthly_extreme = 0.03   # FR月均值3%

        # 第二级：轻度风险（25%-50%仓位）
        self.oi_growth_moderate = 0.10   # OI增长率10%
        self.funding_monthly_moderate = 0.02   # FR月均值2%

        # 🎯 V3.1新增：FR_CV阈值
        self.fr_cv_high = 1.0      # 高波动阈值（用于轻度风险分级）
        self.fr_cv_normal = 1.5    # 正常波动阈值（用于正常月份分级）

        # 🎯 滑点和费用
        self.base_slippage = 0.001
        self.max_slippage = 0.005
        self.taker_fee = 0.0004

        # 代理配置（云端环境自动禁用）
        import os
        # 检测是否在云端环境（Zeabur等）
        self.is_cloud_env = os.getenv('ZEABUR') is not None or os.getenv('CLOUD_ENV') is not None

        self.proxy_host = "127.0.0.1"
        self.proxy_port = "15236"
        self.proxy_http = f"http://{self.proxy_host}:{self.proxy_port}"
        self.proxy_https = f"http://{self.proxy_host}:{self.proxy_port}"

        # 如果检测到云端环境，禁用代理
        self.proxy_enabled = True and not self.is_cloud_env

        # 自动测试代理连接（如果启用的话）
        if self.proxy_enabled and not self.is_cloud_env:
            try:
                import requests
                test_url = "https://api.binance.com/api/v3/ping"
                test_proxies = {'http': self.proxy_http, 'https': self.proxy_https}
                # 设置超时时间为2秒
                response = requests.get(test_url, proxies=test_proxies, timeout=2)
                # 如果连接成功，保持代理启用
            except Exception as e:
                # 代理连接失败，自动禁用代理
                print(f'⚠️ 代理连接失败: {e}')
                print(f'🔄 自动禁用代理，使用直连')
                self.proxy_enabled = False
                self.is_cloud_env = True  # 标记为云端/无代理环境

        # Telegram配置
        self.telegram_token = "8189663571:AAEvIUEBTfF_MfyKc7rWq5gQvgi4gAxZJrA"
        self.telegram_chat_id = "838429342"

        # 微信Server酱配置
        self.wechat_sckey = "SCT307134TCw1AtdGtadVA7CZhRklB0ptp"

        # 数据源
        self.binance_symbol = "BTCUSDT"
        self.timeframe_4h = "4h"
        self.timeframe_15m = "15m"

        # Coinalyze API配置
        self.coinalyze_api_key = "cd4bfa05-9951-4916-b02a-e4f45f992bc0"
        self.coinalyze_base_url = "https://api.coinalyze.net/v1"  # 修复：添加/v1前缀

        # Coinglass API配置（备用）
        self.coinglass_api_key = "04c3a7ffe78d4249968a1886f8e7af1a"
        self.coinglass_base_url = "https://open-api.coinglass.com"

        # 🎯 V3.1：运行频率配置
        self.normal_check_interval = 240      # 4小时检查物理信号
        self.battle_check_interval = 1        # 战备模式：每分钟检查
        self.position_check_interval = 1      # 仓位监控：每分钟
        self.risk_check_interval = 60         # 风险监控：每小时检查

        # 🎯 战备状态
        self.battle_mode = False
        self.battle_start_time = None
        self.battle_signal_type = None
        self.battle_regime_desc = ""
        self.battle_signal_price = 0.0
        self.battle_signal_confidence = 0.0
        self.battle_duration_hours = 8
        self.battle_check_count = 0

        # 🎯 最新信号
        self.last_signal_time = None
        self.last_signal_type = None
        self.last_signal_desc = ""
        self.last_signal_price = 0.0
        self.last_signal_confidence = 0.0

        # 🎯 仓位状态（V2完整版）
        self.has_position = False
        self.position_type = None
        self.entry_price = 0.0
        self.effective_entry_price = 0.0
        self.initial_entry_price = 0.0
        self.entry_time = None
        self.position_size_pct = 0.0
        self.position_quantity = 0.0
        self.add_position_taken = False
        self.entry_regime = None

        # 🎯 止盈止损
        self.stop_loss_price = 0.0
        self.initial_stop_loss_price = 0.0
        self.breakeven_price = 0.0
        self.tp1_price = 0.0
        self.tp2_price = 0.0
        self.trailing_stop_price = 0.0
        self.tp1_hit = False
        self.trailing_activated = False
        self.breakeven_triggered = False

        # 峰值记录
        self.peak_price = 0.0
        self.peak_profit_pct = 0.0
        self.max_floating_profit = 0.0
        self.max_floating_pct = 0.0

        # 🎯 原始趋势信息（混合策略）
        self.original_tp1_price = 0.0
        self.original_tp2_price = 0.0
        self.original_regime = None
        self.original_direction = None
        self.original_signal_time = None
        self.trend_continuation_count = 0
        self.original_tp_reached = False

        # 🎯 V3.1：风险状态（5级）
        self.current_risk_level = "NORMAL"  # EXTREME / MODERATE_HIGH / MODERATE / NORMAL_CAUTIOUS / NORMAL
        self.last_risk_check_time = None
        self.risk_warning_history = deque(maxlen=100)  # 保留最近100条风险预警

        # 🎯 V4.1 Smart Ape配置（黄金阈值 + 逻辑止损 + 爆仓潮止盈）
        # 黄金阈值配置（只用于空单BULLISH信号）
        self.GOLDEN_THRESHOLD_SHORT = 2.0  # 空单LS阈值（LS < 2.0跳过，+4.5%收益）
        self.GOLDEN_THRESHOLD_SHORT_SKIP = 2.0  # 低于此值跳过

        # 逻辑失效止损配置
        self.LOGIC_FAILURE_LS_CHANGE = 0.5  # LS变化阈值
        self.LOGIC_FAILURE_OI_CHANGE = -0.10  # OI下降阈值（-10%）

        # 爆仓潮止盈配置
        self.LIQUIDATION_FLUSH_95TH = 7020640  # 清算量95分位（2年数据，$7,020,640）

        # Smart Ape监控间隔
        self.smart_ape_check_interval = 60  # Smart Ape检查间隔（秒，每小时）

        # 🎯 V4.1 SKIP过滤配置（极端数值过滤）
        self.enable_skip_filter = True  # 启用SKIP过滤
        self.skip_ls_ratio_threshold = 3.5  # LS-Ratio > 3.5跳过（极端风险）
        self.skip_fr_threshold = -0.02  # FR < -2%跳过（极端负费率）

        # 🎯 V4.1修复：position_sizes字典（用于战备模式通知，与base_position_ratio动态同步）
        # 注意：实际仓位使用base_position_ratio动态计算，这里的字典仅用于显示
        self.position_sizes = {
            "BEARISH_SINGULARITY": 0.15,   # 首次开仓15%（30%×0.5）
            "BULLISH_SINGULARITY": 0.15    # 首次开仓15%（30%×0.5）
        }
        self.add_position_sizes = {
            "BEARISH_SINGULARITY": 0.15,   # 手动加仓15%（通过Telegram命令）
            "BULLISH_SINGULARITY": 0.15    # 手动加仓15%（通过Telegram命令）
        }

# ==================== [2. 增强数据管理器 - 支持OI/FR实时获取] ====================
class EnhancedDataFetcher:
    """增强数据获取器 - 支持Binance + Coinalyze/Coinglass OI/FR数据"""

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

        # 数据缓存
        self.oi_data_cache = deque(maxlen=100)  # OI数据（日线）
        self.fr_data_cache = deque(maxlen=100)  # FR数据（日线）
        self.last_oi_update = None
        self.last_fr_update = None

        # 请求间隔控制
        self.last_request_time = 0
        self.min_request_interval = 0.5

    def _wait_before_request(self):
        """请求前等待，避免请求过于频繁"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last_request
            time.sleep(wait_time)

        self.last_request_time = time.time()

    def fetch_btc_data(self, interval='4h', limit=200):
        """获取BTC K线数据"""
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {
                'symbol': self.config.binance_symbol,
                'interval': interval,
                'limit': limit
            }

            self._wait_before_request()
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

            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            if interval == '15m':
                df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()

            columns = ['open', 'high', 'low', 'close']
            if interval == '15m':
                columns.append('ema21')

            return df[columns].dropna()

        except Exception as e:
            logger.error(f"获取BTC数据失败: {e}")
            return None

    def get_current_btc_price(self):
        """获取当前BTC价格"""
        try:
            url = "https://api.binance.com/api/v3/ticker/price"
            params = {'symbol': self.config.binance_symbol}

            self._wait_before_request()
            resp = self.session.get(url, params=params, timeout=5)
            data = resp.json()

            if 'price' in data:
                return float(data['price'])
            else:
                return None

        except Exception as e:
            logger.error(f"获取当前价格失败: {e}")
            return None

    def fetch_dxy_data(self):
        """获取DXY数据（FRED官方CSV，无需API key）"""
        try:
            # FRED (圣路易斯联储) 提供美元指数DTWEXBGS的CSV下载，无需API key
            # 这是官方且最可靠的数据源
            from io import StringIO

            url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS'

            resp = self.session.get(url, timeout=15)

            if resp.status_code == 200:
                df = pd.read_csv(StringIO(resp.text))
                df['observation_date'] = pd.to_datetime(df['observation_date'])
                df.set_index('observation_date', inplace=True)
                df.rename(columns={'DTWEXBGS': 'Close'}, inplace=True)
                df['Close'] = pd.to_numeric(df['Close'])
                df = df.dropna()

                # 只保留最近60天的数据
                from datetime import timedelta
                cutoff_date = datetime.now() - timedelta(days=90)
                df = df[df.index >= cutoff_date]

                logger.info(f"DXY数据获取成功 (FRED官方, {len(df)}条)")
                return df[['Close']].sort_index()
            else:
                logger.warning(f"FRED返回错误: HTTP {resp.status_code}")
                return None

        except Exception as e:
            logger.warning(f"DXY数据获取失败: {e}")

        return None

    def fetch_coinalyze_oi(self, symbol="BTCUSD_PERP.A", days=35):
        """获取Coinalyze OI数据（最近35天）"""
        try:
            # 计算时间范围
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            to_ts = int(to_date.timestamp())
            from_ts = int(from_date.timestamp())

            # 使用历史数据API（正确的端点和参数格式）
            url = f"{self.config.coinalyze_base_url}/open-interest-history"
            params = {
                'symbols': symbol,          # 注意：是symbols（复数）
                'interval': 'daily',         # 注意：是daily不是1D
                'from': from_ts,             # 时间戳（秒）
                'to': to_ts                  # 时间戳（秒）
            }

            headers = {
                'Authorization': f'Bearer {self.config.coinalyze_api_key}'
            }

            self._wait_before_request()
            resp = self.session.get(url, params=params, headers=headers, timeout=10)

            # 详细日志
            logger.info(f"Coinalyze OI请求: URL={url}, Status={resp.status_code}")

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    # 返回格式：[{"symbol": "...", "history": [...]}]
                    if data and len(data) > 0 and 'history' in data[0]:
                        history = data[0]['history']
                        df = pd.DataFrame(history)
                        df['datetime'] = pd.to_datetime(df['t'], unit='s')
                        self.oi_data_cache.clear()
                        self.oi_data_cache.extend(df.to_dict('records'))
                        self.last_oi_update = datetime.now()
                        logger.info(f"成功获取OI数据: {len(df)}条")
                        return df
                    else:
                        logger.warning(f"Coinalyze OI数据格式异常: {str(data)[:200]}")
                except json.JSONDecodeError as je:
                    logger.error(f"Coinalyze OI JSON解析失败: {je}")
                    logger.error(f"响应内容: {resp.text[:500]}")
            else:
                logger.warning(f"Coinalyze OI API返回: {resp.status_code} - {resp.text[:200]}")

        except Exception as e:
            logger.error(f"获取Coinalyze OI失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return None

    def fetch_coinalyze_funding_rate(self, symbol="BTCUSD_PERP.A", days=35):
        """获取Coinalyze资金费率数据（最近35天）"""
        try:
            # 计算时间范围
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            to_ts = int(to_date.timestamp())
            from_ts = int(from_date.timestamp())

            # 使用历史数据API（正确的端点和参数格式）
            url = f"{self.config.coinalyze_base_url}/funding-rate-history"
            params = {
                'symbols': symbol,          # 注意：是symbols（复数）
                'interval': 'daily',         # 注意：是daily不是1D
                'from': from_ts,             # 时间戳（秒）
                'to': to_ts                  # 时间戳（秒）
            }

            headers = {
                'Authorization': f'Bearer {self.config.coinalyze_api_key}'
            }

            self._wait_before_request()
            resp = self.session.get(url, params=params, headers=headers, timeout=10)

            # 详细日志
            logger.info(f"Coinalyze FR请求: URL={url}, Status={resp.status_code}")

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    # 返回格式：[{"symbol": "...", "history": [...]}]
                    if data and len(data) > 0 and 'history' in data[0]:
                        history = data[0]['history']
                        df = pd.DataFrame(history)
                        df['datetime'] = pd.to_datetime(df['t'], unit='s')
                        self.fr_data_cache.clear()
                        self.fr_data_cache.extend(df.to_dict('records'))
                        self.last_fr_update = datetime.now()
                        logger.info(f"成功获取FR数据: {len(df)}条")
                        return df
                    else:
                        logger.warning(f"Coinalyze FR数据格式异常: {str(data)[:200]}")
                except json.JSONDecodeError as je:
                    logger.error(f"Coinalyze FR JSON解析失败: {je}")
                    logger.error(f"响应内容: {resp.text[:500]}")
            else:
                logger.warning(f"Coinalyze FR API返回: {resp.status_code} - {resp.text[:200]}")

        except Exception as e:
            logger.error(f"获取Coinalyze FR失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return None

    def get_latest_ls_ratio(self):
        """获取最新LS-Ratio（从Coinglass API）"""
        try:
            # Coinglass API for Long/Short Ratio
            url = "https://api.coinglass.com/api/v1/long_short_ratio"
            params = {
                'symbol': 'BTCUSDT',
                'interval': '1h'
            }

            headers = {
                'User-Agent': 'Mozilla/5.0'
            }

            self._wait_before_request()
            resp = self.session.get(url, params=params, headers=headers, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                if data and 'data' in data and len(data['data']) > 0:
                    # Coinglass返回最新的LS-Ratio
                    latest = data['data'][0]
                    ls_ratio = float(latest.get('longShortRatio', 0))
                    logger.info(f"成功获取LS-Ratio: {ls_ratio:.2f}")
                    return ls_ratio
                else:
                    logger.warning(f"Coinglass LS-Ratio数据格式异常")
            else:
                logger.warning(f"Coinglass LS-Ratio API返回: {resp.status_code}")

        except Exception as e:
            logger.error(f"获取LS-Ratio失败: {e}")

        return None

    def get_latest_fr(self):
        """获取最新资金费率（从缓存或API）"""
        try:
            # 优先从缓存获取最新的FR
            if len(self.fr_data_cache) > 0:
                latest_record = self.fr_data_cache[-1]
                fr = latest_record.get('c', 0)
                logger.info(f"从缓存获取FR: {fr*100:.4f}%")
                return fr

            # 缓存为空，重新获取
            if self.last_fr_update is None or (datetime.now() - self.last_fr_update).total_seconds() > 3600:
                df = self.fetch_coinalyze_funding_rate()
                if df is not None and len(df) > 0:
                    latest_record = self.fr_data_cache[-1]
                    fr = latest_record.get('c', 0)
                    return fr

        except Exception as e:
            logger.error(f"获取FR失败: {e}")

        return None

    def get_latest_oi(self):
        """获取最新OI（从缓存或API）"""
        try:
            # 优先从缓存获取最新的OI
            if len(self.oi_data_cache) > 0:
                latest_record = self.oi_data_cache[-1]
                oi = latest_record.get('c', 0)
                logger.info(f"从缓存获取OI: {oi:.0f}")
                return oi

            # 缓存为空，重新获取
            if self.last_oi_update is None or (datetime.now() - self.last_oi_update).total_seconds() > 3600:
                df = self.fetch_coinalyze_oi()
                if df is not None and len(df) > 0:
                    latest_record = self.oi_data_cache[-1]
                    oi = latest_record.get('c', 0)
                    return oi

        except Exception as e:
            logger.error(f"获取OI失败: {e}")

        return None

    # Alias methods for compatibility with Smart Ape code
    def fetch_ls_ratio(self):
        """别名方法，用于Smart Ape兼容性"""
        return self.get_latest_ls_ratio()

    def fetch_oi(self):
        """别名方法，用于Smart Ape兼容性"""
        return self.get_latest_oi()

    def fetch_liquidation_both(self):
        """获取多空清算量（从Coinglass API）"""
        try:
            url = "https://api.coinglass.com/api/v1/liquidation_chart"
            params = {
                'symbol': 'BTCUSDT',
                'interval': '1h'
            }

            headers = {
                'User-Agent': 'Mozilla/5.0'
            }

            self._wait_before_request()
            resp = self.session.get(url, params=params, headers=headers, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                if data and 'data' in data and len(data['data']) > 0:
                    latest = data['data'][0]
                    long_liq = float(latest.get('longLiquidation', 0))
                    short_liq = float(latest.get('shortLiquidation', 0))
                    logger.info(f"成功获取清算量: 多${long_liq:,.0f}, 空${short_liq:,.0f}")
                    return long_liq, short_liq
                else:
                    logger.warning(f"Coinglass清算数据格式异常")
            else:
                logger.warning(f"Coinglass清算API返回: {resp.status_code}")

        except Exception as e:
            logger.error(f"获取清算数据失败: {e}")

        return None, None

    def get_monthly_features(self):
        """计算当前月度特征（OI增长率、FR均值、FR_CV）"""
        try:
            if len(self.oi_data_cache) < 2 or len(self.fr_data_cache) < 2:
                logger.warning("OI或FR数据不足，无法计算月度特征")
                return None

            # 转换为DataFrame
            oi_df = pd.DataFrame(list(self.oi_data_cache))
            fr_df = pd.DataFrame(list(self.fr_data_cache))

            # 获取最近30天的数据（当月）
            oi_df = oi_df.tail(30)
            fr_df = fr_df.tail(30)

            # 计算OI增长率
            oi_start = oi_df['c'].iloc[0]
            oi_end = oi_df['c'].iloc[-1]
            oi_growth = (oi_end - oi_start) / oi_start if oi_start > 0 else 0

            # 计算FR统计量
            fr_mean = fr_df['c'].mean()
            fr_std = fr_df['c'].std()
            fr_max = fr_df['h'].max()
            fr_min = fr_df['l'].min()

            # 计算FR_CV（变异系数）
            fr_cv = fr_std / abs(fr_mean) if abs(fr_mean) > 1e-6 else 0

            features = {
                'oi_growth': oi_growth,
                'fr_mean': fr_mean,
                'fr_std': fr_std,
                'fr_max': fr_max,
                'fr_min': fr_min,
                'fr_cv': fr_cv,
                'update_time': datetime.now()
            }

            logger.info(f"月度特征计算完成:")
            logger.info(f"  OI增长率: {oi_growth*100:+.2f}%")
            logger.info(f"  FR均值: {fr_mean*100:+.2f}%, FR_CV: {fr_cv:.2f}")
            logger.info(f"  FR峰值: {fr_max*100:+.2f}%")

            return features

        except Exception as e:
            logger.error(f"计算月度特征失败: {e}")
            return None

    def fetch_coinalyze_long_short_ratio(self, symbol="BTCUSD_PERP.A", days=35):
        """获取Coinalyze多空比数据（最近35天）- Smart Ape需要"""
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            to_ts = int(to_date.timestamp())
            from_ts = int(from_date.timestamp())

            url = f"{self.config.coinalyze_base_url}/long-short-ratio-history"
            params = {
                'symbols': symbol,
                'interval': 'daily',
                'from': from_ts,
                'to': to_ts
            }

            headers = {
                'Authorization': f'Bearer {self.config.coinalyze_api_key}'
            }

            self._wait_before_request()
            resp = self.session.get(url, params=params, headers=headers, timeout=10)

            logger.info(f"Coinalyze LS-Ratio请求: URL={url}, Status={resp.status_code}")

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if data and len(data) > 0 and 'history' in data[0]:
                        history = data[0]['history']
                        df = pd.DataFrame(history)
                        df['datetime'] = pd.to_datetime(df['t'], unit='s')

                        if not hasattr(self, 'ls_ratio_cache'):
                            self.ls_ratio_cache = deque(maxlen=100)
                        self.ls_ratio_cache.clear()
                        self.ls_ratio_cache.extend(df.to_dict('records'))

                        logger.info(f"✅ 成功获取LS-Ratio数据: {len(df)}条")
                        return df
                    else:
                        logger.warning(f"Coinalyze LS-Ratio数据格式异常: {str(data)[:200]}")
                except Exception as e:
                    logger.error(f"解析LS-Ratio数据失败: {e}")
            else:
                logger.warning(f"Coinalyze LS-Ratio API返回: {resp.status_code} - {resp.text[:200]}")

        except Exception as e:
            logger.error(f"获取Coinalyze LS-Ratio失败: {e}")

        return None

    def fetch_coinalyze_liquidation(self, symbol="BTCUSD_PERP.A", days=35):
        """获取Coinalyze清算数据（最近35天）- Smart Ape需要"""
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            to_ts = int(to_date.timestamp())
            from_ts = int(from_date.timestamp())

            url = f"{self.config.coinalyze_base_url}/liquidation-history"
            params = {
                'symbols': symbol,
                'interval': 'daily',
                'from': from_ts,
                'to': to_ts
            }

            headers = {
                'Authorization': f'Bearer {self.config.coinalyze_api_key}'
            }

            self._wait_before_request()
            resp = self.session.get(url, params=params, headers=headers, timeout=10)

            logger.info(f"Coinalyze Liquidation请求: URL={url}, Status={resp.status_code}")

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    # API返回格式：[{"symbol": "...", "history": [{"t": 0, "l": 0, "s": 0}]}]
                    if data and len(data) > 0 and 'history' in data[0]:
                        history = data[0]['history']
                        df = pd.DataFrame(history)
                        df['datetime'] = pd.to_datetime(df['t'], unit='s')

                        if not hasattr(self, 'liquidation_cache'):
                            self.liquidation_cache = deque(maxlen=100)
                        self.liquidation_cache.clear()
                        self.liquidation_cache.extend(df.to_dict('records'))

                        # 计算75分位数
                        liq_75pctile = df['l'].quantile(0.75)

                        logger.info(f"✅ 成功获取清算数据: {len(df)}条")
                        logger.info(f"   清算75分位数: ${liq_75pctile:,.0f}")

                        return df, liq_75pctile
                    else:
                        logger.warning(f"Coinalyze清算数据格式异常: {str(data)[:200]}")
                except Exception as e:
                    logger.error(f"解析清算数据失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                logger.warning(f"Coinalyze清算API返回: {resp.status_code} - {resp.text[:200]}")

        except Exception as e:
            logger.error(f"获取Coinalyze清算失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return None, None

# ==================== [2.5. Smart Ape动态风险管理器 - V4.1新增] ====================
class SmartApeRiskManager:
    """
    Smart Ape动态风险管理器（V4.1新增）

    核心功能：
      1. 黄金阈值检查（check_golden_threshold） - 只过滤空单LS < 2.0，+4.5%收益
      2. 逻辑失效止损检查（check_logic_failure_stop） - LS突变 + OI下降
      3. 爆仓潮止盈检查（check_liquidation_flush_tp） - 清算量 > 95分位

    回测验证：
      - 黄金阈值：768% → 803% (+4.5%)
      - 跳过交易：7笔（LS < 2.0的空单）
      - 避免亏损：$3,467
    """

    def __init__(self, config, data_fetcher):
        self.config = config
        self.data_fetcher = data_fetcher

        # 加载历史分位数
        self._load_historical_percentiles()

        logger.info("[Smart Ape] 初始化完成")
        logger.info(f"  黄金阈值(空单): LS >= {self.config.GOLDEN_THRESHOLD_SHORT}")
        logger.info(f"  逻辑止损LS变化: ±{self.config.LOGIC_FAILURE_LS_CHANGE}")
        logger.info(f"  逻辑止损OI变化: {self.config.LOGIC_FAILURE_OI_CHANGE*100:.0f}%")
        logger.info(f"  爆仓潮止盈95分位: ${self.config.LIQUIDATION_FLUSH_95TH:,.0f}")

    def _load_historical_percentiles(self):
        """
        加载历史分位数作为阈值
        注：实际实施时可以从CSV文件加载
        """
        # 清算量分位数（2年数据）
        self.liq_95th = self.config.LIQUIDATION_FLUSH_95TH

        logger.info(f"[Smart Ape] 历史分位数加载完成:")
        logger.info(f"  清算量95分位: ${self.liq_95th:,.0f}")

    def check_golden_threshold(self, signal_type, current_ls_ratio):
        """
        黄金阈值过滤（V4.1新增） - 只用于空单（BULLISH信号）

        回测数据：
          - LS < 2.0的空单：7笔，胜率42.9%，亏损$3,467
          - LS >= 2.0的空单：69笔，胜率69.6%，盈利$27,546

        Args:
            signal_type: "BULLISH_SINGULARITY" (空单) or "BEARISH_SINGULARITY" (多单)
            current_ls_ratio: 当前LS-Ratio值

        Returns:
            (passed, reason): (True, None) or (False, "reason string")
        """
        if signal_type == "BULLISH_SINGULARITY":
            # 空单：检查LS-Ratio是否足够高
            if current_ls_ratio < self.config.GOLDEN_THRESHOLD_SHORT_SKIP:
                reason = (f"LOW_LS_RATIO: LS={current_ls_ratio:.2f} < {self.config.GOLDEN_THRESHOLD_SHORT_SKIP} "
                         f"(散户拥挤度不足，胜率仅42.9%)")
                logger.warning(f"[Smart Ape] 黄金阈值过滤: {reason}")
                return False, reason

            # LS >= 2.0，胜率提升到69.6%
            logger.info(f"[Smart Ape] 黄金阈值通过: LS={current_ls_ratio:.2f} >= 2.0 (高胜率区间)")
            return True, None

        elif signal_type == "BEARISH_SINGULARITY":
            # 多单：不过滤（LS-Ratio在BTC多单上无明显规律）
            logger.info(f"[Smart Ape] 多单信号，不应用黄金阈值过滤")
            return True, None

        else:
            logger.info(f"[Smart Ape] 信号类型{signal_type}，不应用黄金阈值")
            return True, None

    def check_logic_failure_stop(self, position_state, current_ls_ratio, current_oi):
        """
        逻辑失效止损检查（V4.1新增）

        核心逻辑：
          - 监控LS-Ratio和OI的变化
          - 识别散户是否已经跑路
          - 逻辑失效立即止损（比-2.5%更早触发）

        多单逻辑失效：LS上升 + OI下降 → 散户割肉跑路 → 多头逻辑失效
        空单逻辑失效：LS下降 + OI下降 → 散户割肉跑路 → 空头逻辑失效

        Args:
            position_state: 持仓状态字典（必须有entry_ls_ratio和entry_oi）
            current_ls_ratio: 当前LS-Ratio
            current_oi: 当前OI

        Returns:
            (should_stop, reason): (True, "reason string") or (False, None)
        """
        if not position_state.get('smart_ape_enabled', False):
            return False, None

        entry_ls = position_state.get('entry_ls_ratio', None)
        entry_oi = position_state.get('entry_oi', None)

        if entry_ls is None or entry_oi is None:
            return False, None

        # 计算变化
        ls_change = current_ls_ratio - entry_ls
        oi_change_pct = (current_oi - entry_oi) / entry_oi if entry_oi > 0 else 0

        position_side = position_state.get('direction', None)

        if position_side > 0:  # 多单
            # 散户跑了 → 多头逻辑失效
            if (ls_change > self.config.LOGIC_FAILURE_LS_CHANGE and
                oi_change_pct < self.config.LOGIC_FAILURE_OI_CHANGE):

                reason = (f"LOGIC_FAILURE_LONG: LS {entry_ls:.2f}→{current_ls_ratio:.2f} (+{ls_change:.2f}), "
                         f"OI {oi_change_pct:+.1%}, 散户已割肉跑路，多头逻辑失效")
                logger.warning(f"[Smart Ape] {reason}")
                return True, reason

        elif position_side < 0:  # 空单
            # 散户跑了 → 空头逻辑失效
            if (ls_change < -self.config.LOGIC_FAILURE_LS_CHANGE and
                oi_change_pct < self.config.LOGIC_FAILURE_OI_CHANGE):

                reason = (f"LOGIC_FAILURE_SHORT: LS {entry_ls:.2f}→{current_ls_ratio:.2f} ({ls_change:.2f}), "
                         f"OI {oi_change_pct:+.1%}, 散户已割肉跑路，空头逻辑失效")
                logger.warning(f"[Smart Ape] {reason}")
                return True, reason

        return False, None

    def check_liquidation_flush_tp(self, position_state, current_long_liq, current_short_liq):
        """
        爆仓潮止盈检查（V4.1新增）

        核心逻辑：
          - 监控清算量（Liquidation）
          - 达到95分位 → 爆仓高潮 → 立即止盈
          - 在情绪最高点离场

        多单：监控空单清算量（空单爆仓高潮 → 多头止盈）
        空单：监控多单清算量（多头爆仓高潮 → 空头止盈）

        Args:
            position_state: 持仓状态字典
            current_long_liq: 当前多单清算量
            current_short_liq: 当前空单清算量

        Returns:
            (should_tp, reason): (True, "reason string") or (False, None)
        """
        if not position_state.get('smart_ape_enabled', False):
            return False, None

        position_side = position_state.get('direction', None)

        if position_side > 0:  # 多单
            # 监控空单清算量
            if current_short_liq >= self.liq_95th:
                reason = (f"LIQUIDATION_FLUSH_LONG: 空单清算量 ${current_short_liq:,.0f} > "
                         f"95分位 ${self.liq_95th:,.0f}, 空头爆仓高潮，立即止盈")
                logger.info(f"[Smart Ape] {reason}")
                return True, reason

        elif position_side < 0:  # 空单
            # 监控多单清算量
            if current_long_liq >= self.liq_95th:
                reason = (f"LIQUIDATION_FLUSH_SHORT: 多单清算量 ${current_long_liq:,.0f} > "
                         f"95分位 ${self.liq_95th:,.0f}, 多头爆仓高潮，立即止盈")
                logger.info(f"[Smart Ape] {reason}")
                return True, reason

        return False, None

# ==================== [3. 三维动态风险评估器 V3.1] ====================
class ThreeDimRiskAssessorV3_1:
    """三维动态风险评估器 - V3.1核心风险管理系统"""

    def __init__(self, config, data_fetcher):
        self.config = config
        self.data_fetcher = data_fetcher

        # 评估历史
        self.risk_history = deque(maxlen=1000)

    def assess_risk_level(self):
        """评估当前风险等级 - V3.1三维版

        返回: (risk_level, multiplier, details)
        - risk_level: 'EXTREME' / 'MODERATE_HIGH' / 'MODERATE' / 'NORMAL_CAUTIOUS' / 'NORMAL'
        - multiplier: 0.0 / 0.25 / 0.5 / 0.75 / 1.0
        - details: 包含具体指标和预警信息的字典
        """
        try:
            # 获取月度特征
            features = self.data_fetcher.get_monthly_features()

            if features is None:
                logger.warning("无月度特征数据，默认为正常风险")
                return 'NORMAL', 1.0, {'reason': '无月度特征数据，默认满仓'}

            oi_growth = features['oi_growth']
            fr_avg = features['fr_mean']
            fr_cv = features['fr_cv']
            fr_max = features['fr_max']

            details = {
                'oi_growth': oi_growth,
                'fr_avg': fr_avg,
                'fr_cv': fr_cv,
                'fr_max': fr_max,
                'timestamp': datetime.now()
            }

            # ========== 第一级：极端异常 - 完全过滤（0%仓位） ==========
            if (oi_growth > self.config.oi_growth_extreme or
                fr_avg > self.config.funding_monthly_extreme):
                risk_level = 'EXTREME'
                multiplier = 0.0
                reason = (f"极端异常 - OI增长率{oi_growth*100:.2f}%>{self.config.oi_growth_extreme*100:.0f}% "
                         f"或 FR均值{fr_avg*100:.2f}%>{self.config.funding_monthly_extreme*100:.0f}%")

                details['reason'] = reason
                details['warning'] = '🚨 建议：完全规避，停止开新仓'

                logger.warning(f"风险等级: {risk_level} (0%仓位) - {reason}")
                return risk_level, multiplier, details

            # ========== 第二级：轻度风险 - 根据FR_CV细分 ==========
            if (oi_growth > self.config.oi_growth_moderate or
                fr_avg > self.config.funding_monthly_moderate):

                # 轻度风险 + 高波动 → 极度减仓（25%）
                if fr_cv > self.config.fr_cv_high:
                    risk_level = 'MODERATE_HIGH'
                    multiplier = 0.25
                    reason = (f"高风险+高波动 - OI增长{oi_growth*100:.2f}%或FR均值{fr_avg*100:.2f}% "
                             f"+ FR_CV高({fr_cv:.2f}>{self.config.fr_cv_high})")

                    details['reason'] = reason
                    details['warning'] = '⚡ 建议：极度减仓，25%仓位参与'

                    logger.warning(f"风险等级: {risk_level} (25%仓位) - {reason}")
                    return risk_level, multiplier, details

                # 轻度风险 + 低波动 → 减半仓位（50%）
                else:
                    risk_level = 'MODERATE'
                    multiplier = 0.50
                    reason = (f"高风险+低波动 - OI增长{oi_growth*100:.2f}%或FR均值{fr_avg*100:.2f}% "
                             f"+ FR_CV正常({fr_cv:.2f})")

                    details['reason'] = reason
                    details['warning'] = '⚡ 建议：减半仓位，50%参与'

                    logger.info(f"风险等级: {risk_level} (50%仓位) - {reason}")
                    return risk_level, multiplier, details

            # ========== 第三级：正常月份 - 根据FR_CV细分 ==========
            # 正常 + 高波动 → 谨慎参与（75%）
            if fr_cv > self.config.fr_cv_normal:
                risk_level = 'NORMAL_CAUTIOUS'
                multiplier = 0.75
                reason = (f"正常+高波动 - OI增长{oi_growth*100:.2f}%, FR均值{fr_avg*100:.2f}% "
                         f"+ FR_CV偏高({fr_cv:.2f}>{self.config.fr_cv_normal})")

                details['reason'] = reason
                details['warning'] = '📊 建议：谨慎参与，75%仓位'

                logger.info(f"风险等级: {risk_level} (75%仓位) - {reason}")
                return risk_level, multiplier, details

            # 正常 + 低波动 → 满仓交易（100%）
            else:
                risk_level = 'NORMAL'
                multiplier = 1.0
                reason = (f"正常+低波动 - OI增长{oi_growth*100:.2f}%, FR均值{fr_avg*100:.2f}% "
                         f"+ FR_CV正常({fr_cv:.2f})")

                details['reason'] = reason
                details['warning'] = '✅ 风险正常，可以满仓参与'

                logger.info(f"风险等级: {risk_level} (100%仓位) - {reason}")
                return risk_level, multiplier, details

        except Exception as e:
            logger.error(f"风险评估失败: {e}")
            return 'NORMAL', 1.0, {'reason': f'评估失败: {e}'}

# ==================== [4. 消息推送器 - V2完整版] ====================
class EnhancedMessageNotifier:
    """消息推送器 - V2完整版（支持详细仓位和信号信息）"""

    def __init__(self, config):
        self.config = config

        # 设置代理
        self.proxies = None
        if config.proxy_enabled:
            self.proxies = {
                'http': config.proxy_http,
                'https': config.proxy_https
            }

        self.session = requests.Session()
        if self.proxies:
            self.session.proxies = self.proxies

        # 禁用SSL验证
        self.session.verify = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.telegram_url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"
        self.wechat_url = f"https://sctapi.ftqq.com/{config.wechat_sckey}.send"

    def _build_message(self, alert_type, message, details=None):
        """构建详细消息格式"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"🎯【物理奇点预警 V3.1 - {alert_type}】",
            f"⏰ 时间: {timestamp}",
            f"📊 交易对: {self.config.binance_symbol}",
            "─" * 40,
            f"📢 {message}",
            "─" * 40
        ]

        if details:
            for key, value in details.items():
                if "─" in key:
                    lines.append(value)
                else:
                    lines.append(f"  {key}: {value}")

        lines.extend([
            "─" * 40,
            "🧠 系统: V3.1三维风控 + V2完整功能",
            "📈 时间框架: 4H信号 + 15M入场",
            "🎯 策略: 反向交易 + EMA21加仓 + 动态仓位",
            "🛡️ 风控: OI + FR + FR_CV三维评估",
            "=" * 50
        ])

        return "\n".join(lines)

    def send_telegram(self, message):
        """发送Telegram消息"""
        try:
            if len(message) > 4000:
                message = message[:3900] + "\n...\n【消息过长，已截断】"

            payload = {
                'chat_id': self.config.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }

            response = self.session.post(self.telegram_url, json=payload, timeout=10)
            result = response.json()

            if result.get("ok"):
                return True
            else:
                payload.pop('parse_mode', None)
                response = self.session.post(self.telegram_url, json=payload, timeout=10)
                return response.json().get("ok", False)

        except Exception as e:
            logger.error(f"Telegram发送错误: {e}")
            return False

    def send_wechat(self, alert_type, message, details=None):
        """发送微信消息"""
        try:
            full_message = self._build_message(alert_type, message, details)

            payload = {
                'title': f"物理奇点预警 V3.1 - {alert_type}",
                'desp': full_message
            }

            response = self.session.post(self.wechat_url, data=payload, timeout=10)
            return response.json().get('code') == 0

        except Exception as e:
            logger.error(f"微信发送错误: {e}")
            return False

    def send_alert(self, alert_type, message, details=None, urgency="normal"):
        """发送警报到所有渠道"""
        urgency_prefix = {
            "normal": "🔔",
            "high": "🚨",
            "urgent": "⚠️🚨"
        }.get(urgency, "🔔")

        full_alert_type = f"{urgency_prefix} {alert_type}"

        logger.info(f"发送警报: {full_alert_type}")

        results = {}
        results['telegram'] = self.send_telegram(self._build_message(full_alert_type, message, details))
        results['wechat'] = self.send_wechat(alert_type, message, details)

        print(f"\n{self._build_message(full_alert_type, message, details)}")

        return results

    # ==================== V4.1新增：Smart Ape通知方法 ====================

    def send_smart_ape_stop_loss(self, stop_type, direction, reason, pnl_pct):
        """
        发送Smart Ape止损通知（V4.1新增）

        Args:
            stop_type: 止损类型（"逻辑失效止损"）
            direction: 1 (多) or -1 (空)
            reason: 止损原因
            pnl_pct: 当前盈亏百分比
        """
        direction_str = "多单" if direction > 0 else "空单"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = f"""
🛑 Smart Ape止损触发

⏰ 时间: {timestamp}
─" * 50
止损类型: {stop_type}
方向: {direction_str}

止损原因:
{reason}

当前盈亏: {pnl_pct:+.2f}%

─" * 50
💡 说明: Smart Ape动态风险管理检测到散户已割肉跑路，
   逻辑失效，比固定止损更早触发，避免更大亏损。

🧠 系统: V4.1 Smart Ape Edition
📊 版本: V3.1完整功能 + Smart Ape动态风险管理
"""

        # 发送到Telegram
        self.send_telegram(message)
        logger.info(f"[Telegram] Smart Ape止损通知已发送: {stop_type}, {direction_str}, {pnl_pct:+.2f}%")

    def send_smart_ape_take_profit(self, tp_type, direction, reason, pnl_pct):
        """
        发送Smart Ape止盈通知（V4.1新增）

        Args:
            tp_type: 止盈类型（"爆仓潮止盈"）
            direction: 1 (多) or -1 (空)
            reason: 止盈原因
            pnl_pct: 当前盈亏百分比
        """
        direction_str = "多单" if direction > 0 else "空单"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = f"""
🎯 Smart Ape止盈触发

⏰ 时间: {timestamp}
─" * 50
止盈类型: {tp_type}
方向: {direction_str}

止盈原因:
{reason}

当前盈亏: {pnl_pct:+.2f}%

─" * 50
💡 说明: Smart Ape检测到爆仓高潮（清算量>95分位），
   在情绪最高点离场，避免爆仓潮后的反弹回撤。

🧠 系统: V4.1 Smart Ape Edition
📊 版本: V3.1完整功能 + Smart Ape动态风险管理
"""

        # 发送到Telegram
        self.send_telegram(message)
        logger.info(f"[Telegram] Smart Ape止盈通知已发送: {tp_type}, {direction_str}, {pnl_pct:+.2f}%")

    def send_golden_threshold_skip(self, signal_type, ls_ratio, reason):
        """
        发送黄金阈值跳过通知（V4.1新增）

        Args:
            signal_type: 信号类型（BULLISH_SINGULARITY or BEARISH_SINGULARITY）
            ls_ratio: LS-Ratio值
            reason: 跳过原因
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = f"""
⚠️ 黄金阈值过滤：跳过交易

⏰ 时间: {timestamp}
─" * 50
信号类型: {signal_type}
LS-Ratio: {ls_ratio:.2f}

跳过原因:
{reason}

─" * 50
💡 说明: 空单LS-Ratio < 2.0时胜率仅42.9%（亏损$3,467），
   跳过此信号可提升整体收益+4.5%。

📊 回测验证:
   • 跳过前: 768%收益
   • 跳过后: 803%收益 (+4.5%)
   • 避免亏损: $3,467（7笔最差交易）

🧠 系统: V4.1 Smart Ape Edition
"""

        # 发送到Telegram
        self.send_telegram(message)
        logger.info(f"[Telegram] 黄金阈值跳过通知已发送: {signal_type}, LS={ls_ratio:.2f}")

# ==================== [5. 物理诊断引擎 - 与回测对齐] ====================
class PhysicsDiagnosisEngine:
    """物理奇点诊断引擎 - 与回测逻辑严格对齐"""

    def __init__(self, config):
        self.config = config

    def calculate_tension_acceleration(self, prices):
        """计算张力和加速度 - 与回测完全一致"""
        if len(prices) < 60:
            return 0.0, 0.0

        try:
            prices_array = np.array(prices, dtype=np.float64)
            d_prices = detrend(prices_array)

            coeffs = fft(d_prices)
            coeffs[8:] = 0
            filtered = ifft(coeffs).real

            analytic = hilbert(filtered)
            tension = np.imag(analytic)

            if len(tension) > 1 and np.std(tension) > 0:
                norm_tension = (tension - np.mean(tension)) / np.std(tension)
            else:
                norm_tension = tension

            current_tension = norm_tension[-1]
            prev_tension = norm_tension[-2] if len(norm_tension) > 1 else current_tension
            prev2_tension = norm_tension[-3] if len(norm_tension) > 2 else prev_tension

            velocity = current_tension - prev_tension
            acceleration = velocity - (prev_tension - prev2_tension)

            return float(current_tension), float(acceleration)

        except Exception as e:
            logger.error(f"物理计算错误: {e}")
            return 0.0, 0.0

    def get_dxy_fuel(self, dxy_data, date=None):
        """获取DXY燃料 - 使用前一天数据"""
        if dxy_data is None or dxy_data.empty:
            return 0.0

        try:
            if date is None:
                date = datetime.now()

            prev_date = date - timedelta(days=1)
            mask = dxy_data.index <= prev_date
            available_dates = dxy_data[mask].index

            if len(available_dates) == 0:
                return 0.0

            latest_date = available_dates[-1]
            recent = dxy_data.loc[:latest_date].tail(5)

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

    def diagnose_regime(self, tension, acceleration, dxy_fuel):
        """诊断物理体制 - 与回测完全一致"""
        if tension > self.config.TENSION_THRESHOLD and acceleration < -self.config.ACCEL_THRESHOLD:
            if dxy_fuel > 0.1:
                return "BEARISH_SINGULARITY", "强奇点看空 (宏观失速)", 0.9
            else:
                return "BEARISH_SINGULARITY", "奇点看空 (动力失速)", 0.7

        if tension < -self.config.TENSION_THRESHOLD and acceleration > self.config.ACCEL_THRESHOLD:
            if dxy_fuel > 0.2:
                return "BULLISH_SINGULARITY", "超强奇点看涨 (燃料爆炸)", 0.95
            elif dxy_fuel > 0:
                return "BULLISH_SINGULARITY", "强奇点看涨 (动力回归)", 0.8
            else:
                return "BULLISH_SINGULARITY", "奇点看涨 (弹性释放)", 0.6

        if abs(tension) < self.config.OSCILLATION_BAND and abs(acceleration) < 0.02:
            return "OSCILLATION", "系统平衡 (震荡收敛)", 0.8

        if tension > 0.3 and abs(acceleration) < 0.01:
            return "HIGH_OSCILLATION", "高位震荡 (风险积聚)", 0.6

        if tension < -0.3 and abs(acceleration) < 0.01:
            return "LOW_OSCILLATION", "低位震荡 (机会积聚)", 0.6

        if tension > 0 and acceleration > 0:
            return "TRANSITION_UP", "向上过渡 (蓄力)", 0.4
        elif tension < 0 and acceleration < 0:
            return "TRANSITION_DOWN", "向下过渡 (泄力)", 0.4

        return "TRANSITION", "体制切换中", 0.3

# 位置有限，我将继续在下一个文件中创建完整的V3.1系统
# 由于系统很大，我需要创建多个部分

# ==================== 文件未完，继续下一部分 ====================
# 下部分将包含：
# [6] PositionTracker - V2完整版仓位追踪器
# [7] BattleSignalGenerator - 战备模式管理器
# [8] TelegramCommandHandler - Telegram交互控制
# [9] 主程序 - 完整的调度和集成

# ==================== [6. 仓位跟踪器 - V2完整版] ====================
class PositionTracker:
    """仓位跟踪器 - 与回测逻辑严格对齐"""

    def __init__(self, config, notifier):
        self.config = config
        self.notifier = notifier

        # 加载仓位状态
        self.position_file = "position_tracker_aligned_status.json"

        # 🎯 信号历史文件（独立于持仓，用于混合策略）
        self.signal_history_file = "signal_history.json"

        # ✅ 交易历史追踪器
        self.trade_history = TradeHistoryTracker('trade_history.json')

        self.load_position()
        self.load_signal_history()
        self.trade_history.print_summary()  # 启动时显示历史统计
    
    def calculate_dynamic_slippage(self, position_pct, is_open=True):
        """🎯 动态滑点计算 - 与回测一致"""
        base_slippage = self.config.base_slippage
        
        # 开仓通常比平仓滑点大
        if is_open:
            base_slippage *= 1.2
        
        # 限制最大滑点
        final_slippage = min(base_slippage, self.config.max_slippage)
        
        return final_slippage
    
    def load_position(self):
        """加载仓位状态"""
        if os.path.exists(self.position_file):
            try:
                with open(self.position_file, 'r', encoding='utf-8') as f:
                    status = json.load(f)

                    self.config.has_position = status.get('has_position', False)
                    self.config.position_type = status.get('position_type')
                    self.config.entry_price = status.get('entry_price', 0.0)
                    self.config.effective_entry_price = status.get('effective_entry_price', 0.0)
                    self.config.initial_entry_price = status.get('initial_entry_price', 0.0)
                    self.config.entry_time = datetime.fromisoformat(status['entry_time']) if status.get('entry_time') else None
                    self.config.position_size_pct = status.get('position_size_pct', 0.0)
                    self.config.position_quantity = status.get('position_quantity', 0.0)
                    self.config.add_position_taken = status.get('add_position_taken', False)
                    self.config.entry_regime = status.get('entry_regime')

                    # 止盈止损状态
                    self.config.stop_loss_price = status.get('stop_loss_price', 0.0)
                    self.config.initial_stop_loss_price = status.get('initial_stop_loss_price', 0.0)
                    self.config.breakeven_price = status.get('breakeven_price', 0.0)
                    self.config.tp1_price = status.get('tp1_price', 0.0)
                    self.config.tp2_price = status.get('tp2_price', 0.0)
                    self.config.trailing_stop_price = status.get('trailing_stop_price', 0.0)
                    self.config.tp1_hit = status.get('tp1_hit', False)
                    self.config.trailing_activated = status.get('trailing_activated', False)
                    self.config.breakeven_triggered = status.get('breakeven_triggered', False)
                    self.config.peak_price = status.get('peak_price', 0.0)
                    self.config.peak_profit_pct = status.get('peak_profit_pct', 0.0)
                    self.config.max_floating_profit = status.get('max_floating_profit', 0.0)
                    self.config.max_floating_pct = status.get('max_floating_pct', 0.0)

                    # 🎯 原始趋势信息（混合策略）
                    self.config.original_tp1_price = status.get('original_tp1_price', 0.0)
                    self.config.original_tp2_price = status.get('original_tp2_price', 0.0)
                    self.config.original_regime = status.get('original_regime')
                    self.config.original_direction = status.get('original_direction')
                    self.config.original_signal_time = datetime.fromisoformat(status['original_signal_time']) if status.get('original_signal_time') else None
                    self.config.trend_continuation_count = status.get('trend_continuation_count', 0)

                    # 🎯 最新检测信号
                    self.config.last_signal_time = datetime.fromisoformat(status['last_signal_time']) if status.get('last_signal_time') else None
                    self.config.last_signal_type = status.get('last_signal_type')
                    self.config.last_signal_desc = status.get('last_signal_desc', '')
                    self.config.last_signal_price = status.get('last_signal_price', 0.0)
                    self.config.last_signal_confidence = status.get('last_signal_confidence', 0.0)

                    # 🎯 V4.1新增：Smart Ape状态（动态风险管理）
                    self.config.entry_ls_ratio = status.get('entry_ls_ratio', None)
                    self.config.entry_oi = status.get('entry_oi', None)
                    self.config.entry_liq = status.get('entry_liq', None)
                    self.config.smart_ape_enabled = status.get('smart_ape_enabled', False)
                    self.config.logic_failed_triggered = status.get('logic_failed_triggered', False)
                    self.config.liquidation_flush_triggered = status.get('liquidation_flush_triggered', False)

                print(f"   加载仓位状态: 有仓位")
            except Exception as e:
                print(f"   加载仓位状态失败: {e}")
        else:
            print(f"   加载仓位状态: 无仓位")

    def load_signal_history(self):
        """🎯 加载信号历史（独立于持仓，用于混合策略）"""
        if os.path.exists(self.signal_history_file):
            try:
                with open(self.signal_history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    self.config.original_regime = history.get('regime_type')
                    self.config.original_direction = history.get('direction')
                    self.config.original_signal_time = datetime.fromisoformat(history['signal_time']) if history.get('signal_time') else None
                    self.config.original_tp1_price = history.get('tp1_price', 0.0)
                    self.config.original_tp2_price = history.get('tp2_price', 0.0)
                    self.config.trend_continuation_count = history.get('continuation_count', 0)
                    print(f"   加载信号历史: {self.config.original_regime or '无'}")
            except Exception as e:
                print(f"   加载信号历史失败: {e}")
        else:
            print(f"   加载信号历史: 无历史")

    def save_signal_history(self, regime_type, position_type, entry_price, signal_time):
        """🎯 保存信号历史（用于混合策略）"""
        try:
            # 计算止盈目标
            if position_type == 'long':
                tp1_price = entry_price * (1 + self.config.tp1_pct/100)
                tp2_price = entry_price * (1 + self.config.tp2_pct/100)
            else:  # short
                tp1_price = entry_price * (1 - self.config.tp1_pct/100)
                tp2_price = entry_price * (1 - self.config.tp2_pct/100)

            history = {
                'regime_type': regime_type,
                'direction': position_type,
                'signal_time': signal_time.isoformat(),
                'entry_price': entry_price,
                'tp1_price': tp1_price,
                'tp2_price': tp2_price,
                'continuation_count': self.config.trend_continuation_count,
                'last_update': datetime.now().isoformat()
            }

            with open(self.signal_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存信号历史失败: {e}")

    def display_status_on_startup(self):
        """[STAR] 启动时显示持仓状态摘要"""
        print("\n" + "="*80)
        print("[STATUS] BTC 持仓状态摘要")
        print("="*80)

        if self.config.has_position:
            # 有持仓
            print(f"[POSITION] 当前有持仓")
            print(f"   方向: {'[LONG] 多头' if self.config.position_type == 'long' else '[SHORT] 空头'}")
            print(f"   入场价: ${self.config.effective_entry_price:,.2f}")
            print(f"   初始入场: ${self.config.initial_entry_price:,.2f}")

            # 如果有加仓
            if self.config.add_position_taken and hasattr(self.config, 'add_position_price'):
                print(f"   加仓价: ${self.config.add_position_price:,.2f}")

            print(f"   止损: ${self.config.stop_loss_price:,.2f}")
            print(f"   TP1: ${self.config.tp1_price:,.2f} {'[OK]' if self.config.tp1_hit else '[PENDING]'}")
            print(f"   TP2: ${self.config.tp2_price:,.2f}")
            print(f"   移动止损: ${self.config.trailing_stop_price:,.2f}" if self.config.trailing_stop_price > 0 else "   移动止损: 未激活")
            print(f"   峰值盈利: {self.config.peak_profit_pct:+.2f}%")
            print(f"   入场时间: {self.config.entry_time.strftime('%Y-%m-%d %H:%M:%S') if self.config.entry_time else 'N/A'}")
            print()
            print("[INFO] 监控已恢复，继续跟踪止盈止损")
        else:
            # 空仓
            print(f"[POSITION] 当前无持仓")
            print(f"[INFO] 系统状态: 空仓，等待新信号")

        print("="*80 + "\n")

    def save_position(self):
        """保存仓位状态"""
        try:
            status = {
                'has_position': self.config.has_position,
                'position_type': self.config.position_type,
                'entry_price': self.config.entry_price,
                'effective_entry_price': self.config.effective_entry_price,
                'initial_entry_price': self.config.initial_entry_price,
                'entry_time': self.config.entry_time.isoformat() if self.config.entry_time else None,
                'position_size_pct': self.config.position_size_pct,
                'position_quantity': self.config.position_quantity,
                'add_position_taken': self.config.add_position_taken,
                'entry_regime': self.config.entry_regime,
                
                # 止盈止损
                'stop_loss_price': self.config.stop_loss_price,
                'initial_stop_loss_price': self.config.initial_stop_loss_price,
                'breakeven_price': self.config.breakeven_price,
                'tp1_price': self.config.tp1_price,
                'tp2_price': self.config.tp2_price,
                'trailing_stop_price': self.config.trailing_stop_price,
                
                # 状态标记
                'tp1_hit': self.config.tp1_hit,
                'trailing_activated': self.config.trailing_activated,
                'breakeven_triggered': self.config.breakeven_triggered,
                
                # 峰值记录
                'peak_price': self.config.peak_price,
                'peak_profit_pct': self.config.peak_profit_pct,
                'max_floating_profit': self.config.max_floating_profit,
                'max_floating_pct': self.config.max_floating_pct,

                # 🎯 原始趋势信息（混合策略）
                'original_tp1_price': self.config.original_tp1_price,
                'original_tp2_price': self.config.original_tp2_price,
                'original_regime': self.config.original_regime,
                'original_direction': self.config.original_direction,
                'original_signal_time': self.config.original_signal_time.isoformat() if self.config.original_signal_time else None,
                'trend_continuation_count': self.config.trend_continuation_count,
                'original_tp_reached': self.config.original_tp_reached,

                # 🎯 最新检测信号
                'last_signal_time': self.config.last_signal_time.isoformat() if self.config.last_signal_time else None,
                'last_signal_type': self.config.last_signal_type,
                'last_signal_desc': self.config.last_signal_desc,
                'last_signal_price': self.config.last_signal_price,
                'last_signal_confidence': self.config.last_signal_confidence,

                # 🎯 V4.1新增：Smart Ape状态（动态风险管理）
                'entry_ls_ratio': self.config.entry_ls_ratio,
                'entry_oi': self.config.entry_oi,
                'entry_liq': self.config.entry_liq,
                'smart_ape_enabled': self.config.smart_ape_enabled,
                'logic_failed_triggered': self.config.logic_failed_triggered,
                'liquidation_flush_triggered': self.config.liquidation_flush_triggered,

                'last_update': datetime.now().isoformat()
            }
            
            with open(self.position_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存仓位状态失败: {e}")
    
    def is_same_trend_continuation(self, regime_type, position_type):
        """判断是否是同一趋势的延续

        入场信号：BEARISH_SINGULARITY、BULLISH_SINGULARITY
        中继信号：OSCILLATION、HIGH_OSCILLATION、LOW_OSCILLATION、TRANSITION_UP、TRANSITION_DOWN

        判断标准：
        1. 有原始趋势信息
        2. regime类型相同（BEARISH_SINGULARITY 或 BULLISH_SINGULARITY）
        3. 交易方向相同（long 或 short）

        新趋势判断：
        - 信号翻转（BEARISH ↔ BULLISH）
        - 方向翻转（long ↔ short）
        - 出现中继信号（趋势进入震荡/过渡阶段，在主循环中处理）
        """
        # 如果没有原始趋势信息，这是新趋势
        if self.config.original_regime is None:
            return False

        # ✅ 信号翻转判断：regime类型改变
        if self.config.original_regime != regime_type:
            logger.info(f"信号翻转: {self.config.original_regime} → {regime_type}，新趋势开始")
            return False

        # ✅ 信号翻转判断：交易方向改变
        if self.config.original_direction != position_type:
            logger.info(f"方向翻转: {self.config.original_direction} → {position_type}，新趋势开始")
            return False

        # regime和方向都相同，说明是同一趋势的延续（无时间限制）
        return True

    def open_position(self, regime_type, regime_desc, entry_price, current_ema, signal_confidence,
                     ls_ratio=None, oi=None, liq=None):
        """🎯 记录开仓 - 与回测逻辑对齐，混合策略：新止损+旧止盈

        V4.1新增：记录Smart Ape状态（ls_ratio, oi, liq）用于动态风险管理"""
        # 确定交易方向
        if regime_type == "BEARISH_SINGULARITY":
            position_type = 'long'  # 反向做多
            side = 'buy'
        elif regime_type == "BULLISH_SINGULARITY":
            position_type = 'short'  # 反向做空
            side = 'sell'
        else:
            return False

        # 判断是否是同一趋势的延续
        is_continuation = self.is_same_trend_continuation(regime_type, position_type)

        # 🎯 V3.1 A2：动态仓位计算（与回测逻辑一致：首次×0.5，加仓×0.5）
        # 首次开仓 = base_position_ratio × 0.5
        # EMA21加仓 = base_position_ratio × 0.5
        # 总仓位 = base_position_ratio
        position_size_pct = self.config.base_position_ratio * 0.5  # 首次开仓占基础仓位的一半

        logger.info(f"📊 [Smart Ape] 动态仓位计算:")
        logger.info(f"   基础仓位: {self.config.base_position_ratio*100:.1f}%")
        logger.info(f"   首次开仓: {position_size_pct*100:.2f}% (基础×0.5)")
        logger.info(f"   后续加仓: {position_size_pct*100:.2f}% (基础×0.5)")
        logger.info(f"   总仓位: {self.config.base_position_ratio*100:.1f}%")

        # 🎯 计算动态滑点
        open_slippage = self.calculate_dynamic_slippage(position_size_pct, is_open=True)

        # 计算有效入场价格（含滑点）
        if side == 'buy':
            effective_entry_price = entry_price * (1 + open_slippage)
        else:
            effective_entry_price = entry_price * (1 - open_slippage)

        # 设置仓位状态
        self.config.has_position = True
        self.config.position_type = position_type
        self.config.entry_price = entry_price  # 信号价格
        self.config.effective_entry_price = effective_entry_price  # 实际价格（含滑点）
        self.config.initial_entry_price = effective_entry_price
        self.config.entry_time = datetime.now()
        self.config.position_size_pct = position_size_pct
        # ✅ 修复：设置虚拟数量用于计算平均成本（占位1%，加仓29%）
        self.config.position_quantity = 1.0  # 虚拟数量，首仓占位1%对应1单位
        self.config.add_position_taken = False
        self.config.entry_regime = regime_type

        # 🎯 V4.1新增：记录Smart Ape状态（动态风险管理）
        self.config.entry_ls_ratio = ls_ratio
        self.config.entry_oi = oi
        self.config.entry_liq = liq
        self.config.smart_ape_enabled = True if (ls_ratio and oi and liq) else False
        self.config.logic_failed_triggered = False
        self.config.liquidation_flush_triggered = False

        if self.config.smart_ape_enabled:
            logger.info(f"[Smart Ape] 记录进场状态:")
            logger.info(f"  LS-Ratio: {ls_ratio:.2f}")
            logger.info(f"  OI: {oi:.0f}")
            logger.info(f"  清算量: ${liq:,.0f}")

        # 🎯 混合策略：新止损 + 旧止盈
        if is_continuation:
            # 同一趋势延续：使用新信号的止损，保留原始信号的止盈
            if position_type == 'long':
                self.config.stop_loss_price = effective_entry_price * (1 - self.config.sl_pct/100)
                self.config.tp1_price = self.config.original_tp1_price  # ✅ 保留原始止盈
                self.config.tp2_price = self.config.original_tp2_price  # ✅ 保留原始止盈
                self.config.breakeven_price = effective_entry_price * 1.001  # 保本价
                self.config.peak_price = effective_entry_price
            else:  # short
                self.config.stop_loss_price = effective_entry_price * (1 + self.config.sl_pct/100)
                self.config.tp1_price = self.config.original_tp1_price  # ✅ 保留原始止盈
                self.config.tp2_price = self.config.original_tp2_price  # ✅ 保留原始止盈
                self.config.breakeven_price = effective_entry_price * 0.999  # 保本价
                self.config.peak_price = effective_entry_price

            self.config.trend_continuation_count += 1
            logger.info(f"同一趋势延续(第{self.config.trend_continuation_count}次): 混合策略生效")
        else:
            # 新趋势：记录原始止盈目标
            if position_type == 'long':
                self.config.stop_loss_price = effective_entry_price * (1 - self.config.sl_pct/100)
                self.config.tp1_price = effective_entry_price * (1 + self.config.tp1_pct/100)
                self.config.tp2_price = effective_entry_price * (1 + self.config.tp2_pct/100)
                self.config.breakeven_price = effective_entry_price * 1.001  # 保本价
                self.config.peak_price = effective_entry_price

                # 记录原始止盈目标
                self.config.original_tp1_price = self.config.tp1_price
                self.config.original_tp2_price = self.config.tp2_price
            else:  # short
                self.config.stop_loss_price = effective_entry_price * (1 + self.config.sl_pct/100)
                self.config.tp1_price = effective_entry_price * (1 - self.config.tp1_pct/100)
                self.config.tp2_price = effective_entry_price * (1 - self.config.tp2_pct/100)
                self.config.breakeven_price = effective_entry_price * 0.999  # 保本价
                self.config.peak_price = effective_entry_price

                # 记录原始止盈目标
                self.config.original_tp1_price = self.config.tp1_price
                self.config.original_tp2_price = self.config.tp2_price

            # 记录原始趋势信息
            self.config.original_regime = regime_type
            self.config.original_direction = position_type
            self.config.original_signal_time = datetime.now()
            self.config.trend_continuation_count = 0
            logger.info("新趋势开始: 记录原始止盈目标")

        self.config.initial_stop_loss_price = self.config.stop_loss_price
        
        # 重置其他状态
        self.config.tp1_hit = False
        self.config.trailing_activated = False
        self.config.trailing_stop_price = 0.0
        self.config.breakeven_triggered = False
        self.config.peak_profit_pct = 0.0
        self.config.max_floating_profit = 0.0
        self.config.max_floating_pct = 0.0
        
        # 🎯 V4.1简化：发送简洁开仓通知
        direction = "📈 做多" if position_type == 'long' else "📉 做空"
        action = "反向做多" if regime_type == "BEARISH_SINGULARITY" else "反向做空"

        # 止盈止损价格
        if position_type == 'long':
            sl_str = f"${self.config.initial_stop_loss_price:.2f} (-{self.config.sl_pct}%)"
            tp1_str = f"${self.config.tp1_price:.2f} (+{self.config.tp1_pct}%)"
            tp2_str = f"${self.config.tp2_price:.2f} (+{self.config.tp2_pct}%)"
        else:
            sl_str = f"${self.config.initial_stop_loss_price:.2f} (-{self.config.sl_pct}%)"
            tp1_str = f"${self.config.tp1_price:.2f} (+{self.config.tp1_pct}%)"
            tp2_str = f"${self.config.tp2_price:.2f} (+{self.config.tp2_pct}%)"

        details = {
            "交易方向": f"{direction} - {action}",
            "入场价格": f"${effective_entry_price:.2f}",
            "首次仓位": f"{position_size_pct*100:.0f}% (后续加仓{position_size_pct*100:.0f}%)",
            "总仓位": f"{self.config.base_position_ratio*100:.0f}%",
            "止损(SL)": sl_str,
            "止盈1(TP1)": tp1_str,
            "止盈2(TP2)": tp2_str,
            "移动止损": f"最高价-{self.config.trail_offset_pct}% (TP1后激活)",
            "🎯 手动加仓": f"当前15%，建议手动加仓15%至总30%",
            "加仓方法": f"Telegram发送: /addposition 价格 或 我已加仓 价格为：XXXXX",
            "信号": f"{regime_desc} (置信度{signal_confidence:.1%})"
        }

        title = f"🚀 开仓成功 - {direction}"
        self.notifier.send_alert(title,
                                f"入场价格 ${effective_entry_price:.2f}，止损-{self.config.sl_pct}%，TP1+{self.config.tp1_pct}%，TP2+{self.config.tp2_pct}%",
                                details,
                                urgency="high")

        self.save_position()

        # 🎯 保存信号历史（独立于持仓，用于混合策略）
        self.save_signal_history(regime_type, position_type, entry_price, datetime.now())

        logger.info(f"记录开仓: {action} @ ${effective_entry_price:.2f}")
        return True
    
    def check_add_position(self, current_price, current_ema):
        """检查是否满足加仓条件"""
        if not self.config.has_position or self.config.add_position_taken:
            return False
        
        # 检查15分钟EMA21回踩条件
        if self.config.position_type == 'long':
            if current_price >= current_ema:
                return True
        else:  # short
            if current_price <= current_ema:
                return True
        
        return False
    
    def execute_add_position(self, add_price, current_ema):
        """执行EMA21回踩加仓"""
        if not self.config.has_position or self.config.add_position_taken:
            return False

        # 🎯 V3.1 A2：动态加仓计算（与回测逻辑一致）
        # 加仓仓位 = base_position_ratio × 0.5（与首次开仓相同）
        add_size_pct = self.config.base_position_ratio * 0.5

        logger.info(f"📊 [Smart Ape] 动态加仓计算:")
        logger.info(f"   基础仓位: {self.config.base_position_ratio*100:.1f}%")
        logger.info(f"   加仓比例: {add_size_pct*100:.2f}% (基础×0.5)")
        logger.info(f"   总仓位: {self.config.base_position_ratio*100:.1f}%")

        # 🎯 计算动态滑点
        add_slippage = self.calculate_dynamic_slippage(add_size_pct, is_open=True)

        # 计算有效加仓价格
        if self.config.position_type == 'long':
            effective_add_price = add_price * (1 + add_slippage)
        else:
            effective_add_price = add_price * (1 - add_slippage)

        # ✅ V3.1 A2修复：虚拟数量计算（首次和加仓比例相同，都是base×0.5）
        # 首次开仓 = base_position_ratio × 0.5，虚拟数量 = 1.0
        # 加仓 = base_position_ratio × 0.5，虚拟数量 = 1.0（与首次相同）
        old_quantity = self.config.position_quantity  # 首仓虚拟数量（1.0）
        initial_pct = self.config.base_position_ratio * 0.5  # 首次比例
        add_pct = self.config.base_position_ratio * 0.5  # 加仓比例（相同）
        add_quantity = old_quantity * (add_pct / initial_pct)  # = 1.0

        total_quantity = old_quantity + add_quantity

        logger.info(f"📊 [Smart Ape] 虚拟数量计算:")
        logger.info(f"   首仓数量: {old_quantity:.2f} (占比{initial_pct*100:.2f}%)")
        logger.info(f"   加仓数量: {add_quantity:.2f} (占比{add_pct*100:.2f}%)")
        logger.info(f"   总数量: {total_quantity:.2f}")

        if self.config.position_type == 'long':
            # 多单：计算新的平均成本
            avg_cost = (self.config.effective_entry_price * old_quantity +
                       effective_add_price * add_quantity) / total_quantity
            # 设置硬止损：平均成本 - 2.5%
            self.config.stop_loss_price = avg_cost * (1 - self.config.sl_pct/100)
        else:  # short
            # 空单：计算新的平均成本
            avg_cost = (self.config.effective_entry_price * old_quantity +
                       effective_add_price * add_quantity) / total_quantity
            # 设置硬止损：平均成本 + 2.5%
            self.config.stop_loss_price = avg_cost * (1 + self.config.sl_pct/100)

        # 更新有效入场价格为新的平均成本
        self.config.effective_entry_price = avg_cost

        # 更新仓位数量
        self.config.position_quantity = total_quantity

        # 更新状态
        self.config.add_position_taken = True
        
        # 🎯 发送加仓通知
        direction = "做多" if self.config.position_type == 'long' else "做空"
        
        details = {
            "📊 加仓信息": "─",
            "持仓方向": direction,
            "加仓价格": f"${add_price:.2f}",
            "实际价格": f"${effective_add_price:.2f} (含滑点{add_slippage*100:.3f}%)",
            "EMA21价格": f"${current_ema:.2f}",
            "加仓比例": f"{add_size_pct*100:.0f}%",
            "原入场价": f"${self.config.initial_entry_price:.2f}",
            "平均成本": f"${self.config.effective_entry_price:.2f}",
            "当前持仓": "初始仓 + 加仓",

            "🎯 止盈止损": "─",
            "止损价格": f"${self.config.stop_loss_price:.2f} (-2.5%)",
            "止盈1(TP1)": f"${self.config.tp1_price:.2f} (+{self.config.tp1_pct}%)",
            "止盈2(TP2)": f"${self.config.tp2_price:.2f} (+{self.config.tp2_pct}%)",
            "保本价格": f"${self.config.breakeven_price:.2f}",

            "🛡️ 风控更新": "─",
            "止损调整": "已使用平均成本设置硬止损-2.5%",
            "后续策略": "继续持仓，等待TP1/T2或追踪止损"
        }
        
        self.notifier.send_alert("➕ EMA21加仓信号", 
                                f"价格回踩EMA21，建议加仓{direction}", 
                                details,
                                urgency="high")
        
        self.save_position()
        logger.info(f"记录加仓: {direction} @ ${effective_add_price:.2f}")
        return True

    def manual_add_position(self, add_price):
        """🎯 V4.1人机结合版：手动加仓（通过Telegram命令）"""
        # 检查是否有持仓
        if not self.config.has_position:
            return False, "当前无持仓"

        # 检查是否已经加仓
        if self.config.add_position_taken:
            return False, "已经加仓过，无法再次加仓"

        # 计算加仓仓位（15%）
        add_size_pct = self.config.base_position_ratio * 0.5  # 30% × 0.5 = 15%

        logger.info(f"📊 [V4.1手动加仓] 计算加仓:")
        logger.info(f"   基础仓位: {self.config.base_position_ratio*100:.1f}%")
        logger.info(f"   加仓比例: {add_size_pct*100:.1f}%")
        logger.info(f"   总仓位: {self.config.base_position_ratio*100:.1f}%")

        # 🎯 手动加仓：用户输入的价格就是实际成交价（不需要滑点调整）
        effective_add_price = add_price

        # 虚拟数量计算（首次和加仓比例相同）
        old_quantity = self.config.position_quantity  # 首仓虚拟数量（1.0）
        initial_pct = self.config.base_position_ratio * 0.5  # 首次比例（15%）
        add_pct = self.config.base_position_ratio * 0.5  # 加仓比例（15%）
        add_quantity = old_quantity * (add_pct / initial_pct)  # = 1.0

        total_quantity = old_quantity + add_quantity

        logger.info(f"📊 [V4.1手动加仓] 虚拟数量计算:")
        logger.info(f"   首仓数量: {old_quantity:.2f} (占比{initial_pct*100:.1f}%)")
        logger.info(f"   加仓数量: {add_quantity:.2f} (占比{add_pct*100:.1f}%)")
        logger.info(f"   总数量: {total_quantity:.2f}")

        # 计算新的平均成本
        if self.config.position_type == 'long':
            # 多单：计算新的平均成本
            avg_cost = (self.config.effective_entry_price * old_quantity +
                       effective_add_price * add_quantity) / total_quantity
            # 重新计算止盈止损价格
            self.config.stop_loss_price = avg_cost * (1 - self.config.sl_pct/100)
            self.config.tp1_price = avg_cost * (1 + self.config.tp1_pct/100)
            self.config.tp2_price = avg_cost * (1 + self.config.tp2_pct/100)
            self.config.breakeven_price = avg_cost * (1 + self.config.taker_fee * 2)
        else:  # short
            # 空单：计算新的平均成本
            avg_cost = (self.config.effective_entry_price * old_quantity +
                       effective_add_price * add_quantity) / total_quantity
            # 重新计算止盈止损价格
            self.config.stop_loss_price = avg_cost * (1 + self.config.sl_pct/100)
            self.config.tp1_price = avg_cost * (1 - self.config.tp1_pct/100)
            self.config.tp2_price = avg_cost * (1 - self.config.tp2_pct/100)
            self.config.breakeven_price = avg_cost * (1 - self.config.taker_fee * 2)

        # 更新有效入场价格为新的平均成本
        self.config.effective_entry_price = avg_cost

        # 更新仓位数量
        self.config.position_quantity = total_quantity

        # 更新状态
        self.config.add_position_taken = True

        # 保存状态
        self.save_position()

        # 返回成功信息
        direction = "做多" if self.config.position_type == 'long' else "做空"
        message = f"""
加仓信息：
- 持仓方向：{direction}
- 加仓价格：${add_price:.2f}
- 原入场价：${self.config.initial_entry_price:.2f}
- 平均成本：${avg_cost:.2f}
- 当前持仓：初始仓15% + 加仓15% = 总30%

新的止盈止损：
- 止损价格：${self.config.stop_loss_price:.2f} ({self.config.sl_pct}%)
- 止盈1(TP1)：${self.config.tp1_price:.2f} (+{self.config.tp1_pct}%)
- 止盈2(TP2)：${self.config.tp2_price:.2f} (+{self.config.tp2_pct}%)
        """

        logger.info(f"✅ [V4.1手动加仓] 成功: {direction} @ ${effective_add_price:.2f}")
        return True, message.strip()

    def check_position(self, current_price, current_high, current_low):
        """🎯 检查仓位止盈止损 - 与回测逻辑对齐（使用K线高低价）"""
        if not self.config.has_position:
            return None, ""
        
        # 计算当前盈亏
        if self.config.position_type == 'long':
            profit_pct = (current_price - self.config.effective_entry_price) / self.config.effective_entry_price * 100
            profit_usd = 0  # 不计算实际金额
        else:  # short
            profit_pct = (self.config.effective_entry_price - current_price) / self.config.effective_entry_price * 100
            profit_usd = 0
        
        # 更新最大浮盈
        if abs(profit_pct) > abs(self.config.peak_profit_pct):
            self.config.peak_profit_pct = profit_pct
            self.config.max_floating_pct = profit_pct
        
        # 更新峰值价格
        if self.config.position_type == 'long':
            if current_price > self.config.peak_price:
                self.config.peak_price = current_price
        else:
            if current_price < self.config.peak_price:
                self.config.peak_price = current_price
        
        exit_reason = ""
        should_exit = False
        exit_price = 0.0

        # 🎯 V4.1 Smart Ape：优先检查逻辑失效止损和爆仓潮止盈（最高优先级）
        # 注意：需要全局的smart_ape_manager和data_fetcher
        global smart_ape_manager, data_fetcher
        if (self.config.smart_ape_enabled and smart_ape_manager is not None
            and not self.config.logic_failed_triggered and not self.config.liquidation_flush_triggered):
            try:
                # 获取Smart Ape数据
                current_ls_ratio = data_fetcher.fetch_ls_ratio() if data_fetcher else None
                current_oi = data_fetcher.fetch_oi() if data_fetcher else None
                current_long_liq, current_short_liq = data_fetcher.fetch_liquidation_both() if data_fetcher else (None, None)

                # 构建position_state
                position_state = {
                    'direction': 1 if self.config.position_type == 'long' else -1,
                    'smart_ape_enabled': self.config.smart_ape_enabled,
                    'entry_ls_ratio': self.config.entry_ls_ratio,
                    'entry_oi': self.config.entry_oi,
                    'entry_liq': self.config.entry_liq
                }

                # 1. 检查逻辑失效止损
                if current_ls_ratio and current_oi:
                    should_stop, reason = smart_ape_manager.check_logic_failure_stop(
                        position_state, current_ls_ratio, current_oi
                    )
                    if should_stop:
                        self.config.logic_failed_triggered = True
                        # 发送Smart Ape止损通知
                        self.notifier.send_smart_ape_stop_loss(
                            "逻辑失效止损",
                            1 if self.config.position_type == 'long' else -1,
                            reason,
                            profit_pct
                        )
                        exit_reason = f"SMART_APE_LOGIC_FAILURE: {reason}"
                        should_exit = True
                        logger.warning(f"[Smart Ape] {exit_reason}")
                        return should_exit, exit_reason

                # 2. 检查爆仓潮止盈
                if current_long_liq and current_short_liq and not should_exit:
                    should_tp, reason = smart_ape_manager.check_liquidation_flush_tp(
                        position_state, current_long_liq, current_short_liq
                    )
                    if should_tp:
                        self.config.liquidation_flush_triggered = True
                        # 发送Smart Ape止盈通知
                        self.notifier.send_smart_ape_take_profit(
                            "爆仓潮止盈",
                            1 if self.config.position_type == 'long' else -1,
                            reason,
                            profit_pct
                        )
                        exit_reason = f"SMART_APE_LIQUIDATION_FLUSH: {reason}"
                        should_exit = True
                        logger.info(f"[Smart Ape] {exit_reason}")
                        return should_exit, exit_reason

            except Exception as e:
                logger.error(f"[Smart Ape] 检查失败: {e}")

        # 🎯 关键优化：使用K线高低价检查止损（与回测一致）
        if self.config.position_type == 'long':
            # TP1触发
            if not self.config.tp1_hit and profit_pct >= self.config.tp1_pct:
                self.config.tp1_hit = True
                
                # 移动到保本位
                if self.config.flip_to_breakeven:
                    self.config.stop_loss_price = self.config.breakeven_price
                    self.config.breakeven_triggered = True
                
                # 激活追踪止损
                if self.config.trail_after_tp1:
                    self.config.trailing_activated = True
                    self.config.trailing_stop_price = current_price * (1 - self.config.trail_offset_pct/100)
                
                # 🎯 发送TP1触发通知
                details = {
                    "🎯 TP1达成": "─",
                    "触发价格": f"${current_price:.2f}",
                    "目标盈利": f"{self.config.tp1_pct}%",
                    "实际盈利": f"{profit_pct:.2f}%",
                    "持仓时间": f"{(datetime.now() - self.config.entry_time).total_seconds()/3600:.1f}小时",
                    "最大浮盈": f"{self.config.peak_profit_pct:.2f}%",
                    
                    "🛡️ 风控调整": "─",
                    "新止损价": f"${self.config.stop_loss_price:.2f}" if self.config.flip_to_breakeven else "不变",
                    "追踪止损": f"已激活 @ ${self.config.trailing_stop_price:.2f}" if self.config.trailing_activated else "未激活",
                    "后续策略": "继续持仓，等待TP2或追踪止损"
                }
                
                self.notifier.send_alert("🎯 TP1触发", 
                                        f"第一目标位已达到，盈利{profit_pct:.2f}%", 
                                        details,
                                        urgency="high")
            
            # TP2触发
            elif profit_pct >= self.config.tp2_pct:
                exit_price = current_price
                # 🎯 计算滑点
                close_slippage = self.calculate_dynamic_slippage(self.config.position_size_pct, is_open=False)
                exit_price = current_price * (1 - close_slippage)
                exit_reason = f"TP2触发 @ ${exit_price:.2f} (含滑点{close_slippage*100:.3f}%)"
                should_exit = True
            
            # 🎯 追踪止损（使用最低价判断）
            elif self.config.trailing_activated:
                # 更新追踪止损
                new_trailing_stop = current_price * (1 - self.config.trail_offset_pct/100)
                if new_trailing_stop > self.config.trailing_stop_price:
                    self.config.trailing_stop_price = new_trailing_stop
                
                # 使用K线最低价判断（与回测一致）
                if current_low <= self.config.trailing_stop_price:
                    exit_price = self.config.trailing_stop_price
                    close_slippage = self.calculate_dynamic_slippage(self.config.position_size_pct, is_open=False)
                    exit_price = self.config.trailing_stop_price * (1 - close_slippage)
                    exit_reason = f"追踪止损触发 @ ${exit_price:.2f} (含滑点{close_slippage*100:.3f}%)"
                    should_exit = True
            
            # 🎯 止损（使用K线最低价判断）
            elif current_low <= self.config.stop_loss_price:
                exit_price = self.config.stop_loss_price
                close_slippage = self.calculate_dynamic_slippage(self.config.position_size_pct, is_open=False)
                exit_price = self.config.stop_loss_price * (1 - close_slippage)
                exit_reason = f"止损触发 @ ${exit_price:.2f} (含滑点{close_slippage*100:.3f}%)"
                should_exit = True
        
        else:  # short position
            # TP1触发
            if not self.config.tp1_hit and profit_pct >= self.config.tp1_pct:
                self.config.tp1_hit = True
                
                # 移动到保本位
                if self.config.flip_to_breakeven:
                    self.config.stop_loss_price = self.config.breakeven_price
                    self.config.breakeven_triggered = True
                
                # 激活追踪止损
                if self.config.trail_after_tp1:
                    self.config.trailing_activated = True
                    self.config.trailing_stop_price = current_price * (1 + self.config.trail_offset_pct/100)
                
                # 🎯 发送TP1触发通知
                details = {
                    "🎯 TP1达成": "─",
                    "触发价格": f"${current_price:.2f}",
                    "目标盈利": f"{self.config.tp1_pct}%",
                    "实际盈利": f"{profit_pct:.2f}%",
                    "持仓时间": f"{(datetime.now() - self.config.entry_time).total_seconds()/3600:.1f}小时",
                    "最大浮盈": f"{self.config.peak_profit_pct:.2f}%",
                    
                    "🛡️ 风控调整": "─",
                    "新止损价": f"${self.config.stop_loss_price:.2f}" if self.config.flip_to_breakeven else "不变",
                    "追踪止损": f"已激活 @ ${self.config.trailing_stop_price:.2f}" if self.config.trailing_activated else "未激活",
                    "后续策略": "继续持仓，等待TP2或追踪止损"
                }
                
                self.notifier.send_alert("🎯 TP1触发", 
                                        f"第一目标位已达到，盈利{profit_pct:.2f}%", 
                                        details,
                                        urgency="high")
            
            # TP2触发
            elif profit_pct >= self.config.tp2_pct:
                exit_price = current_price
                close_slippage = self.calculate_dynamic_slippage(self.config.position_size_pct, is_open=False)
                exit_price = current_price * (1 + close_slippage)
                exit_reason = f"TP2触发 @ ${exit_price:.2f} (含滑点{close_slippage*100:.3f}%)"
                should_exit = True
            
            # 🎯 追踪止损（使用最高价判断）
            elif self.config.trailing_activated:
                # 更新追踪止损
                new_trailing_stop = current_price * (1 + self.config.trail_offset_pct/100)
                if new_trailing_stop < self.config.trailing_stop_price:
                    self.config.trailing_stop_price = new_trailing_stop
                
                # 使用K线最高价判断（与回测一致）
                if current_high >= self.config.trailing_stop_price:
                    exit_price = self.config.trailing_stop_price
                    close_slippage = self.calculate_dynamic_slippage(self.config.position_size_pct, is_open=False)
                    exit_price = self.config.trailing_stop_price * (1 + close_slippage)
                    exit_reason = f"追踪止损触发 @ ${exit_price:.2f} (含滑点{close_slippage*100:.3f}%)"
                    should_exit = True
            
            # 🎯 止损（使用K线最高价判断）
            elif current_high >= self.config.stop_loss_price:
                exit_price = self.config.stop_loss_price
                close_slippage = self.calculate_dynamic_slippage(self.config.position_size_pct, is_open=False)
                exit_price = self.config.stop_loss_price * (1 + close_slippage)
                exit_reason = f"止损触发 @ ${exit_price:.2f} (含滑点{close_slippage*100:.3f}%)"
                should_exit = True
        
        return should_exit, exit_reason, exit_price
    
    def close_position(self, exit_price, exit_reason):
        """记录平仓"""
        if not self.config.has_position:
            return False

        # 计算最终盈亏
        if self.config.position_type == 'long':
            profit_pct = (exit_price - self.config.effective_entry_price) / self.config.effective_entry_price * 100
        else:  # short
            profit_pct = (self.config.effective_entry_price - exit_price) / self.config.effective_entry_price * 100

        # 计算持仓时间
        hold_time = datetime.now() - self.config.entry_time
        hold_hours = hold_time.total_seconds() / 3600

        # ✅ 计算盈亏金额（假设初始资金$10,000）
        initial_capital = 10000
        position_value = initial_capital * self.config.position_size_pct
        profit_amount = position_value * profit_pct / 100

        # ✅ 生成交易ID
        trade_id = len(self.trade_history.trades) + 1

        # ✅ 添加到交易历史
        self.trade_history.add_trade(
            trade_id=trade_id,
            entry_time=self.config.entry_time,
            exit_time=datetime.now(),
            signal_type=self.config.entry_regime or 'UNKNOWN',
            position_type=self.config.position_type,
            entry_price=self.config.effective_entry_price,
            exit_price=exit_price,
            profit_pct=profit_pct,
            profit_amount=profit_amount,
            exit_reason=exit_reason,
            hold_hours=hold_hours,
            peak_profit_pct=self.config.peak_profit_pct,
            tp1_hit=self.config.tp1_hit,
            trailing_activated=self.config.trailing_activated,
            position_size_pct=self.config.position_size_pct,
            initial_sl=self.config.initial_stop_loss_price,
            final_sl=self.config.stop_loss_price,
            tp1_price=self.config.tp1_price,
            tp2_price=self.config.tp2_price
        )

        # 发送详细平仓通知
        profit_loss = "盈利" if profit_pct > 0 else "亏损"
        direction = "做多" if self.config.position_type == 'long' else "做空"
        action = "反向做多" if self.config.entry_regime == "BEARISH_SINGULARITY" else "反向做空"

        details = {
            "📊 平仓总结": "─",
            "交易ID": f"#{trade_id}",
            "平仓原因": exit_reason,
            "信号类型": self.config.entry_regime or "N/A",
            "交易方向": action,
            "持仓方向": direction,

            "💰 盈亏详情": "─",
            "入场价格": f"${self.config.effective_entry_price:.2f}",
            "出场价格": f"${exit_price:.2f}",
            "盈亏百分比": f"{profit_pct:+.2f}%",
            "盈亏金额": f"${profit_amount:+,.2f}",
            "最终结果": profit_loss,

            "⏰ 时间统计": "─",
            "入场时间": self.config.entry_time.strftime("%Y-%m-%d %H:%M"),
            "出场时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "持仓时间": f"{hold_hours:.1f}小时",

            "📈 表现统计": "─",
            "最大浮盈": f"{self.config.peak_profit_pct:+.2f}%",
            "TP1触发": "是" if self.config.tp1_hit else "否",
            "追踪止损": "已激活" if self.config.trailing_activated else "未激活",
            "保本触发": "是" if self.config.breakeven_triggered else "否",
            "是否加仓": "是" if self.config.add_position_taken else "否",
            "仓位比例": f"{self.config.position_size_pct*100:.0f}%",

            "🎯 关键价格回顾": "─",
            "初始止损": f"${self.config.initial_stop_loss_price:.2f}",
            "最终止损": f"${self.config.stop_loss_price:.2f}",
            "TP1价格": f"${self.config.tp1_price:.2f}",
            "TP2价格": f"${self.config.tp2_price:.2f}",
            "追踪止损价": f"${self.config.trailing_stop_price:.2f}" if self.config.trailing_stop_price > 0 else "N/A"
        }

        self.notifier.send_alert(f"📉 平仓信号 ({profit_loss})",
                                f"建议平仓，本次交易{profit_loss}{abs(profit_pct):.2f}%",
                                details,
                                urgency="high")

        # 重置仓位状态
        self.reset_position()

        logger.info(f"记录平仓: #{trade_id} | {profit_loss}{profit_pct:.2f}% | ${profit_amount:+,.2f}")
        return True
    
    def reset_position(self):
        """重置仓位状态"""
        self.config.has_position = False
        self.config.position_type = None
        self.config.entry_price = 0.0
        self.config.effective_entry_price = 0.0
        self.config.initial_entry_price = 0.0
        self.config.entry_time = None
        self.config.position_size_pct = 0.0
        self.config.position_quantity = 0.0
        self.config.add_position_taken = False
        self.config.entry_regime = None

        # 止盈止损
        self.config.stop_loss_price = 0.0
        self.config.initial_stop_loss_price = 0.0
        self.config.breakeven_price = 0.0
        self.config.tp1_price = 0.0
        self.config.tp2_price = 0.0
        self.config.trailing_stop_price = 0.0

        # 状态标记
        self.config.tp1_hit = False
        self.config.trailing_activated = False
        self.config.breakeven_triggered = False

        # 峰值记录
        self.config.peak_price = 0.0
        self.config.peak_profit_pct = 0.0
        self.config.max_floating_profit = 0.0
        self.config.max_floating_pct = 0.0

        # 🎯 原始趋势信息（混合策略）
        # 注意：不完全重置 original_regime 和 original_signal_time，以便后续判断同一趋势
        # 只有当中继信号出现或 regime 改变时，才会在主循环中自动判断为新趋势
        # 信号历史文件独立保存，不会被清除
        self.config.original_tp1_price = 0.0
        self.config.original_tp2_price = 0.0
        self.config.original_tp_reached = False
        # 不重置 original_regime, original_direction, original_signal_time
        # trend_continuation_count 也不重置，保持在同一趋势中的计数

        # ⚠️ 重要：不删除 signal_history.json，保留信号历史用于混合策略

        self.save_position()
    
    def send_position_update(self, current_price, current_high, current_low):
        """发送仓位状态更新"""
        if not self.config.has_position:
            return
        
        # 计算当前盈亏
        if self.config.position_type == 'long':
            profit_pct = (current_price - self.config.effective_entry_price) / self.config.effective_entry_price * 100
            to_sl_pct = (current_price - self.config.stop_loss_price) / current_price * 100 if self.config.stop_loss_price > 0 else 0
            to_tp1_pct = (self.config.tp1_price - current_price) / current_price * 100 if self.config.tp1_price > 0 else 0
            to_tp2_pct = (self.config.tp2_price - current_price) / current_price * 100 if self.config.tp2_price > 0 else 0
        else:  # short
            profit_pct = (self.config.effective_entry_price - current_price) / self.config.effective_entry_price * 100
            to_sl_pct = (self.config.stop_loss_price - current_price) / current_price * 100 if self.config.stop_loss_price > 0 else 0
            to_tp1_pct = (current_price - self.config.tp1_price) / current_price * 100 if self.config.tp1_price > 0 else 0
            to_tp2_pct = (current_price - self.config.tp2_price) / current_price * 100 if self.config.tp2_price > 0 else 0
        
        # 每30分钟发送一次更新
        current_time = datetime.now()
        if hasattr(self, 'last_update_time'):
            time_diff = (current_time - self.last_update_time).total_seconds()
            if time_diff < 1800:  # 30分钟
                return
        
        self.last_update_time = current_time
        
        hold_time = datetime.now() - self.config.entry_time
        hold_hours = hold_time.total_seconds() / 3600
        
        details = {
            "📊 实时状态": "─",
            "当前价格": f"${current_price:.2f}",
            "最高价": f"${current_high:.2f}",
            "最低价": f"${current_low:.2f}",
            "当前盈亏": f"{profit_pct:+.2f}%",
            "持仓时间": f"{hold_hours:.1f}小时",

            "🎯 目标距离": "─",
            "到止损": f"{to_sl_pct:+.2f}%",
            "到TP1": f"{to_tp1_pct:+.2f}%",
            "到TP2": f"{to_tp2_pct:+.2f}%",

            "🛡️ 风控状态": "─",
            "平均成本": f"${self.config.effective_entry_price:.2f}",
            "止损价格": f"${self.config.stop_loss_price:.2f}",
            "止盈1(TP1)": f"${self.config.tp1_price:.2f}",
            "止盈2(TP2)": f"${self.config.tp2_price:.2f}",
            "保本价格": f"${self.config.breakeven_price:.2f}",
            "追踪止损": f"${self.config.trailing_stop_price:.2f}" if self.config.trailing_stop_price > 0 else "未激活",
            "TP1状态": "已触发" if self.config.tp1_hit else "未触发",
            "追踪状态": "已激活" if self.config.trailing_activated else "未激活",

            "📈 表现统计": "─",
            "最大浮盈": f"{self.config.peak_profit_pct:+.2f}%",
            "是否加仓": "是" if self.config.add_position_taken else "否",
            "信号体制": self.config.entry_regime or "N/A"
        }
        
        self.notifier.send_alert("📊 仓位监控", 
                                f"持仓中，当前{profit_pct:+.2f}%", 
                                details,
                                urgency="normal")

# ==================== [6. 战备信号生成器 - 与回测对齐] ====================

# ==================== [7. 战备信号生成器 - V2完整版] ====================
class BattleSignalGenerator:
    """战备信号生成器 - 与回测逻辑严格对齐"""
    
    def __init__(self, config, notifier, data_fetcher, position_tracker):
        self.config = config
        self.notifier = notifier
        self.data_fetcher = data_fetcher
        self.position_tracker = position_tracker
        self.physics_engine = PhysicsDiagnosisEngine(config)
        
        self.status_file = "battle_aligned_status.json"
        self.load_status()
    
    def load_status(self):
        """加载状态"""
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    status = json.load(f)
                    self.config.battle_mode = status.get('battle_mode', False)
                    self.config.battle_start_time = datetime.fromisoformat(status.get('battle_start_time')) if status.get('battle_start_time') else None
                    self.config.battle_signal_type = status.get('battle_signal_type')
                    self.config.battle_regime_desc = status.get('battle_regime_desc', '')
                    self.config.battle_signal_price = status.get('battle_signal_price', 0.0)
                    self.config.battle_signal_confidence = status.get('battle_signal_confidence', 0.0)
                    self.config.battle_check_count = status.get('battle_check_count', 0)
            except:
                pass
    
    def save_status(self):
        """保存状态"""
        try:
            status = {
                'battle_mode': self.config.battle_mode,
                'battle_start_time': self.config.battle_start_time.isoformat() if self.config.battle_start_time else None,
                'battle_signal_type': self.config.battle_signal_type,
                'battle_regime_desc': self.config.battle_regime_desc,
                'battle_signal_price': self.config.battle_signal_price,
                'battle_signal_confidence': self.config.battle_signal_confidence,
                'battle_check_count': self.config.battle_check_count,
                'last_update': datetime.now().isoformat()
            }
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def run_normal_check(self):
        """🎯 普通模式：检查4小时物理信号 - 与回测逻辑对齐"""
        logger.info("执行普通模式检查（4小时物理信号）")
        
        try:
            btc_4h_data = self.data_fetcher.fetch_btc_data(interval='4h', limit=200)
            dxy_data = self.data_fetcher.fetch_dxy_data()
            current_price = self.data_fetcher.get_current_btc_price()
            
            if btc_4h_data is None or current_price is None:
                return
            
            # 🎯 物理诊断（与回测一致）
            btc_prices = btc_4h_data['close'].values
            
            if len(btc_prices) >= 60:
                tension, acceleration = self.physics_engine.calculate_tension_acceleration(btc_prices)
                dxy_fuel = self.physics_engine.get_dxy_fuel(dxy_data)
                
                regime_type, regime_desc, confidence = self.physics_engine.diagnose_regime(
                    tension, acceleration, dxy_fuel
                )

                logger.info(f"物理诊断: {regime_type} - {regime_desc}, 置信度: {confidence:.1%}")

                # 🎯 记录最新检测到的信号（用于 Telegram /status 显示）
                self.config.last_signal_time = datetime.now()
                self.config.last_signal_type = regime_type
                self.config.last_signal_desc = regime_desc
                self.config.last_signal_price = current_price
                self.config.last_signal_confidence = confidence

                # 🎯 检查中继信号：如果出现中继信号，重置原始趋势信息
                intermediate_signals = ['OSCILLATION', 'HIGH_OSCILLATION', 'LOW_OSCILLATION', 'TRANSITION_UP', 'TRANSITION_DOWN']
                if regime_type in intermediate_signals and self.config.original_regime is not None:
                    logger.info(f"检测到中继信号: {regime_type}，重置原始趋势信息")

                    # 重置内存中的趋势信息
                    self.config.original_tp1_price = 0.0
                    self.config.original_tp2_price = 0.0
                    self.config.original_regime = None
                    self.config.original_direction = None
                    self.config.original_signal_time = None
                    self.config.trend_continuation_count = 0
                    self.config.original_tp_reached = False

                    # 🎯 删除信号历史文件（防止重启后恢复）
                    try:
                        if os.path.exists("signal_history.json"):
                            os.remove("signal_history.json")
                            logger.info("已删除信号历史文件")
                    except Exception as e:
                        logger.error(f"删除信号历史文件失败: {e}")

                # 🎯 检测到奇点信号，进入战备模式
                if regime_type in ['BEARISH_SINGULARITY', 'BULLISH_SINGULARITY']:
                    if confidence > 0.6:
                        # 🎯 V4.1 开仓过滤检查（SKIP过滤 + 黄金阈值）
                        if self.config.enable_skip_filter:
                            should_skip, skip_reason = self.check_skip_filter(regime_type)
                            if should_skip:
                                logger.warning(f"[开仓过滤] 信号被跳过:\n{skip_reason}")
                                self.notifier.send_alert(
                                    "⚠️ 信号被过滤",
                                    f"{regime_desc}\n{skip_reason}",
                                    urgency="normal"
                                )
                                return

                        self.enter_battle_mode(regime_type, regime_desc, current_price, confidence, tension, acceleration, dxy_fuel)
                        return
                        
        except Exception as e:
            logger.error(f"普通模式检查错误: {e}")

    def check_skip_filter(self, signal_type):
        """🎯 V4.1 开仓过滤检查（SKIP过滤 + 黄金阈值过滤）

        返回: (should_skip, reason)
        - should_skip: True表示应该跳过信号
        - reason: 跳过原因的描述
        """
        try:
            # 获取LS-Ratio和FR
            ls_ratio = self.data_fetcher.get_latest_ls_ratio()
            current_fr = self.data_fetcher.get_latest_fr()

            ls_str = f"{ls_ratio:.2f}" if ls_ratio else "N/A"
            fr_str = f"{current_fr*100:.2f}%" if current_fr else "N/A"
            logger.info(f"[开仓过滤] 检查信号: {signal_type}, LS={ls_str}, FR={fr_str}")

            # ========== 1. SKIP过滤检查（极端数值）==========
            # 检查LS-Ratio是否过高
            if ls_ratio is not None and ls_ratio > self.config.skip_ls_ratio_threshold:
                reason = (f"SKIP过滤: LS-Ratio过高 ({ls_ratio:.2f} > {self.config.skip_ls_ratio_threshold})\n"
                         f"极端风险：散户拥挤度过高，胜率下降")
                logger.warning(f"[SKIP过滤] {reason}")
                return True, reason

            # 检查FR是否过低（极端负费率）
            if current_fr is not None and current_fr < self.config.skip_fr_threshold:
                reason = (f"SKIP过滤: FR过低 ({current_fr*100:.2f}% < {self.config.skip_fr_threshold*100:.0f}%)\n"
                         f"极端风险：市场过度做空，可能逼空")
                logger.warning(f"[SKIP过滤] {reason}")
                return True, reason

            # ========== 2. 黄金阈值过滤检查（仅空单）==========
            if signal_type == "BULLISH_SINGULARITY" and ls_ratio is not None:
                # 空单：检查LS-Ratio是否足够高（黄金阈值）
                if ls_ratio < self.config.GOLDEN_THRESHOLD_SHORT_SKIP:
                    reason = (f"黄金阈值过滤: LS过低 ({ls_ratio:.2f} < {self.config.GOLDEN_THRESHOLD_SHORT_SKIP})\n"
                             f"空单LS<2.0：胜率仅42.9%，回测验证避免亏损$3,467")
                    logger.warning(f"[黄金阈值] {reason}")
                    return True, reason
                else:
                    logger.info(f"[黄金阈值] 空单LS={ls_ratio:.2f} >= 2.0，胜率提升至69.6%")

            # 通过所有过滤
            logger.info(f"[开仓过滤] ✅ 信号通过所有检查（SKIP过滤 + 黄金阈值）")
            return False, ""

        except Exception as e:
            logger.error(f"开仓过滤检查失败: {e}")
            # 检查失败时不过滤，保守策略
            return False, ""

    def enter_battle_mode(self, signal_type, regime_desc, current_price, confidence, tension, acceleration, dxy_fuel):
        """🎯 进入战备模式 - 发送详细信号信息"""
        if self.config.battle_mode:
            return

        self.config.battle_mode = True
        self.config.battle_start_time = datetime.now()
        self.config.battle_signal_type = signal_type
        self.config.battle_regime_desc = regime_desc
        self.config.battle_signal_price = current_price
        self.config.battle_signal_confidence = confidence
        self.config.battle_check_count = 0

        # 🎯 发送详细战备模式通知（V4.1改进：更清晰的信息展示）
        # 明确多空方向：BEARISH = 系统看空 → 我们做多，BULLISH = 系统看涨 → 我们做空
        if signal_type == "BEARISH_SINGULARITY":
            direction_emoji = "📈 做多"
            direction_explanation = "系统看空(BEARISH) → 我们反向做多"
            entry_condition = "价格回踩至EMA21或以下"
        else:  # BULLISH_SINGULARITY
            direction_emoji = "📉 做空"
            direction_explanation = "系统看涨(BULLISH) → 我们反向做空"
            entry_condition = "价格反弹至EMA21或以上"

        position_pct = self.config.position_sizes.get(signal_type, 0.15) * 100
        add_position_pct = self.config.add_position_sizes.get(signal_type, 0.15) * 100
        total_position = position_pct + add_position_pct

        details = {
            "🎯 战备模式": "─",
            "信号类型": regime_desc,
            "交易方向": f"{direction_emoji} ({direction_explanation})",
            "置信度": f"{confidence:.1%}",
            "信号价格": f"${current_price:.2f}",
            "监控时长": f"{self.config.battle_duration_hours}小时",

            "📊 物理参数": "─",
            "物理张力": f"{tension:.3f} (阈值±{self.config.TENSION_THRESHOLD})",
            "加速度": f"{acceleration:.3f} (阈值±{self.config.ACCEL_THRESHOLD})",
            "DXY燃料": f"{dxy_fuel:.3f}",

            "💼 仓位规划": "─",
            "首次开仓": f"{position_pct:.0f}% (占位)",
            "EMA21加仓": f"{add_position_pct:.0f}% (回调加仓)",
            "总仓位": f"{total_position:.0f}%",
            "入场条件": entry_condition,
            "加仓条件": "价格回踩15分钟EMA21",
            "监控频率": f"每{self.config.battle_check_interval}分钟检查",

            "🛡️ 止盈止损": "─",
            "止损(SL)": f"-{self.config.sl_pct}% (硬止损，立即平仓)",
            "止盈1(TP1)": f"+{self.config.tp1_pct}% (激活移动止损)",
            "止盈2(TP2)": f"+{self.config.tp2_pct}% (目标止盈)",
            "移动止损": f"最高价-{self.config.trail_offset_pct}% (TP1后激活)",
            "保本止损": "TP1触发后止损移至开仓价",

            "⚠️ 重要说明": "─",
            "说明1": "反向策略：系统看跌我们做多，系统看涨我们做空",
            "说明2": f"首次开仓{position_pct:.0f}%占位，等待EMA21回调再加仓{add_position_pct:.0f}%",
            "说明3": f"止损-{self.config.sl_pct}%，TP1=+{self.config.tp1_pct}%，TP2=+{self.config.tp2_pct}%",
            "说明4": "系统高频监控，满足条件立即入场并自动跟踪止盈止损"
        }
        
        self.notifier.send_alert("进入战备模式", 
                                f"检测到{regime_desc}，等待EMA21回踩入场", 
                                details,
                                urgency="high")
        
        self.save_status()
    
    def run_battle_check(self):
        """战备模式：高频检查15分钟EMA - 每分钟检查"""
        if not self.config.battle_mode:
            return
        
        self.config.battle_check_count += 1
        logger.info(f"执行战备检查 #{self.config.battle_check_count}")
        
        try:
            # 检查是否超时
            battle_age = (datetime.now() - self.config.battle_start_time).total_seconds() / 3600
            if battle_age > self.config.battle_duration_hours:
                self.exit_battle_mode("监控超时")
                return
            
            # 获取数据
            btc_15m_data = self.data_fetcher.fetch_btc_data(interval='15m', limit=50)
            current_price = self.data_fetcher.get_current_btc_price()
            
            if btc_15m_data is None or current_price is None:
                return
            
            # 获取EMA21
            latest_15m = btc_15m_data.iloc[-1]
            current_ema = latest_15m['ema21']
            
            # 🎯 检查EMA入场条件（V4.1修复：反向交易逻辑）
            # BEARISH_SINGULARITY = 系统看空 → 我们做多 → 等价格回踩下跌到EMA21
            # BULLISH_SINGULARITY = 系统看涨 → 我们做空 → 等价格反弹上涨到EMA21
            signal_type = self.config.battle_signal_type
            entry_condition_met = False

            if signal_type == "BEARISH_SINGULARITY":
                # 我们做多：等待价格回踩到EMA21或以下
                if current_price <= current_ema:
                    entry_condition_met = True
                    logger.info(f"✅ EMA入场条件满足: 价格${current_price:.2f} ≤ EMA21 ${current_ema:.2f} (回踩到位，做多)")

            elif signal_type == "BULLISH_SINGULARITY":
                # 我们做空：等待价格反弹到EMA21或以上
                if current_price >= current_ema:
                    entry_condition_met = True
                    logger.info(f"✅ EMA入场条件满足: 价格${current_price:.2f} ≥ EMA21 ${current_ema:.2f} (反弹到位，做空)")
            
            if entry_condition_met:
                self.send_entry_signal(current_price, current_ema)
                return
            
            # 🎯 状态更新（每5次检查发送一次）
            if self.config.battle_check_count % 5 == 0:
                # V4.1修复：正确的条件判断和显示
                if signal_type == "BEARISH_SINGULARITY":
                    # 我们做多：条件是价格 ≤ EMA21
                    price_diff = current_price - current_ema  # 负数表示低于EMA
                    condition = "≤"
                    condition_desc = "等待价格回踩至EMA21或以下（做多）"
                else:
                    # 我们做空：条件是价格 ≥ EMA21
                    price_diff = current_ema - current_price  # 负数表示低于EMA（未满足）
                    condition = "≥"
                    condition_desc = "等待价格反弹至EMA21或以上（做空）"

                # 判断是否满足条件
                condition_met = (signal_type == "BEARISH_SINGULARITY" and current_price <= current_ema) or \
                                (signal_type == "BULLISH_SINGULARITY" and current_price >= current_ema)

                details = {
                    "📡 战备监控中": "─",
                    "检查次数": f"#{self.config.battle_check_count}",
                    "已监控时长": f"{battle_age:.1f}小时",
                    "剩余时长": f"{self.config.battle_duration_hours - battle_age:.1f}小时",
                    "当前价格": f"${current_price:.2f}",
                    "EMA21价格": f"${current_ema:.2f}",
                    "价格差": f"${abs(price_diff):.2f}",
                    "入场条件": f"价格 {condition} EMA21",
                    "条件说明": condition_desc,
                    "条件状态": "✅ 已满足，准备入场" if condition_met else "⏳ 未满足",
                    "信号类型": self.config.battle_regime_desc,
                    "置信度": f"{self.config.battle_signal_confidence:.1%}"
                }
                
                self.notifier.send_alert("📡 战备监控", 
                                        f"等待EMA21回踩...", 
                                        details,
                                        urgency="normal")
            
            self.save_status()
            
        except Exception as e:
            logger.error(f"战备检查错误: {e}")
    
    def send_entry_signal(self, current_price, current_ema):
        """发送入场信号 - 与回测逻辑对齐"""
        signal_type = self.config.battle_signal_type
        regime_desc = self.config.battle_regime_desc
        confidence = self.config.battle_signal_confidence
        
        # 记录开仓
        self.position_tracker.open_position(signal_type, regime_desc, current_price, current_ema, confidence)
        
        # 退出战备模式
        self.exit_battle_mode("入场成功")
    
    def exit_battle_mode(self, reason):
        """退出战备模式"""
        if not self.config.battle_mode:
            return
        
        battle_duration = (datetime.now() - self.config.battle_start_time).total_seconds() / 3600
        
        details = {
            "战备模式结束": "─",
            "结束原因": reason,
            "检查次数": f"#{self.config.battle_check_count}",
            "监控时长": f"{battle_duration:.1f}小时",
            "信号类型": self.config.battle_regime_desc,
            "信号价格": f"${self.config.battle_signal_price:.2f}",
            "最终价格": f"${self.data_fetcher.get_current_btc_price() or 0:.2f}",
            "价格变化": f"{((self.data_fetcher.get_current_btc_price() or 0) - self.config.battle_signal_price) / self.config.battle_signal_price * 100:.2f}%"
        }
        
        self.notifier.send_alert("🛑 战备模式结束", 
                                f"战备监控已结束: {reason}", 
                                details,
                                urgency="normal")
        
        # 重置状态
        self.config.battle_mode = False
        self.config.battle_start_time = None
        self.config.battle_signal_type = None
        self.config.battle_regime_desc = ""
        self.config.battle_signal_price = 0.0
        self.config.battle_signal_confidence = 0.0
        self.config.battle_check_count = 0
        
        self.save_status()

# ==================== [7. Telegram 命令处理器] ====================

# ==================== [8. Telegram命令处理器 - V2完整版] ====================
class TelegramCommandHandler:
    """Telegram 命令处理器 - 支持交互式控制"""

    def __init__(self, config, position_tracker):
        self.config = config
        self.position_tracker = position_tracker
        self.token = config.telegram_token
        self.chat_id = str(config.telegram_chat_id)

        # Telegram API URL
        self.api_url = f"https://api.telegram.org/bot{self.token}/"

        # 上次更新ID（用于获取新消息）
        self.last_update_id = 0

        # 支持的命令
        self.commands = {
            "/start": self.cmd_start,
            "/help": self.cmd_help,
            "/status": self.cmd_status,
            "/close": self.cmd_close,
            "/clear": self.cmd_clear,
            "我已平仓": self.cmd_close,
        }

    def get_updates(self, offset=None, timeout=30):
        """获取更新"""
        try:
            url = f"{self.api_url}getUpdates"
            params = {
                'offset': offset,
                'timeout': timeout,
                'allowed_updates': ['message']
            }
            response = requests.get(url, params=params, timeout=timeout + 5)
            return response.json()
        except Exception as e:
            logger.error(f"获取Telegram更新失败: {e}")
            return None

    def send_message(self, text, chat_id=None):
        """发送消息"""
        try:
            chat_id = chat_id or self.chat_id
            url = f"{self.api_url}sendMessage"
            params = {
                'chat_id': chat_id,
                'text': text,
                # 不使用parse_mode，避免特殊字符解析失败
            }
            response = requests.post(url, json=params, timeout=10)
            result = response.json()

            # 检查是否成功
            if not result.get('ok', False):
                logger.error(f"Telegram API错误: {result}")

            return result.get('ok', False)
        except Exception as e:
            logger.error(f"发送Telegram消息失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def process_message(self, message):
        """处理消息"""
        # 检查发送者
        chat_id = str(message.get('chat', {}).get('id'))
        if chat_id != self.chat_id:
            logger.warning(f"忽略非授权用户的消息: {chat_id}")
            return

        # 获取文本
        text = message.get('text', '')

        # 🎯 V4.1人机结合版：处理手动加仓的自然语言格式
        # 只有明确包含"我已加仓"才处理，避免误匹配其他命令
        if "我已加仓" in text:
            # 提取价格（支持多种格式）
            import re
            # 匹配：价格为：XXXXX / 价格:XXXXX / XXXXX等
            price_match = re.search(r'[价格为:\s]+([0-9,]+\.?[0-9]*)', text)
            if price_match:
                price_str = price_match.group(1).replace(',', '').strip()
                try:
                    add_price = float(price_str)
                    success, message = self.position_tracker.manual_add_position(add_price)
                    if success:
                        self.send_message(f"✅ 手动加仓成功\n\n{message}\n\n当前持仓：\n- 方向：{self.config.position_type}\n- 总仓位：{self.config.base_position_ratio * 100:.0f}% (首次15% + 加仓15%)\n- 平均成本：${self.config.effective_entry_price:.2f}\n- 止损价格：${self.config.stop_loss_price:.2f}\n- 止盈1(TP1)：${self.config.tp1_price:.2f}\n- 止盈2(TP2)：${self.config.tp2_price:.2f}")
                    else:
                        self.send_message(f"❌ 手动加仓失败：{message}")
                    return
                except ValueError:
                    self.send_message(f"❌ 价格格式错误：{price_str}\n请输入数字，例如：92500")
                    return
            else:
                self.send_message("❌ 未识别到价格，请使用格式：\n我已加仓 价格为：92500\n或\n/addposition 92500")
                return

        # 处理带参数的命令（例如：/addposition 92500）
        if text.startswith('/'):
            parts = text.split()
            command = parts[0].lower()  # 转换为小写，支持/STATUS、/status等
            args = parts[1:] if len(parts) > 1 else []

            # 支持命令大小写不敏感
            command_key = None
            for cmd in self.commands.keys():
                if cmd.lower() == command:
                    command_key = cmd
                    break

            if command_key:
                # 找到命令，调用它
                logger.info(f"执行命令: {command_key}")
                import inspect
                sig = inspect.signature(self.commands[command_key])
                if len(sig.parameters) > 0:
                    self.commands[command_key](args)
                else:
                    self.commands[command_key]()
            elif command == '/addposition':
                # 处理加仓命令
                logger.info(f"执行加仓命令: /addposition {args}")
                self.cmd_addposition(args)
            else:
                # 未知命令，显示帮助
                logger.warning(f"未知命令: {text}")
                self.send_message(f"❓ 未知命令: {text}\n\n请发送 /help 查看可用命令")
        else:
            # 非命令消息
            logger.info(f"收到非命令消息: {text[:50]}...")
            # 未知命令，显示帮助
            self.send_message(f"❓ 未知命令: {text}\n\n请发送 /help 查看可用命令")

    # ==================== 命令处理函数 ====================

    def cmd_start(self):
        """启动命令"""
        self.send_message("""
🤖 BTC 物理奇点预警系统

欢迎使用交互式控制！

可用命令：
/help - 查看帮助
/status - 查看当前状态
/close 或 "我已平仓" - 手动平仓
/clear - 清除所有数据

请输入命令...
        """)

    def cmd_help(self):
        """帮助命令"""
        self.send_message("""
📖 命令帮助

🔍 查看状态：
/status - 查看当前持仓和信号状态

💼 仓位操作：
/close - 手动平仓（保留信号历史）
我已平仓 - 同上（快捷方式）

🎯 手动加仓（V4.1新增）：
/addposition 价格 - 手动加仓15%
示例：/addposition 92500
      我已加仓 价格为：92500


🗑️ 数据清理：
/clear - 清除所有数据（包括信号历史）

ℹ️ 其他：
/help - 显示此帮助

💡 提示：
- 首次开仓15%，建议手动加仓15%至总30%
- 手动加仓后系统会重新计算平均成本和止盈止损

    def cmd_status(self):
        """查看状态"""
        try:
            lines = []
            lines.append("📊 当前状态")
            lines.append("=" * 40)

            # 仓位状态
            if self.config.has_position:
                direction = "做多" if self.config.position_type == 'long' else "做空"
                lines.append(f"📌 持仓状态: {direction}")
                lines.append(f"   入场价: ${self.config.effective_entry_price:.2f}")
                lines.append(f"   止损价: ${self.config.stop_loss_price:.2f}")
                lines.append(f"   TP1: ${self.config.tp1_price:.2f}")
                lines.append(f"   TP2: ${self.config.tp2_price:.2f}")
                # 安全地格式化入场时间
                if self.config.entry_time:
                    lines.append(f"   入场时间: {self.config.entry_time.strftime('%Y-%m-%d %H:%M')}")
                else:
                    lines.append("   入场时间: 未知")
            else:
                lines.append("📌 持仓状态: 空仓")

            # 🎯 最新检测信号
            if self.config.last_signal_time:
                time_diff = ""
                try:
                    hours = (datetime.now() - self.config.last_signal_time).total_seconds() / 3600
                    if hours < 1:
                        time_diff = f" ({int(hours*60)}分钟前)"
                    else:
                        time_diff = f" ({hours:.1f}小时前)"
                except:
                    time_diff = ""

                signal_desc = self.config.last_signal_desc or "未知信号"
                lines.append(f"\n🔔 最新信号: {signal_desc}{time_diff}")
                lines.append(f"   信号类型: {self.config.last_signal_type or '未知'}")
                lines.append(f"   价格: ${self.config.last_signal_price:.2f}")
                lines.append(f"   置信度: {self.config.last_signal_confidence:.1%}")
            else:
                lines.append("\n🔔 最新信号: 暂无")

            # 信号历史（首次信号）
            if self.config.original_regime:
                time_diff = ""
                try:
                    if self.config.original_signal_time:
                        hours = (datetime.now() - self.config.original_signal_time).total_seconds() / 3600
                        time_diff = f" ({hours:.1f}小时前)"
                except:
                    time_diff = ""

                lines.append(f"\n📡 首次信号: {self.config.original_regime}{time_diff}")
                lines.append(f"   原始TP1: ${self.config.original_tp1_price:.2f}")
                lines.append(f"   原始TP2: ${self.config.original_tp2_price:.2f}")
            else:
                lines.append("\n📡 首次信号: 无")

            # 战备状态
            if self.config.battle_mode:
                lines.append(f"\n⚔️ 战备模式: 激活")
                lines.append(f"   信号类型: {self.config.battle_regime_desc or '未知'}")
            else:
                lines.append(f"\n⚔️ 战备模式: 未激活")

            lines.append("=" * 40)

            self.send_message("\n".join(lines))

        except Exception as e:
            import traceback
            error_msg = f"❌ 查看状态时出错: {str(e)}\n\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.send_message(f"❌ 查看状态时出错: {str(e)}")

    def cmd_close(self):
        """手动平仓"""
        if not self.config.has_position:
            self.send_message("⚠️ 当前无持仓，无需平仓")
            return

        # 记录平仓
        self.position_tracker.reset_position()

        self.send_message("""
✅ 手动平仓成功

仓位已清除，信号历史已保留。

下次相同信号将使用混合策略：
- 新止损（最新价格）
- 旧止盈（首次信号）
        """)

    def cmd_addposition(self, args):
        """🎯 V4.1人机结合版：手动加仓命令"""
        # 检查是否有持仓
        if not self.config.has_position:
            self.send_message("⚠️ 当前无持仓，无法加仓")
            return

        # 检查是否已经加仓
        if self.config.add_position_taken:
            self.send_message("⚠️ 已经加仓过，无法再次加仓")
            return

        # 解析价格参数
        if not args or len(args) == 0:
            self.send_message("""
❌ 手动加仓失败：缺少价格参数

使用方法：
/addposition 价格

示例：
/addposition 92500
我已加仓 价格为：92500
            """)
            return

        # 尝试解析价格（支持多种格式）
        price_str = args[0].replace(',', '').replace('$', '').strip()
        try:
            add_price = float(price_str)
        except ValueError:
            self.send_message(f"❌ 价格格式错误：{price_str}\n请输入数字，例如：92500")
            return

        # 调用position_tracker的手动加仓方法
        success, message = self.position_tracker.manual_add_position(add_price)

        if success:
            self.send_message(f"""
✅ 手动加仓成功

{message}

当前持仓：
- 方向：{self.config.position_type}
- 总仓位：{self.config.base_position_ratio * 100:.0f}% (首次15% + 加仓15%)
- 平均成本：${self.config.effective_entry_price:.2f}
- 止损价格：${self.config.stop_loss_price:.2f}
- 止盈1(TP1)：${self.config.tp1_price:.2f}
- 止盈2(TP2)：${self.config.tp2_price:.2f}
            """)
        else:
            self.send_message(f"❌ 手动加仓失败：{message}")

    def cmd_clear(self):
        """清除所有数据"""
        # 清除仓位
        self.position_tracker.reset_position()

        # 清除信号历史
        try:
            if os.path.exists(self.position_tracker.signal_history_file):
                os.remove(self.position_tracker.signal_history_file)

            # 重置配置
            self.config.original_regime = None
            self.config.original_direction = None
            self.config.original_signal_time = None
            self.config.original_tp1_price = 0.0
            self.config.original_tp2_price = 0.0
            self.config.trend_continuation_count = 0

            self.send_message("""
✅ 所有数据已清除

包括：
- 持仓数据
- 信号历史
- 趋势信息

下次信号将作为新趋势处理。
            """)
        except Exception as e:
            self.send_message(f"❌ 清除失败: {e}")


    def start_listening(self):
        """开始监听（在后台线程中运行）"""
        logger.info("Telegram命令监听已启动")

        while True:
            try:
                # 获取更新
                updates = self.get_updates(offset=self.last_update_id + 1, timeout=30)

                if updates and updates.get('ok'):
                    for update in updates.get('result', []):
                        # 更新last_update_id
                        self.last_update_id = update['update_id']

                        # 处理消息
                        if 'message' in update:
                            self.process_message(update['message'])

                time.sleep(1)  # 避免过于频繁请求

            except Exception as e:
                logger.error(f"Telegram监听错误: {e}")
                time.sleep(5)  # 错误后等待5秒重试

# ==================== [8. 全局变量] ====================

# 全局变量：用于持仓风险监控
smart_ape_manager = None  # Smart Ape风险管理器（全局，V4.1）
config = None             # 配置（全局）
notifier = None           # 消息推送器（全局）

# ==================== [9. 主程序] ====================

# ==================== [10. 主程序 - V3.1集成版] ====================
def main():
    """V4.1完整版主程序 - V3.1完整功能 + Smart Ape动态风险管理"""
    print("="*80)
    print("物理奇点预警系统 V4.1 Smart Ape Edition")
    print("="*80)
    print("完整功能：V3.1所有功能 + 黄金阈值 + Smart Ape动态风险管理")
    print("数据来源：Binance实时K线 + Coinalyze (OI/FR/LS-Ratio/清算)")
    print("="*80)

    config = PhysicsSignalConfigV4_1()

    print("\n📋 系统配置 (V4.1 Smart Ape):")
    print(f"   代理启用: {'是' if config.proxy_enabled else '否'}")
    print(f"   交易对: {config.binance_symbol}")
    print(f"   物理参数: 张力阈值{config.TENSION_THRESHOLD}, 加速度阈值{config.ACCEL_THRESHOLD}")
    print(f"   止盈止损: 止损{config.sl_pct}%, TP1:{config.tp1_pct}%, TP2:{config.tp2_pct}%")
    print(f"   追踪偏移: {config.trail_offset_pct}%, TP1后激活: {'是' if config.trail_after_tp1 else '否'}")
    print(f"   基础仓位: {config.base_position_ratio*100:.0f}% = 首次{config.base_position_ratio*0.5*100:.0f}% + 加仓{config.base_position_ratio*0.5*100:.0f}%")

    # 🎯 V4.1 Smart Ape：Smart Ape配置
    print(f"\n🦍 Smart Ape动态风险管理:")
    print(f"   黄金阈值(空单): LS >= {config.GOLDEN_THRESHOLD_SHORT} (跳过LS<2.0，+4.5%收益)")
    print(f"   逻辑失效止损: LS变化±{config.LOGIC_FAILURE_LS_CHANGE} + OI下降{config.LOGIC_FAILURE_OI_CHANGE*100:.0f}%")
    print(f"   爆仓潮止盈: 清算量 > ${config.LIQUIDATION_FLUSH_95TH:,.0f} (95分位)")
    print(f"   回测验证: 768% → 803% (+4.5%)")

    # 初始化组件
    notifier = EnhancedMessageNotifier(config)
    data_fetcher = EnhancedDataFetcher(config)
    physics_engine = PhysicsDiagnosisEngine(config)
    position_tracker = PositionTracker(config, notifier)

    # 🎯 V4.1 Smart Ape：初始化Smart Ape风险管理器
    global smart_ape_manager
    smart_ape_manager = SmartApeRiskManager(config, data_fetcher)
    print(f"\n✅ Smart Ape风险管理器: 已初始化")

    battle_generator = BattleSignalGenerator(config, notifier, data_fetcher, position_tracker)

    telegram_handler = TelegramCommandHandler(config, position_tracker)

    # 启动 Telegram 监听线程
    import threading
    telegram_thread = threading.Thread(target=telegram_handler.start_listening, daemon=True)
    telegram_thread.start()
    print("   Telegram交互: 已启用")

    # 显示持仓状态摘要
    position_tracker.display_status_on_startup()

    # 测试消息
    status_msg = "有仓位，正在跟踪" if config.has_position else "无仓位，等待信号"
    test_details = {
        "🔧 系统启动": "─",
        "系统版本": "V3.1 完整版 - 三维风控 + V2全功能",
        "启动时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "当前状态": status_msg,
        "交易对": config.binance_symbol,
        "时间框架": "4H信号 + 15M入场",
        "策略类型": "物理奇点反向交易",

        "🎯 核心功能": "─",
        "物理诊断": "启用 (与回测一致)",
        "EMA入场": "启用 (15分钟EMA21)",
        "加仓机制": "启用 (EMA21回踩)",
        "止盈止损": "多级止盈 + 追踪止损",
        "混合策略": "启用 (新止损+旧止盈)",
        "滑点模型": "动态滑点计算",

        "🛡️ 三维风控 (V3.1)": "─",
        "OI监控": "实时获取Coinalyze OI",
        "FR监控": "实时获取资金费率",
        "FR_CV": "资金费率变异系数",
        "动态仓位": "0%/25%/50%/75%/100%五级",
        "极端规避": "自动识别并规避",

        "💬 Telegram交互": "─",
        "交互命令": "已启用",
        "可用命令": "/help /status /close /clear",
        "快捷平仓": '发送"我已平仓"',

        "📊 监控设置": "─",
        "普通检查": f"每{config.normal_check_interval}分钟",
        "战备检查": f"每{config.battle_check_interval}分钟",
        "仓位监控": f"每{config.position_check_interval}分钟",
        "风险评估": f"每{config.risk_check_interval}分钟",
        "战备时长": f"{config.battle_duration_hours}小时"
    }

    notifier.send_alert("🧪 系统启动成功", "V3.1完整版已启动", test_details, urgency="normal")

    # 🎯 V3.1新增：风险评估任务
    def scheduled_risk_check():
        """风险评估检查 - 每小时执行"""
        try:
            logger.info("开始执行风险评估...")

            # 更新OI和FR数据
            data_fetcher.fetch_coinalyze_oi()
            data_fetcher.fetch_coinalyze_funding_rate()

            # 🎯 V4.1修复：更新LS-Ratio和Liquidation数据（Smart Ape需要）
            logger.info("📊 更新Smart Ape数据...")
            data_fetcher.fetch_coinalyze_long_short_ratio()
            data_fetcher.fetch_coinalyze_liquidation()
            logger.info("✅ Smart Ape数据更新完成")

            logger.info("✅ 市场数据更新完成")

        except Exception as e:
            logger.error(f"风险评估错误: {e}")

    # 调度函数
    def scheduled_normal_check():
        """普通模式检查"""
        if not config.battle_mode and not config.has_position:
            battle_generator.run_normal_check()

    def scheduled_battle_check():
        """战备模式检查"""
        if config.battle_mode:
            battle_generator.run_battle_check()

    def scheduled_position_check():
        """仓位监控检查"""
        if config.has_position:
            btc_15m_data = data_fetcher.fetch_btc_data(interval='15m', limit=2)
            current_price = data_fetcher.get_current_btc_price()

            if current_price and btc_15m_data is not None and len(btc_15m_data) >= 2:
                latest_candle = btc_15m_data.iloc[-1]
                current_high = latest_candle['high']
                current_low = latest_candle['low']

                should_exit, exit_reason, exit_price = position_tracker.check_position(current_price, current_high, current_low)

                if should_exit and exit_price > 0:
                    position_tracker.close_position(exit_price, exit_reason)
                # 🎯 V4.1人机结合版：移除自动EMA21加仓，改为Telegram手动加仓
                # else:
                #     if not config.add_position_taken:
                #         current_ema = latest_candle['ema21']
                #         if position_tracker.check_add_position(current_price, current_ema):
                #             position_tracker.execute_add_position(current_price, current_ema)

    # 设置调度任务
    schedule.every(config.battle_check_interval).minutes.do(scheduled_battle_check)
    schedule.every(config.position_check_interval).minutes.do(scheduled_position_check)
    schedule.every(config.risk_check_interval).minutes.do(scheduled_risk_check)

    # 严格对齐 4 小时收盘点
    check_times = ["00:00:05", "04:00:05", "08:00:05", "12:00:05", "16:00:05", "20:00:05"]
    for t in check_times:
        schedule.every().day.at(t).do(scheduled_normal_check)

    print(f"\n✅ 系统已启动！")
    print(f"   仓位监控: 每{config.position_check_interval}分钟")
    print(f"   战备检查: 每{config.battle_check_interval}分钟")
    print(f"   风险评估: 每{config.risk_check_interval}分钟 (V3.1新增)")
    print(f"   普通检查: 严格对齐 4H 收盘整点")
    print(f"   按 Ctrl+C 停止系统")
    print("="*80)

    # 🎯 启动时立即执行一次风险评估
    print(f"\n🔍 正在执行启动时风险评估...")
    scheduled_risk_check()
    print(f"✅ 风险评估完成")

    # 启动时立即执行一次物理诊断
    print(f"\n🔍 正在执行启动时物理诊断...")
    scheduled_normal_check()
    print(f"✅ 物理诊断完成")

    # 立即执行一次仓位检查
    scheduled_position_check()

    # 计算并显示倒计时
    now = datetime.now().strftime("%H:%M:%S")
    print(f"ℹ️  当前时间 {now}，系统已进入潜伏状态")

    # 主循环
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 系统正在停止...")

        stop_details = {
            "🛑 系统停止": "─",
            "停止时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "系统状态": "已停止",
            "当前仓位": "有仓位" if config.has_position else "无仓位",
            "战备模式": "激活" if config.battle_mode else "未激活",
            "风险等级": config.current_risk_level,
            "仓位乘数": f"{config.position_multiplier:.2f}",
            "最终状态": "V3.1预警系统已安全停止"
        }

        notifier.send_alert("🛑 系统停止", "V3.1预警系统已停止", stop_details, urgency="normal")

        print("✅ 系统已安全停止")
        print("="*80)

if __name__ == "__main__":
    main()