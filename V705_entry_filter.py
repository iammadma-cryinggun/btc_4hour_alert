# -*- coding: utf-8 -*-
"""
V7.0.6 入场策略：V7.0.5 + 谐波模式双重确认

架构：
┌─────────────┐
│ V7.0.5过滤器 │ → 第一层过滤：量能、EMA、主升/跌浪
└──────┬──────┘
       │ 通过
       ↓
┌─────────────┐
│ 谐波模式确认 │ → 第二层过滤：ABCD/Gartley/Butterfly形态
└──────┬──────┘
       │ 确认
       ↓
┌─────────────┐
│  最终入场信号 │
└─────────────┘

优势：
1. 保留V7.0.5已验证的有效过滤逻辑
2. 增加谐波模式的形态确认
3. 入场质量更高，假信号更少
4. 逻辑统一（基于斐波那契比例）
"""

import pandas as pd
import numpy as np
from harmonic_patterns import HarmonicPatternDetector, HarmonicPattern

class V706EntryFilter:
    """V7.0.6入场过滤器（V7.0.5 + 谐波模式）"""

    def __init__(self):
        # V7.0.5参数
        self.BULLISH_VOLUME_THRESHOLD = 0.95
        self.HIGH_OSC_EMA_THRESHOLD = 0.02
        self.HIGH_OSC_VOLUME_THRESHOLD = 1.1
        self.BEARISH_EMA_THRESHOLD = -0.05

        # 谐波模式检测器
        self.harmonic_detector = HarmonicPatternDetector(tolerance=0.15)  # 容差放宽到15%

        # 缓存谐波模式（避免重复计算）
        self.cached_patterns = None
        self.cached_patterns_time = None

    def calculate_ema_standard(self, prices, period=20):
        """标准EMA计算"""
        if len(prices) < period:
            return prices[-1]
        return pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1]

    def apply_v705_filter(self, signal_type, acceleration, volume_ratio, price_vs_ema, dxy_fuel=None):
        """
        V7.0.5过滤器（第一层）

        返回: (should_pass, reason)
        """
        if signal_type == 'HIGH_OSCILLATION':
            # 牛市回调
            if price_vs_ema > self.HIGH_OSC_EMA_THRESHOLD:
                return False, f"牛市回调(价格>EMA {price_vs_ema*100:.1f}%)"

            # 动能向上
            if acceleration >= 0:
                return False, f"无向下动能(a={acceleration:.3f})"

            # 高位放量
            if volume_ratio > self.HIGH_OSC_VOLUME_THRESHOLD:
                return False, f"高位放量({volume_ratio:.2f})"

            return True, "通过V7.0.5"

        elif signal_type == 'LOW_OSCILLATION':
            # V7.0.5：完全移除过滤
            return True, "通过V7.0.5"

        elif signal_type == 'BULLISH_SINGULARITY':
            # 量能阈值
            if volume_ratio > self.BULLISH_VOLUME_THRESHOLD:
                return False, f"量能放大({volume_ratio:.2f})"

            # 主升浪过滤
            if price_vs_ema > 0.05:
                return False, f"主升浪(偏离{price_vs_ema*100:.1f}%)"

            return True, "通过V7.0.5"

        elif signal_type == 'BEARISH_SINGULARITY':
            # 主跌浪过滤
            if price_vs_ema < self.BEARISH_EMA_THRESHOLD:
                return False, f"主跌浪(偏离{price_vs_ema*100:.1f}%)"

            return True, "通过V7.0.5"

        return True, "通过V7.0.5"

    def detect_recent_harmonic_patterns(self, df, current_time, lookback_hours=48):
        """
        检测最近的谐波模式（第二层）

        参数:
            df: K线数据
            current_time: 当前时间
            lookback_hours: 回溯时间（默认48小时=12根4H K线）

        返回:
            List[HarmonicPattern]: 最近48小时的谐波模式
        """
        # 只取最近的数据（提高性能）
        recent_df = df.tail(200).copy()

        # 检测所有谐波模式
        all_patterns = self.harmonic_detector.detect_all_patterns(recent_df)

        # 筛选出最近48小时的模式
        recent_patterns = []
        for pattern_type, patterns in all_patterns.items():
            for pattern in patterns:
                time_diff = (current_time - pattern.entry_time).total_seconds() / 3600
                if time_diff <= lookback_hours:
                    recent_patterns.append(pattern)

        return recent_patterns

    def check_harmonic_confirmation(self, signal_type, signal_direction, current_price, recent_patterns):
        """
        谐波模式确认（第二层）

        逻辑：
        1. 看涨信号 → 检测是否有看涨谐波模式在附近完成
        2. 看跌信号 → 检测是否有看跌谐波模式在附近完成
        3. 如果没有谐波模式，仍然可以入场（但不加分）
        4. 如果有谐波模式，增加置信度

        返回: (confirmed, confidence_boost, reason)
        """
        if len(recent_patterns) == 0:
            return True, 0.0, "无谐波模式确认（允许入场）"

        # 检查是否有匹配方向的谐波模式
        matching_patterns = []
        for pattern in recent_patterns:
            # 检查方向是否匹配
            if signal_type == 'LOW_OSCILLATION' or signal_type == 'BEARISH_SINGULARITY':
                # 做多信号 → 需要看涨谐波模式
                if pattern.direction == 'bullish':
                    # 检查D点（入场点）是否接近当前价格
                    price_diff = abs(pattern.entry_price - current_price) / current_price
                    if price_diff < 0.01:  # 1%以内
                        matching_patterns.append(pattern)

            elif signal_type == 'HIGH_OSCILLATION' or signal_type == 'BULLISH_SINGULARITY':
                # 做空信号 → 需要看跌谐波模式
                if pattern.direction == 'bearish':
                    price_diff = abs(pattern.entry_price - current_price) / current_price
                    if price_diff < 0.01:  # 1%以内
                        matching_patterns.append(pattern)

        if len(matching_patterns) == 0:
            return True, 0.0, "无匹配谐波模式（允许入场）"

        # 找到置信度最高的模式
        best_pattern = max(matching_patterns, key=lambda p: p.confidence)

        # 根据模式类型给予置信度加权
        pattern_bonus = {
            'ABCD': 0.05,
            'Gartley': 0.10,
            'Butterfly': 0.15,
            'Bat': 0.12,
            'Crab': 0.12,
        }.get(best_pattern.pattern_type, 0.05)

        confidence_boost = best_pattern.confidence * pattern_bonus

        return True, confidence_boost, f"谐波{best_pattern.pattern_type}确认(C+{confidence_boost:.2f})"

    def apply_v706_filter(self, signal_type, acceleration, volume_ratio, price_vs_ema,
                          current_price, current_time, df_klines, dxy_fuel=None):
        """
        V7.0.6完整过滤逻辑（V7.0.5 + 谐波模式）

        返回: (should_trade, reason, confidence_boost)
        """
        # 第一层：V7.0.5过滤
        v705_pass, v705_reason = self.apply_v705_filter(
            signal_type, acceleration, volume_ratio, price_vs_ema, dxy_fuel
        )

        if not v705_pass:
            return False, v705_reason, 0.0

        # 第二层：谐波模式确认
        recent_patterns = self.detect_recent_harmonic_patterns(df_klines, current_time)
        harmonic_pass, confidence_boost, harmonic_reason = self.check_harmonic_confirmation(
            signal_type,
            'long' if signal_type in ['LOW_OSCILLATION', 'BEARISH_SINGULARITY'] else 'short',
            current_price,
            recent_patterns
        )

        if not harmonic_pass:
            return False, harmonic_reason, 0.0

        final_reason = f"{v705_reason} + {harmonic_reason}"
        return True, final_reason, confidence_boost


