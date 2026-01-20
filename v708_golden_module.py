# -*- coding: utf-8 -*-
"""
V7.0.8 升级模块 - 黄金策略识别器
基于6个月统计学分析的好机会识别系统

独立模块，可与V7.0.7系统集成使用
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class V708Config:
    """V7.0.8配置参数"""

    def __init__(self):
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

        # V7.0.8最优平仓参数
        self.SHORT_EXIT_ENERGY_EXPAND = 1.0
        self.SHORT_EXIT_MIN_PERIOD = 5
        self.SHORT_EXIT_MAX_PERIOD = 10
        self.SHORT_EXIT_TENSION_DROP = 0.14  # 14%
        self.SHORT_EXIT_PROFIT_TARGET = 0.02  # 2%

        self.LONG_EXIT_ENERGY_EXPAND = 1.0
        self.LONG_EXIT_MIN_PERIOD = 7
        self.LONG_EXIT_MAX_PERIOD = 10
        self.LONG_EXIT_PROFIT_TARGET = 0.02  # 2%

        # 固定止盈止损（保留V7.0.7）
        self.FALLBACK_TP = 0.05  # +5%
        self.FALLBACK_SL = -0.025  # -2.5%


class V708GoldenDetector:
    """V7.0.8黄金机会识别器"""

    def __init__(self, config):
        self.config = config
        self.pending_signals = {}  # 待确认的信号
        self.waiting_periods = {}  # 等待周期计数

    def check_first_signal(self, tension, acceleration, volume_ratio, timestamp, price, signal_type):
        """
        检查是否为首次信号（需要等待确认）

        返回: (is_signal, action, message)
        action: 'direct_enter' | 'wait_confirm' | 'ignore'
        """

        # 计算张力/加速度比
        ratio = abs(tension / acceleration) if acceleration != 0 else 0

        message_detail = f"T={tension:.4f}, a={acceleration:.6f}, E={volume_ratio:.2f}, 比例={ratio:.1f}"

        if signal_type in ['BEARISH_SINGULARITY', 'HIGH_OSCILLATION']:
            # SHORT信号判断
            if tension < self.config.SHORT_TENSION_MIN:
                return False, 'ignore', f"张力过低: {message_detail}"

            # 判断是否可以直接开仓
            can_direct = (
                tension >= self.config.SHORT_TENSION_DIRECT and
                self.config.SHORT_ENERGY_IDEAL_MIN <= volume_ratio <= self.config.SHORT_ENERGY_IDEAL_MAX and
                self.config.SHORT_RATIO_MIN <= ratio <= self.config.SHORT_RATIO_MAX
            )

            if can_direct:
                return True, 'direct_enter', f"【直接开仓SHORT】: {message_detail}"
            else:
                # 记录为待确认信号
                self.pending_signals[timestamp] = {
                    'direction': 'short',
                    'tension': tension,
                    'acceleration': acceleration,
                    'volume_ratio': volume_ratio,
                    'price': price,
                    'ratio': ratio,
                    'signal_type': signal_type
                }
                self.waiting_periods[timestamp] = 0
                return True, 'wait_confirm', f"【等待确认SHORT】: {message_detail}"

        elif signal_type in ['BULLISH_SINGULARITY', 'LOW_OSCILLATION']:
            # LONG信号判断
            if tension > self.config.LONG_TENSION_MAX:
                return False, 'ignore', f"张力过高: {message_detail}"

            # 判断是否可以直接开仓
            can_direct = (
                tension <= self.config.LONG_TENSION_STRONG and
                ratio >= self.config.LONG_RATIO_MIN
            )

            if can_direct:
                return True, 'direct_enter', f"【直接开仓LONG】: {message_detail}"
            else:
                # 记录为待确认信号
                self.pending_signals[timestamp] = {
                    'direction': 'long',
                    'tension': tension,
                    'acceleration': acceleration,
                    'volume_ratio': volume_ratio,
                    'price': price,
                    'ratio': ratio,
                    'signal_type': signal_type
                }
                self.waiting_periods[timestamp] = 0
                return True, 'wait_confirm', f"【等待确认LONG】: {message_detail}"

        return False, 'ignore', f"非目标信号: {message_detail}"

    def check_golden_entry(self, current_tension, current_accel, current_volume,
                           current_price, current_time):
        """
        检查是否达到黄金开仓条件

        返回: list of entry_info
        """
        confirmed_entries = []

        # 检查所有待确认信号
        for timestamp, signal in list(self.pending_signals.items()):
            self.waiting_periods[timestamp] += 1
            wait_period = self.waiting_periods[timestamp]

            direction = signal['direction']
            orig_tension = signal['tension']
            orig_price = signal['price']

            # 清理超过最大等待周期的信号
            if wait_period > 10:
                del self.pending_signals[timestamp]
                del self.waiting_periods[timestamp]
                logger.info(f"[V7.0.8] 信号超时移除: {timestamp}")
                continue

            if direction == 'short':
                # SHORT黄金确认条件
                ratio = current_tension / abs(current_accel) if current_accel != 0 else 0

                is_confirmed = (
                    current_tension > 0.45 and
                    current_accel < 0 and
                    current_volume < 1.0 and
                    self.config.SHORT_WAIT_MIN <= wait_period <= self.config.SHORT_WAIT_MAX
                )

                if is_confirmed:
                    tension_change = (current_tension - orig_tension) / orig_tension * 100
                    price_advantage = (orig_price - current_price) / orig_price * 100

                    # 判断是否为黄金机会
                    is_golden = (
                        tension_change > 5 or price_advantage > 0.5
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

                    confirmed_entries.append(entry_info)
                    logger.info(f"[V7.0.8] SHORT黄金机会确认: T变化={tension_change:.2f}%, 价格优势={price_advantage:.2f}%")

                    # 移除已确认的信号
                    del self.pending_signals[timestamp]
                    del self.waiting_periods[timestamp]

            elif direction == 'long':
                # LONG黄金确认条件
                ratio = abs(current_tension) / current_accel if current_accel != 0 else 0

                is_confirmed = (
                    current_tension < -0.45 and
                    current_accel > 0 and
                    current_volume < 1.0 and
                    self.config.LONG_WAIT_MIN <= wait_period <= self.config.LONG_WAIT_MAX
                )

                if is_confirmed:
                    # LONG的张力是负数，使用绝对值计算变化率
                    tension_change = (abs(current_tension) - abs(orig_tension)) / abs(orig_tension) * 100
                    price_advantage = (current_price - orig_price) / orig_price * 100

                    # 判断是否为黄金机会
                    # LONG的tension_change是负数时表示张力绝对值减小（向好），使用绝对值判断
                    is_golden = (
                        abs(tension_change) > 5 or price_advantage > 0.5 or ratio >= 100
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

                    confirmed_entries.append(entry_info)
                    logger.info(f"[V7.0.8] LONG黄金机会确认: T变化={tension_change:.2f}%, 价格优势={price_advantage:.2f}%")

                    # 移除已确认的信号
                    del self.pending_signals[timestamp]
                    del self.waiting_periods[timestamp]

        return confirmed_entries

    def check_golden_exit(self, position, current_tension, current_accel,
                         current_volume, current_price, hold_periods):
        """
        检查是否达到黄金平仓条件

        返回: (should_exit, exit_reason, exit_type)
        exit_type: 'golden' | 'fallback'
        """
        direction = position['direction']
        entry_price = position['entry_price']
        entry_tension = position['entry_tension']

        # 计算当前盈亏
        if direction == 'short':
            pnl = (entry_price - current_price) / entry_price * 100
        else:
            pnl = (current_price - entry_price) / entry_price * 100

        # 先检查固定止损
        if pnl <= self.config.FALLBACK_SL * 100:
            return True, f"固定止损({pnl:.2f}%)", 'fallback'
        if pnl >= self.config.FALLBACK_TP * 100:
            return True, f"固定止盈({pnl:.2f}%)", 'fallback'

        # 检查黄金平仓条件
        if direction == 'short':
            tension_change = (current_tension - entry_tension) / entry_tension * 100

            should_exit = (
                (current_volume > self.config.SHORT_EXIT_ENERGY_EXPAND or
                 hold_periods >= self.config.SHORT_EXIT_MIN_PERIOD)
            ) and (
                tension_change <= -self.config.SHORT_EXIT_TENSION_DROP * 100 or
                pnl >= self.config.SHORT_EXIT_PROFIT_TARGET * 100
            )

            if should_exit:
                reasons = []
                if current_volume > self.config.SHORT_EXIT_ENERGY_EXPAND:
                    reasons.append(f"量能放大({current_volume:.2f})")
                if hold_periods >= self.config.SHORT_EXIT_MIN_PERIOD:
                    reasons.append(f"持仓{hold_periods}周期")
                if tension_change <= -self.config.SHORT_EXIT_TENSION_DROP * 100:
                    reasons.append(f"张力下降{abs(tension_change):.1f}%")
                if pnl >= self.config.SHORT_EXIT_PROFIT_TARGET * 100:
                    reasons.append(f"盈利{pnl:.2f}%")

                return True, f"黄金平仓: {', '.join(reasons)}", 'golden'

            # 强制平仓
            if hold_periods >= self.config.SHORT_EXIT_MAX_PERIOD:
                return True, f"强制平仓: 持仓{hold_periods}周期", 'golden'

        else:  # long
            # LONG的张力是负数，使用绝对值计算变化率
            tension_change = (abs(current_tension) - abs(entry_tension)) / abs(entry_tension) * 100

            should_exit = (
                (current_volume > self.config.LONG_EXIT_ENERGY_EXPAND or
                 hold_periods >= self.config.LONG_EXIT_MIN_PERIOD)
            ) and (
                tension_change < 0 or  # 张力不再增加（绝对值开始减小）
                pnl >= self.config.LONG_EXIT_PROFIT_TARGET * 100
            )

            if should_exit:
                reasons = []
                if current_volume > self.config.LONG_EXIT_ENERGY_EXPAND:
                    reasons.append(f"量能放大({current_volume:.2f})")
                if hold_periods >= self.config.LONG_EXIT_MIN_PERIOD:
                    reasons.append(f"持仓{hold_periods}周期")
                if tension_change > 0:
                    reasons.append("张力不再增加")
                if pnl >= self.config.LONG_EXIT_PROFIT_TARGET * 100:
                    reasons.append(f"盈利{pnl:.2f}%")

                return True, f"黄金平仓: {', '.join(reasons)}", 'golden'

            # 强制平仓
            if hold_periods >= self.config.LONG_EXIT_MAX_PERIOD:
                return True, f"强制平仓: 持仓{hold_periods}周期", 'golden'

        return False, "持仓中", None


class V708TelegramNotifier:
    """V7.0.8三级通知系统"""

    def __init__(self, token, chat_id, enabled=True):
        self.token = token
        self.chat_id = chat_id
        self.enabled = enabled

    def send(self, message, priority='normal'):
        """发送Telegram消息"""
        if not self.enabled:
            return

        try:
            import requests
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }

            # 增加重试机制
            for attempt in range(3):
                try:
                    resp = requests.post(url, json=data, timeout=15)
                    if resp.status_code == 200:
                        logger.info(f"[Telegram] 发送成功")
                        return True
                    else:
                        logger.warning(f"[Telegram] 发送失败: {resp.status_code}, {resp.text}")
                except Exception as e:
                    logger.error(f"[Telegram] 发送异常(尝试{attempt+1}/3): {e}")
                    import time
                    time.sleep(2)

            return False

        except Exception as e:
            logger.error(f"[Telegram] 通知异常: {e}")
            return False

    def notify_first_signal(self, signal_type, tension, acceleration, volume_ratio,
                           price, timestamp, direction, ratio):
        """通知1: 原始信号"""
        emoji = "🔴" if direction == 'short' else "🟢"
        direction_cn = "做空SHORT" if direction == 'short' else "做多LONG"

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
⏳ 等待确认中...
"""

        self.send(message, priority='normal')

    def notify_golden_entry(self, entry_info, fallback_tp, fallback_sl):
        """通知2: 黄金开仓"""
        direction = entry_info['direction']
        is_golden = entry_info['is_golden']

        if direction == 'short':
            emoji = "🔴" if is_golden else "⚪"
            direction_cn = "做空SHORT"
            emoji_level = "✨✨✨" if is_golden else "✨"
            tp_price = entry_info['entry_price'] * (1 - fallback_tp)
            sl_price = entry_info['entry_price'] * (1 - fallback_sl)
        else:
            emoji = "🟢" if is_golden else "⚪"
            direction_cn = "做多LONG"
            emoji_level = "✨✨✨" if is_golden else "✨"
            tp_price = entry_info['entry_price'] * (1 + fallback_tp)
            sl_price = entry_info['entry_price'] * (1 + fallback_sl)

        entry_price = entry_info['entry_price']
        entry_tension = entry_info['entry_tension']
        wait_period = entry_info['wait_period']
        tension_change = entry_info['tension_change']
        price_advantage = entry_info['price_advantage']

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
🎯 止盈: ${tp_price:.2f} (+{fallback_tp*100:.1f}%)
🛡️ 止损: ${sl_price:.2f} ({fallback_sl*100:.1f}%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{emoji} {'黄金机会！' if is_golden else '普通机会'}
"""

        self.send(message, priority='high' if is_golden else 'normal')

    def notify_golden_exit(self, position, exit_reason, exit_price, pnl, exit_type):
        """通知3: 黄金平仓"""
        direction = position['direction']

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
⏰ 入场时间: {position.get('entry_time', 'N/A')}
💰 入场价格: ${position['entry_price']:.2f}
⏰ 平仓时间: {position.get('exit_time', 'N/A')}
💰 平仓价格: ${exit_price:.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 盈亏: {pnl:+.2f}%
📝 原因: {exit_reason}
🏷️ 类型: {'黄金平仓' if exit_type == 'golden' else '固定止损'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        self.send(message, priority='high' if exit_type == 'golden' else 'normal')
