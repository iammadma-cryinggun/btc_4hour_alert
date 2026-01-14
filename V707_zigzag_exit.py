# -*- coding: utf-8 -*-
"""
V7.0.7 出场策略：基于ZigZag转折点的动态止盈止损

核心理念：
- 入场：V7.0.5过滤器（量能、EMA）
- 出场：ZigZag转折点作为支撑/阻力位

逻辑：
┌─────────────┐
│ V7.0.5入场 │
└──────┬──────┘
       │ 开仓
       ↓
┌─────────────┐
│ZigZag转折点 │ → 实时检测最近的支撑/阻力位
└──────┬──────┘
       │
       ↓
┌─────────────┐
│动态止盈止损 │ → 基于最近的peak/valley
└─────────────┘

优势：
1. 转折点自动适应市场波动
2. 止盈止损基于实际价格结构
3. 不依赖固定百分比
4. 1H K线转折点丰富（71个），适合实时检测
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional, List


class V707ZigZagExitManager:
    """V7.0.7 ZigZag转折点出场管理器"""

    def __init__(self, depth=12, deviation=5):
        """
        初始化

        参数:
            depth: ZigZag深度（默认12）
            deviation: ZigZag偏差阈值（默认5）
        """
        self.depth = depth
        self.deviation = deviation

        # 当前持仓信息
        self.entry_price = None
        self.entry_time = None
        self.entry_signal_type = None
        self.entry_direction = None  # 'long' or 'short'

        # 检测到的转折点
        self.pivots = []

        # 止盈止损位
        self.take_profit_price = None
        self.stop_loss_price = None

        # 固定止盈止损（回退方案）
        self.fallback_tp_pct = 0.05  # +5%
        self.fallback_sl_pct = -0.025  # -2.5%

    def detect_zigzag(self, df: pd.DataFrame) -> List[dict]:
        """
        检测ZigZag转折点

        参数:
            df: K线数据

        返回:
            List[dict]: 转折点列表 [{'index': int, 'price': float, 'type': 'peak'/'valley', 'time': timestamp}]
        """
        pivots = []
        highs = df['high'].values
        lows = df['low'].values

        for i in range(self.depth, len(df) - self.depth):
            # 检查是否为高点
            is_high = True
            for j in range(1, self.depth + 1):
                if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                    is_high = False
                    break

            if is_high:
                pivots.append({
                    'index': i,
                    'price': highs[i],
                    'type': 'peak',
                    'time': df.iloc[i]['timestamp']
                })
                continue

            # 检查是否为低点
            is_low = True
            for j in range(1, self.depth + 1):
                if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                    is_low = False
                    break

            if is_low:
                pivots.append({
                    'index': i,
                    'price': lows[i],
                    'type': 'valley',
                    'time': df.iloc[i]['timestamp']
                })

        return pivots

    def on_position_open(self, entry_price, entry_time, signal_type, direction, df_klines):
        """
        开仓时调用，初始化转折点检测并设置止盈止损

        参数:
            entry_price: 入场价
            entry_time: 入场时间
            signal_type: 信号类型
            direction: 'long' or 'short'
            df_klines: K线数据
        """
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.entry_signal_type = signal_type
        self.entry_direction = direction

        # 检测所有转折点
        self.pivots = self.detect_zigzag(df_klines)

        # 设置止盈止损
        self.take_profit_price, self.stop_loss_price = self._calculate_tp_sl(df_klines)

        print(f"\n[ZigZag出场] 初始化检测")
        print(f"  入场价: ${entry_price:.2f}")
        print(f"  方向: {direction}")
        print(f"  信号: {signal_type}")
        print(f"  检测到{len(self.pivots)}个转折点")
        print(f"  止盈: ${self.take_profit_price:.2f} ({(self.take_profit_price/entry_price - 1)*100:+.2f}%)")
        print(f"  止损: ${self.stop_loss_price:.2f} ({(self.stop_loss_price/entry_price - 1)*100:+.2f}%)")

    def _calculate_tp_sl(self, df_klines) -> Tuple[float, float]:
        """
        基于转折点计算止盈止损

        逻辑：
        做多：
          - 止损：最近的valley下方（入场价 - (入场价 - 最近valley) * 1.2）
          - 止盈：最近的peak上方（入场价 + (最近peak - 入场价) * 1.2）

        做空：
          - 止损：最近的peak上方（入场价 + (最近peak - 入场价) * 1.2）
          - 止盈：最近的valley下方（入场价 - (入场价 - 最近valley) * 1.2）

        返回: (take_profit_price, stop_loss_price)
        """
        if len(self.pivots) == 0:
            # 没有转折点，使用固定止盈止损
            if self.entry_direction == 'long':
                return self.entry_price * (1 + self.fallback_tp_pct), self.entry_price * (1 + self.fallback_sl_pct)
            else:
                return self.entry_price * (1 - self.fallback_tp_pct), self.entry_price * (1 - self.fallback_sl_pct)

        # 找到入场价前后的转折点
        entry_pivot_idx = None
        for i, pivot in enumerate(self.pivots):
            if pivot['price'] == self.entry_price:
                entry_pivot_idx = i
                break

        # 根据方向查找最近的支撑/阻力位
        if self.entry_direction == 'long':
            # 做多：找最近的valley作为止损参考
            valleys = [p for p in self.pivots if p['type'] == 'valley']
            peaks = [p for p in self.pivots if p['type'] == 'peak']

            # 止损：最近的valley下方
            if len(valleys) > 0:
                # 找到入场价之前最近的valley
                recent_valley = None
                for valley in reversed(valleys):
                    if valley['price'] < self.entry_price:
                        recent_valley = valley
                        break

                if recent_valley:
                    # 止损在valley下方1.2倍距离（给点缓冲）
                    sl_distance = (self.entry_price - recent_valley['price']) * 1.2
                    stop_loss = self.entry_price - sl_distance
                else:
                    # 没有找到valley，使用固定止损
                    stop_loss = self.entry_price * (1 + self.fallback_sl_pct)
            else:
                stop_loss = self.entry_price * (1 + self.fallback_sl_pct)

            # 止盈：最近的peak上方
            if len(peaks) > 0:
                # 找到入场价之后最近的peak
                recent_peak = None
                for peak in peaks:
                    if peak['price'] > self.entry_price:
                        recent_peak = peak
                        break

                if recent_peak:
                    # 止盈在peak上方1.2倍距离（确保突破）
                    tp_distance = (recent_peak['price'] - self.entry_price) * 1.2
                    take_profit = self.entry_price + tp_distance
                else:
                    # 没有找到peak，使用固定止盈
                    take_profit = self.entry_price * (1 + self.fallback_tp_pct)
            else:
                take_profit = self.entry_price * (1 + self.fallback_tp_pct)

        else:  # short
            # 做空：找最近的peak作为止损参考
            valleys = [p for p in self.pivots if p['type'] == 'valley']
            peaks = [p for p in self.pivots if p['type'] == 'peak']

            # 止损：最近的peak上方（使用更紧的止损）
            if len(peaks) > 0:
                # 找到入场价之前最近的peak
                recent_peak = None
                for peak in reversed(peaks):
                    if peak['price'] > self.entry_price:
                        recent_peak = peak
                        break

                if recent_peak:
                    # 止损在peak和入场价的中点（更紧的止损）
                    sl_distance = (recent_peak['price'] - self.entry_price) * 0.5
                    stop_loss = self.entry_price + sl_distance

                    # 如果止损距离超过3%，使用固定3%止损
                    if sl_distance / self.entry_price > 0.03:
                        stop_loss = self.entry_price * (1 - self.fallback_sl_pct)
                else:
                    # 没有找到peak，使用固定止损
                    stop_loss = self.entry_price * (1 - self.fallback_sl_pct)
            else:
                stop_loss = self.entry_price * (1 - self.fallback_sl_pct)

            # 止盈：最近的valley下方
            if len(valleys) > 0:
                # 找到入场价之后最近的valley
                recent_valley = None
                for valley in valleys:
                    if valley['price'] < self.entry_price:
                        recent_valley = valley
                        break

                if recent_valley:
                    # 止盈在valley下方1.2倍距离
                    tp_distance = (self.entry_price - recent_valley['price']) * 1.2
                    take_profit = self.entry_price - tp_distance
                else:
                    # 没有找到valley，使用固定止盈
                    take_profit = self.entry_price * (1 - self.fallback_tp_pct)
            else:
                take_profit = self.entry_price * (1 - self.fallback_tp_pct)

        return take_profit, stop_loss

    def check_exit(self, current_price, df_klines):
        """
        检查是否达到止盈或止损

        返回: (should_exit, reason, exit_price)
        """
        if self.entry_price is None:
            return False, "无持仓", None

        # 更新转折点（实时检测）
        self.pivots = self.detect_zigzag(df_klines)

        # 动态更新止盈止损（基于最新转折点）
        self.take_profit_price, self.stop_loss_price = self._calculate_tp_sl(df_klines)

        # 检查止损
        if self.entry_direction == 'long':
            if current_price <= self.stop_loss_price:
                return True, f"ZigZag止损(${self.stop_loss_price:.2f})", self.stop_loss_price
            elif current_price >= self.take_profit_price:
                return True, f"ZigZag止盈(${self.take_profit_price:.2f})", self.take_profit_price
        else:  # short
            if current_price >= self.stop_loss_price:
                return True, f"ZigZag止损(${self.stop_loss_price:.2f})", self.stop_loss_price
            elif current_price <= self.take_profit_price:
                return True, f"ZigZag止盈(${self.take_profit_price:.2f})", self.take_profit_price

        return False, "持仓中", None


# ==================== 使用示例 ====================
if __name__ == "__main__":
    """
    测试ZigZag出场策略
    """
    print("=" * 70)
    print("V7.0.7 ZigZag出场策略测试")
    print("=" * 70)

    # 读取1H数据
    df_klines = pd.read_csv('btc_1h_dec2025_jan2026_with_volume.csv')
    df_klines['timestamp'] = pd.to_datetime(df_klines['timestamp'], utc=True)

    print(f"\n1H K线数据: {len(df_klines)}条")

    # 创建出场管理器
    exit_manager = V707ZigZagExitManager(depth=12, deviation=5)

    # 模拟一笔交易
    entry_time = pd.to_datetime('2025-12-13 20:00:00+00:00', utc=True)
    entry_price = 88644.88
    signal_type = 'BEARISH_SINGULARITY'
    direction = 'long'

    # 初始化
    exit_manager.on_position_open(entry_price, entry_time, signal_type, direction, df_klines)

    print(f"\n模拟持仓:")
    print(f"  入场: {entry_time}")
    print(f"  价格: ${entry_price:.2f}")
    print(f"  方向: {direction}")

    # 检测不同时间的出场
    test_hours = [8, 24, 48, 96, 168]

    for hold_hours in test_hours:
        test_time = entry_time + pd.Timedelta(hours=hold_hours)

        # 获取到该时间的K线
        df_until = df_klines[df_klines['timestamp'] <= test_time]

        if len(df_until) < 50:
            continue

        current_price = df_until.iloc[-1]['close']

        # 检查出场的
        should_exit, reason, exit_price = exit_manager.check_exit(current_price, df_until)

        print(f"\n{hold_hours}小时后 (${current_price:.2f}):")
        print(f"  止盈: ${exit_manager.take_profit_price:.2f}")
        print(f"  止损: ${exit_manager.stop_loss_price:.2f}")

        if should_exit:
            print(f"  [EXIT] {reason}")
        else:
            print(f"  [HOLD] {reason}")

    print("\n" + "=" * 70)