# ==================== 使用示例 ====================
if __name__ == "__main__":
    """
    测试V7.0.6过滤器
    """
    print("=" * 70)
    print("V7.0.6 过滤器测试：V7.0.5 + 谐波模式")
    print("=" * 70)

    # 创建过滤器
    v706_filter = V706EntryFilter()

    # 读取数据
    df_replay = pd.read_csv('信号复盘_12月1日至今_20260114_115930.csv')
    df_klines = pd.read_csv('btc_4h_dec2025_jan2026_with_volume.csv')
    df_pnl = pd.read_csv('12月复盘_含盈亏.csv')

    # 统一时间为UTC
    df_klines['timestamp'] = pd.to_datetime(df_klines['timestamp'], utc=True)
    df_replay['time_utc'] = pd.to_datetime(df_replay['时间']).dt.tz_localize('Asia/Shanghai').dt.tz_convert('UTC')
    df_pnl['time_utc'] = pd.to_datetime(df_pnl['时间']).dt.tz_localize('Asia/Shanghai').dt.tz_convert('UTC')

    # 只看可交易的信号
    tradable = df_replay[df_replay['可交易'] == '是'].copy()

    print(f"\n12月复盘可交易信号: {len(tradable)}笔")

    # 应用V7.0.6过滤
    tradable['v706_should_trade'] = True
    tradable['v706_filter_reason'] = ""
    tradable['v706_confidence_boost'] = 0.0

    for idx, row in tradable.iterrows():
        should_trade, reason, confidence_boost = v706_filter.apply_v706_filter(
            row['信号类型'],
            row['加速度'],
            row.get('量能比率', 1.0),  # 如果没有量能数据，默认为1.0
            row.get('价格vsEMA', 0.0),  # 如果没有价格数据，默认为0.0
            row.get('入场价', 0),
            row['time_utc'],
            df_klines
        )

        tradable.at[idx, 'v706_should_trade'] = should_trade
        tradable.at[idx, 'v706_filter_reason'] = reason
        tradable.at[idx, 'v706_confidence_boost'] = confidence_boost

    # 合并盈亏数据
    df = df_pnl.merge(tradable[['time_utc', 'v706_should_trade', 'v706_filter_reason', 'v706_confidence_boost']], on='time_utc')

    # 统计
    v706_passed = df[df['v706_should_trade'] == True]
    v706_filtered = df[~df['v706_should_trade']]

    print(f"\nV7.0.6过滤结果:")
    print(f"  通过: {len(v706_passed)}笔")
    print(f"  过滤: {len(v706_filtered)}笔")
    print(f"  通过率: {len(v706_passed)/len(df)*100:.1f}%")

    print(f"\nV7.0.6 vs V7.0.1盈亏对比:")
    print(f"  V7.0.1全部: {df['pnl_pct'].sum()*100:+.2f}%")
    print(f"  V7.0.6通过: {v706_passed['pnl_pct'].sum()*100:+.2f}%")
    print(f"  改善: {(v706_passed['pnl_pct'].sum() - df['pnl_pct'].sum())*100:+.2f}%")

    print(f"\n谐波模式确认统计:")
    harmonic_confirmed = v706_passed[v706_passed['v706_filter_reason'].str.contains('谐波', na=False)]
    print(f"  有谐波确认: {len(harmonic_confirmed)}笔")
    print(f"  无谐波确认: {len(v706_passed) - len(harmonic_confirmed)}笔")

    print("=" * 70)
