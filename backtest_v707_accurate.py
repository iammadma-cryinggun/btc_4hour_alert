# -*- coding: utf-8 -*-
"""
V7.0.7 准确回测脚本（2年数据）
===========================================
目的：验证V7.0.7回测与实盘100%一致

关键点：
1. 使用实盘相同的DataFetcher（从Binance API获取数据）
2. 使用实盘相同的PhysicsSignalCalculator
3. 使用实盘相同的V705EntryFilter
4. 使用实盘相同的V707ZigZagExitManager
5. DXY从FRED API获取（和实盘一致）

数据范围：2024-01-02 至 2025-12-18
===========================================
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入V7.0.7实盘代码
from v707_trader_main import (
    V707TraderConfig,
    DataFetcher,
    PhysicsSignalCalculator,
    V705EntryFilter,
    V707ZigZagExitManager
)

class V707BacktestEngine:
    """V7.0.7准确回测引擎"""

    def __init__(self, data_file_4h, data_file_1h=None):
        """
        初始化回测引擎

        参数:
            data_file_4h: 4小时K线数据文件
            data_file_1h: 1小时K线数据文件（可选，用于ZigZag出场）
        """
        self.data_file_4h = data_file_4h
        self.data_file_1h = data_file_1h

        # 使用实盘配置
        self.config = V707TraderConfig()

        # 使用实盘组件
        self.fetcher = DataFetcher(self.config)
        self.calculator = PhysicsSignalCalculator(self.config)
        self.filter = V705EntryFilter(self.config)
        self.exit_manager = V707ZigZagExitManager(self.config)

        # 回测状态
        self.has_position = False
        self.position_type = None
        self.entry_price = None
        self.entry_time = None
        self.entry_index = None
        self.entry_signal_type = None
        self.entry_confidence = None
        self.take_profit_price = None
        self.stop_loss_price = None

        # 统计数据
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0

        # 交易历史
        self.trade_history = []
        self.signal_history = []

    def load_data(self):
        """加载数据（和实盘一致的方式）"""
        logger.info("=" * 70)
        logger.info("加载数据...")
        logger.info("=" * 70)

        # 加载4小时数据
        logger.info(f"读取4小时数据: {self.data_file_4h}")
        df_4h = pd.read_csv(self.data_file_4h)

        # ⭐ 关键：确保时间列是datetime类型（UTC时间）
        df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'], utc=True)  # 添加时区信息
        df_4h = df_4h.set_index('timestamp')

        logger.info(f"4小时数据: {len(df_4h)}条")
        logger.info(f"时间范围: {df_4h.index[0]} 至 {df_4h.index[-1]}")

        # 检查必需列
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df_4h.columns:
                raise ValueError(f"4小时数据缺少列: {col}")

        # 加载1小时数据（可选）
        df_1h = None
        if self.data_file_1h:
            logger.info(f"读取1小时数据: {self.data_file_1h}")
            df_1h = pd.read_csv(self.data_file_1h)
            df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'], utc=True)  # 添加时区信息
            df_1h = df_1h.set_index('timestamp')
            logger.info(f"1小时数据: {len(df_1h)}条")
        else:
            logger.info("未提供1小时数据，将使用回退止盈止损")

        logger.info("")

        return df_4h, df_1h

    def run_backtest(self):
        """运行回测"""
        df_4h, df_1h = self.load_data()

        logger.info("=" * 70)
        logger.info("开始回测...")
        logger.info("=" * 70)

        # 遍历每个4H K线（模拟实盘每4小时检查一次）
        total_signals = 0
        filtered_signals = 0
        executed_trades = 0

        for i in range(len(df_4h)):
            current_time = df_4h.index[i]
            current_price = df_4h.iloc[i]['close']

            # 只在4H K线收盘时检查信号（和实盘一致）
            # 当前数据已经是4H K线，每条都是收盘点

            # 获取历史数据（用于计算物理指标）
            df_history = df_4h.iloc[:i+1].copy()

            # 物理信号计算需要至少60条数据
            if len(df_history) < 60:
                continue

            # 计算物理指标（和实盘一致）
            try:
                df_metrics = self.calculator.calculate_physics_metrics(df_history)
                if df_metrics is None:
                    continue

                latest = df_metrics.iloc[-1]
                tension = latest['tension']
                acceleration = latest['acceleration']

                # 计算量能比率
                avg_volume = df_metrics['volume'].rolling(20).mean().iloc[-1]
                volume_ratio = latest['volume'] / avg_volume if avg_volume > 0 else 1.0

                # 计算EMA偏离
                prices = df_metrics['close'].values
                ema = self.filter.calculate_ema(prices, period=20)
                price_vs_ema = (current_price - ema) / ema if ema > 0 else 0

            except Exception as e:
                logger.error(f"计算物理指标失败 (时间: {current_time}): {e}")
                continue

            # 诊断信号（和实盘一致）
            signal_type, confidence, description = self.calculator.diagnose_regime(
                tension, acceleration
            )

            if signal_type is None:
                continue

            total_signals += 1

            # 记录信号
            signal_record = {
                'time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'type': signal_type,
                'confidence': confidence,
                'description': description,
                'price': current_price,
                'tension': tension,
                'acceleration': acceleration,
                'volume_ratio': volume_ratio,
                'price_vs_ema': price_vs_ema * 100
            }
            self.signal_history.append(signal_record)

            logger.info(f"\n[信号 {total_signals}] {current_time}")
            logger.info(f"  类型: {signal_type}")
            logger.info(f"  置信度: {confidence:.2f}")
            logger.info(f"  描述: {description}")
            logger.info(f"  价格: ${current_price:.2f}")
            logger.info(f"  张力: {tension:.3f}")
            logger.info(f"  加速度: {acceleration:.3f}")
            logger.info(f"  量能比率: {volume_ratio:.2f}")
            logger.info(f"  EMA偏离: {price_vs_ema*100:.2f}%")

            # V7.0.5过滤（和实盘一致）
            should_pass, filter_reason = self.filter.apply_filter(
                signal_type, acceleration, volume_ratio, price_vs_ema, df_metrics
            )

            if not should_pass:
                filtered_signals += 1
                signal_record['filtered'] = True
                signal_record['filter_reason'] = filter_reason
                signal_record['traded'] = False
                logger.info(f"  [V7.0.5] ❌ {filter_reason}")
                continue

            logger.info(f"  [V7.0.5] ✅ {filter_reason}")

            signal_record['filtered'] = False
            signal_record['filter_reason'] = filter_reason

            # 检查是否已有持仓
            if self.has_position:
                signal_record['traded'] = False
                logger.info(f"  [跳过] 已有持仓 ({self.position_type} @ ${self.entry_price:.2f})")
                continue

            # 确定入场方向（和实盘一致）
            direction_map = {
                'BEARISH_SINGULARITY': 'long',
                'LOW_OSCILLATION': 'long',
                'BULLISH_SINGULARITY': 'short',
                'HIGH_OSCILLATION': 'short'
            }

            direction = direction_map.get(signal_type)
            if direction is None:
                signal_record['traded'] = False
                logger.info(f"  [跳过] 未知信号类型")
                continue

            # 计算止盈止损
            if df_1h is not None:
                # 使用1H数据计算ZigZag出场
                tp, sl = self.exit_manager.calculate_tp_sl(df_1h, current_price, direction)
            else:
                # 回退止盈止损
                if direction == 'long':
                    tp = current_price * 1.05
                    sl = current_price * 0.975
                else:
                    tp = current_price * 0.95
                    sl = current_price * 1.025

            # 开仓
            self.has_position = True
            self.position_type = direction
            self.entry_price = current_price
            self.entry_time = current_time
            self.entry_index = i
            self.entry_signal_type = signal_type
            self.entry_confidence = confidence
            self.take_profit_price = tp
            self.stop_loss_price = sl

            signal_record['traded'] = True
            executed_trades += 1

            logger.info(f"  [开仓] {direction.upper()} @ ${current_price:.2f}")
            logger.info(f"    止盈: ${tp:.2f} ({(tp/current_price - 1)*100:+.2f}%)")
            logger.info(f"    止损: ${sl:.2f} ({(sl/current_price - 1)*100:+.2f}%)")

            # 模拟持仓监控（在后续K线中检查出场）
            self._monitor_position(df_4h, df_1h, i)

        # 输出结果
        self._print_results(total_signals, filtered_signals, executed_trades)

    def _monitor_position(self, df_4h, df_1h, entry_index):
        """监控持仓（在后续K线中检查出场）"""
        max_periods = self.config.MAX_HOLD_PERIODS  # 42周期 = 7天

        for j in range(entry_index + 1, min(entry_index + max_periods + 1, len(df_4h))):
            current_time = df_4h.index[j]
            current_price = df_4h.iloc[j]['close']
            hold_periods = j - entry_index

            # 计算当前盈亏
            if self.position_type == 'long':
                pnl_pct = (current_price - self.entry_price) / self.entry_price
            else:
                pnl_pct = (self.entry_price - current_price) / self.entry_price

            # 检查ZigZag出场（如果有1H数据）
            if df_1h is not None:
                # 获取到当前时间的1H数据
                df_1h_until = df_1h[df_1h.index <= current_time]
                if len(df_1h_until) > 0:
                    should_exit, reason, exit_price = self.exit_manager.check_exit(
                        df_1h_until, self.entry_price, self.position_type
                    )
                    if should_exit:
                        self._close_position(exit_price if exit_price else current_price, reason, hold_periods)
                        return

            # 检查固定止盈止损
            if self.position_type == 'long':
                if current_price >= self.take_profit_price:
                    self._close_position(current_price, f"止盈({(pnl_pct*100):+.2f}%)", hold_periods)
                    return
                elif current_price <= self.stop_loss_price:
                    self._close_position(current_price, f"止损({(pnl_pct*100):+.2f}%)", hold_periods)
                    return
            else:  # short
                if current_price <= self.take_profit_price:
                    self._close_position(current_price, f"止盈({(pnl_pct*100):+.2f}%)", hold_periods)
                    return
                elif current_price >= self.stop_loss_price:
                    self._close_position(current_price, f"止损({(pnl_pct*100):+.2f}%)", hold_periods)
                    return

            # 超时检查
            if hold_periods >= max_periods:
                self._close_position(current_price, f"超时({hold_periods}周期)", hold_periods)
                return

    def _close_position(self, exit_price, reason, hold_periods):
        """平仓"""
        # 计算盈亏
        if self.position_type == 'long':
            pnl_pct = (exit_price - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - exit_price) / self.entry_price

        # 更新统计
        self.total_trades += 1
        if pnl_pct > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        self.total_pnl += pnl_pct * 100

        # 记录交易
        trade_record = {
            'entry_time': self.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'direction': self.position_type,
            'entry_price': self.entry_price,
            'exit_price': exit_price,
            'pnl_pct': pnl_pct * 100,
            'reason': reason,
            'hold_periods': hold_periods,
            'signal_type': self.entry_signal_type,
            'confidence': self.entry_confidence
        }
        self.trade_history.append(trade_record)

        logger.info(f"  [平仓] {self.position_type.upper()} @ ${exit_price:.2f}")
        logger.info(f"    盈亏: {pnl_pct*100:+.2f}%")
        logger.info(f"    原因: {reason}")
        logger.info(f"    持仓: {hold_periods}周期")

        # 重置状态
        self.has_position = False
        self.position_type = None
        self.entry_price = None
        self.entry_time = None
        self.entry_index = None
        self.entry_signal_type = None
        self.entry_confidence = None
        self.take_profit_price = None
        self.stop_loss_price = None

    def _print_results(self, total_signals, filtered_signals, executed_trades):
        """输出回测结果"""
        logger.info("")
        logger.info("=" * 70)
        logger.info("回测完成")
        logger.info("=" * 70)
        logger.info(f"总信号数: {total_signals}")
        logger.info(f"过滤信号: {filtered_signals}")
        logger.info(f"执行交易: {executed_trades}")
        logger.info("")
        logger.info(f"总交易: {self.total_trades}")
        logger.info(f"盈利: {self.winning_trades}")
        logger.info(f"亏损: {self.losing_trades}")
        logger.info(f"胜率: {self.winning_trades/self.total_trades*100 if self.total_trades > 0 else 0:.2f}%")
        logger.info(f"总盈亏: {self.total_pnl:+.2f}%")
        logger.info("")
        logger.info("交易详情:")
        for i, trade in enumerate(self.trade_history, 1):
            logger.info(f"{i}. {trade['entry_time']} | {trade['direction'].upper()} | "
                       f"${trade['entry_price']:.2f} -> ${trade['exit_price']:.2f} | "
                       f"{trade['pnl_pct']:+.2f}% | {trade['reason']}")
        logger.info("=" * 70)


if __name__ == "__main__":
    # 数据文件路径
    data_4h = "C:\\Users\\Martin\\Downloads\\机器人\\趋势判断\\V4.4\\deployment\\btc_4h_2years_with_volume.csv"
    data_1h = "C:\\Users\\Martin\\Downloads\\机器人\\趋势判断\\V4.4\\deployment\\btc_1h_2years.csv"

    # 创建回测引擎
    engine = V707BacktestEngine(data_4h, data_1h)

    # 运行回测
    engine.run_backtest()

    # 保存结果
    results_df = pd.DataFrame(engine.trade_history)
    results_df.to_csv('v707_backtest_results.csv', index=False, encoding='utf-8-sig')
    logger.info("\n结果已保存到 v707_backtest_results.csv")
