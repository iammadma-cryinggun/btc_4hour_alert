# -*- coding: utf-8 -*-
"""
================================================================================
V7.0.8 智能交易系统 - 主程序
================================================================================
完整版本：V7.0.7 + V7.0.8黄金策略识别系统

核心升级：
1. 保留所有V7.0.7功能（信号计算、V7.0.5过滤器、ZigZag出场）
2. 新增V7.0.8黄金策略（基于6个月统计学分析）
3. 三级通知系统（原始信号、黄金开仓、黄金平仓）
4. 通知可靠性改进（3次重试、15秒超时）

使用方法：
1. 复制此文件到服务器
2. 配置.env文件中的TELEGRAM_TOKEN
3. 运行：python main_v708.py

================================================================================
"""

import sys
import os
import time

# 导入V7.0.7核心模块（完整保留）
from v707_trader_main import (
    V707TraderConfig,
    DataFetcher,
    PhysicsSignalCalculator,
    V705EntryFilter,
    V707ZigZagExitManager
)
from v707_trader_part2 import TelegramNotifier, get_beijing_time
from v707_telegram_webhook import TelegramWebhookHandler

# 导入V7.0.8黄金策略模块
from v708_golden_module import V708Config, V708GoldenDetector, V708TelegramNotifier

import logging
logger = logging.getLogger(__name__)


# ==================== [V7.0.8 交易引擎] ====================
class V708TradingEngine:
    """V7.0.8完整交易引擎（V7.0.7 + 黄金策略）"""

    def __init__(self):
        # V7.0.7核心（完整保留）
        self.config = V707TraderConfig()
        self.fetcher = DataFetcher(self.config)
        self.calculator = PhysicsSignalCalculator(self.config)
        self.filter = V705EntryFilter(self.config)
        self.exit_manager = V707ZigZagExitManager(self.config)

        # V7.0.8黄金策略
        self.v708_config = V708Config()
        self.v708_detector = V708GoldenDetector(self.v708_config)
        self.v708_notifier = V708TelegramNotifier(
            token=self.config.telegram_token,
            chat_id=self.config.telegram_chat_id,
            enabled=self.config.telegram_enabled
        )

        # Webhook模式
        self.webhandler = TelegramWebhookHandler(self.config, self)
        self.notifier = TelegramNotifier(self.config, bot_instance=self.webhandler.bot)

        # 加载状态
        self.config.load_state()

    def check_signals(self):
        """检查交易信号（每4小时）- V7.0.7逻辑 + V7.0.8黄金策略"""
        try:
            logger.info("=" * 70)
            logger.info("开始检查信号...")

            # 获取4H数据
            df_4h = self.fetcher.fetch_btc_data(interval='4h', limit=300)
            if df_4h is None:
                logger.error("获取4H数据失败")
                return

            logger.info(f"4H K线数据: {len(df_4h)}条")

            # 计算物理指标
            df_metrics = self.calculator.calculate_physics_metrics(df_4h)
            if df_metrics is None:
                logger.error("物理指标计算失败")
                return

            # 获取最新指标
            latest = df_metrics.iloc[-1]
            tension = latest['tension']
            acceleration = latest['acceleration']
            current_price = latest['close']
            current_time = df_4h.index[-1]

            # 计算量能比率
            avg_volume = df_metrics['volume'].rolling(20).mean().iloc[-1]
            volume_ratio = latest['volume'] / avg_volume if avg_volume > 0 else 1.0

            # 计算EMA偏离
            prices = df_metrics['close'].values
            ema = self.filter.calculate_ema(prices, period=20)
            price_vs_ema = (current_price - ema) / ema if ema > 0 else 0

            # 诊断信号
            signal_type, confidence, description = self.calculator.diagnose_regime(
                tension, acceleration
            )

            if signal_type is None:
                logger.info(f"无有效信号（置信度不足）")
                return

            logger.info(f"检测到信号: {signal_type} | 置信度: {confidence:.2f} | {description}")

            # ==================== V7.0.8: 发送原始信号通知 ====================
            ratio = abs(tension / acceleration) if acceleration != 0 else 0

            direction_map = {
                'BEARISH_SINGULARITY': 'short',    # 看空信号 → 做空
                'HIGH_OSCILLATION': 'short',       # 高位震荡 → 做空
                'BULLISH_SINGULARITY': 'long',     # 看涨信号 → 做多
                'LOW_OSCILLATION': 'long'          # 低位震荡 → 做多
            }
            direction = direction_map.get(signal_type)

            # 发送原始信号通知（V7.0.8新增）
            self.v708_notifier.notify_first_signal(
                signal_type=signal_type,
                tension=tension,
                acceleration=acceleration,
                volume_ratio=volume_ratio,
                price=current_price,
                timestamp=current_time.strftime('%Y-%m-%d %H:%M'),
                direction=direction,
                ratio=ratio
            )
            logger.info("[V7.0.8] 原始信号通知已发送")

            # ==================== V7.0.8: 检查首次信号 ====================
            is_signal, v708_action, v708_msg = self.v708_detector.check_first_signal(
                tension=tension,
                acceleration=acceleration,
                volume_ratio=volume_ratio,
                timestamp=current_time.strftime('%Y-%m-%d %H:%M:%S'),
                price=current_price,
                signal_type=signal_type
            )

            if not is_signal:
                logger.info(f"[V7.0.8] 非目标信号: {v708_msg}")
                return

            logger.info(f"[V7.0.8] 信号识别: {v708_msg}")

            # ==================== 记录信号到历史 ====================
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
            self.config.signal_history.append(signal_record)

            # 只保留最近20个信号
            if len(self.config.signal_history) > 20:
                self.config.signal_history = self.config.signal_history[-20:]

            # 发送信号通知（V7.0.7保留）
            self.notifier.notify_signal(
                signal_type, confidence, description,
                current_price, tension, acceleration
            )
            logger.info(f"价格: ${current_price:.2f} | 张力: {tension:.3f} | 加速度: {acceleration:.3f}")
            logger.info(f"量能比率: {volume_ratio:.2f} | EMA偏离: {price_vs_ema*100:.2f}%")

            # 保存最新信号
            self.config.last_signal_time = current_time
            self.config.last_signal_type = signal_type
            self.config.last_signal_desc = description
            self.config.last_signal_price = current_price
            self.config.last_signal_confidence = confidence

            # ==================== V7.0.7 过滤器（完整保留） ====================
            should_pass, filter_reason = self.filter.apply_filter(
                signal_type, acceleration, volume_ratio, price_vs_ema, df_metrics
            )

            if not should_pass:
                logger.warning(f"[V7.0.5过滤器] {filter_reason}")
                self.config.signal_history[-1]['filtered'] = True
                self.config.signal_history[-1]['filter_reason'] = filter_reason
                self.config.signal_history[-1]['traded'] = False
                self.notifier.send_message(f"""🚫 信号被V7.0.5过滤器拦截

📊 信号: {signal_type}
💰 价格: ${current_price:.2f}
🚫 原因: {filter_reason}""")
                return

            logger.info(f"[V7.0.5过滤器] {filter_reason}")

            # 检查是否已有持仓
            if self.config.has_position:
                logger.info("已有持仓，忽略新信号")
                self.config.signal_history[-1]['filtered'] = True
                self.config.signal_history[-1]['filter_reason'] = '已有持仓，忽略新信号'
                self.config.signal_history[-1]['traded'] = False
                self.notifier.send_message(f"""⏸️ 信号被忽略

📊 信号: {signal_type}
💰 价格: ${current_price:.2f}
⏸️ 原因: 已有持仓（{self.config.position_type.upper()} @ ${self.config.entry_price:.2f}）""")
                return

            # ==================== V7.0.8: 判断开仓方式 ====================
            if v708_action == 'direct_enter':
                # 直接开仓（符合黄金标准）
                logger.info(f"[V7.0.8] 直接触发开仓")
                self._open_position(
                    direction=direction,
                    price=current_price,
                    time=current_time,
                    signal_type=signal_type,
                    confidence=confidence,
                    is_golden=True
                )

            elif v708_action == 'wait_confirm':
                # 等待确认（记录到V7.0.8待确认信号）
                logger.info(f"[V7.0.8] 等待4-6周期确认黄金机会")
                self.config.signal_history[-1]['filtered'] = False
                self.config.signal_history[-1]['filter_reason'] = '等待V7.0.8确认'
                self.config.signal_history[-1]['traded'] = False

        except Exception as e:
            logger.error(f"检查信号异常: {e}", exc_info=True)

    def check_golden_entry(self):
        """检查黄金开仓机会（每个周期）- V7.0.8新增"""
        try:
            if not self.config.has_position:
                # 获取当前数据
                df_4h = self.fetcher.fetch_btc_data(interval='4h', limit=300)
                if df_4h is None:
                    return

                df_metrics = self.calculator.calculate_physics_metrics(df_4h)
                if df_metrics is None:
                    return

                latest = df_metrics.iloc[-1]
                current_price = latest['close']
                current_time = df_4h.index[-1]

                # 检查黄金开仓
                entries = self.v708_detector.check_golden_entry(
                    current_tension=latest['tension'],
                    current_accel=latest['acceleration'],
                    current_volume=latest['volume'] / df_metrics['volume'].rolling(20).mean().iloc[-1],
                    current_price=current_price,
                    current_time=current_time.strftime('%Y-%m-%d %H:%M:%S')
                )

                # 处理所有确认的开仓机会
                for entry in entries:
                    logger.info(f"[V7.0.8] 检测到{'黄金' if entry['is_golden'] else '普通'}开仓机会")
                    logger.info(f"  方向: {entry['direction']}")
                    logger.info(f"  张力变化: {entry['tension_change']:+.2f}%")
                    logger.info(f"  价格优势: {entry['price_advantage']:+.2f}%")
                    logger.info(f"  等待周期: {entry['wait_period']}")

                    # 发送黄金开仓通知
                    self.v708_notifier.notify_golden_entry(
                        entry_info=entry,
                        fallback_tp=self.config.FALLBACK_TP,
                        fallback_sl=self.config.FALLBACK_SL
                    )

                    # 开仓
                    self._open_position(
                        direction=entry['direction'],
                        price=entry['entry_price'],
                        time=current_time,
                        signal_type='GOLDEN_ENTRY',
                        confidence=0.8 if entry['is_golden'] else 0.6,
                        is_golden=entry['is_golden'],
                        entry_info=entry
                    )

        except Exception as e:
            logger.error(f"检查黄金开仓异常: {e}", exc_info=True)

    def _open_position(self, direction, price, time, signal_type, confidence,
                       is_golden=False, entry_info=None):
        """开仓（统一方法）"""
        try:
            # 计算固定止盈止损
            if direction == 'long':
                tp = price * 1.05  # +5%
                sl = price * 0.975  # -2.5%
            else:
                tp = price * 0.95  # -5%
                sl = price * 1.025  # +2.5%

            logger.info(f"[开仓] {direction.upper()} @ ${price:.2f}")
            logger.info(f"  止盈: ${tp:.2f} ({(tp/price - 1)*100:+.2f}%)")
            logger.info(f"  止损: ${sl:.2f} ({(sl/price - 1)*100:+.2f}%)")
            logger.info(f"  {'黄金机会' if is_golden else '普通机会'}")

            # 开仓
            self.config.has_position = True
            self.config.position_type = direction
            self.config.entry_price = price
            self.config.entry_time = time
            self.config.position_size = self.config.BASE_POSITION_SIZE
            self.config.entry_signal_type = signal_type
            self.config.entry_confidence = confidence
            self.config.take_profit_price = tp
            self.config.stop_loss_price = sl

            # 保存V7.0.8额外信息
            if entry_info:
                self.config.entry_tension = entry_info.get('entry_tension', 0.0)

            # 保存状态
            self.config.save_state()

            # 发送V7.0.7通知
            self.notifier.notify_entry(direction, price, signal_type, confidence, tp, sl)

            logger.info("开仓成功！")

        except Exception as e:
            logger.error(f"开仓异常: {e}", exc_info=True)

    def check_position(self):
        """检查持仓状态（每1小时）- V7.0.8黄金平仓 + 固定止盈止损"""
        try:
            if not self.config.has_position:
                return

            logger.info("-" * 70)
            logger.info("检查持仓状态...")

            # 获取4H数据（只需要4H数据，不需要1H数据）
            df_4h = self.fetcher.fetch_btc_data(interval='4h', limit=300)
            if df_4h is None:
                logger.error("获取4H数据失败")
                return

            current_price = df_4h.iloc[-1]['close']
            current_time = df_4h.index[-1]
            hold_periods = (len(df_4h) - 1) - self.config.entry_index

            logger.info(f"持仓时长: {hold_periods}周期 | 当前价格: ${current_price:.2f}")

            # 计算当前盈亏
            if self.config.position_type == 'long':
                pnl_pct = (current_price - self.config.entry_price) / self.config.entry_price
            else:
                pnl_pct = (self.config.entry_price - current_price) / self.config.entry_price

            logger.info(f"当前盈亏: {pnl_pct*100:+.2f}%")

            # ==================== 检查固定止盈止损 ====================
            tp_hit = False
            sl_hit = False

            if self.config.position_type == 'long':
                if current_price >= self.config.take_profit_price:
                    tp_hit = True
                    reason = f"固定止盈(+{(self.config.take_profit_price/self.config.entry_price - 1)*100:.1f}%)"
                elif current_price <= self.config.stop_loss_price:
                    sl_hit = True
                    reason = f"固定止损({(self.config.stop_loss_price/self.config.entry_price - 1)*100:.1f}%)"
            else:  # short
                if current_price <= self.config.take_profit_price:
                    tp_hit = True
                    reason = f"固定止盈(+{(self.config.entry_price/self.config.take_profit_price - 1)*100:.1f}%)"
                elif current_price >= self.config.stop_loss_price:
                    sl_hit = True
                    reason = f"固定止损({(self.config.stop_loss_price/self.config.entry_price - 1)*100:.1f}%)"

            if tp_hit or sl_hit:
                logger.info(f"[固定止盈止损] {reason}")
                self._close_position(current_price, reason, pnl_pct, 'fallback')
                return

            # ==================== V7.0.8: 黄金平仓检查 ====================
            position = {
                'direction': self.config.position_type,
                'entry_price': self.config.entry_price,
                'entry_time': self.config.entry_time.strftime('%Y-%m-%d %H:%M:%S') if self.config.entry_time else 'N/A',
                'entry_tension': getattr(self.config, 'entry_tension', 0.0)
            }

            df_metrics = self.calculator.calculate_physics_metrics(df_4h)
            if df_metrics is not None:
                latest = df_metrics.iloc[-1]
                avg_volume = df_metrics['volume'].rolling(20).mean().iloc[-1]
                volume_ratio = latest['volume'] / avg_volume if avg_volume > 0 else 1.0

                should_exit_v708, reason_v708, exit_type_v708 = self.v708_detector.check_golden_exit(
                    position=position,
                    current_tension=latest['tension'],
                    current_accel=latest['acceleration'],
                    current_volume=volume_ratio,
                    current_price=current_price,
                    hold_periods=hold_periods
                )

                if should_exit_v708 and exit_type_v708 == 'golden':
                    logger.info(f"[V7.0.8] 黄金平仓触发: {reason_v708}")
                    self._close_position(current_price, reason_v708, pnl_pct, exit_type_v708)
                    return

        except Exception as e:
            logger.error(f"检查持仓异常: {e}", exc_info=True)

    def _close_position(self, exit_price, reason, pnl_pct, exit_type):
        """平仓（统一方法）"""
        try:
            logger.info(f"[平仓] {self.config.position_type.upper()} @ ${exit_price:.2f}")
            logger.info(f"  盈亏: {pnl_pct*100:+.2f}%")
            logger.info(f"  原因: {reason}")
            logger.info(f"  类型: {'黄金平仓' if exit_type == 'golden' else '固定止损'}")

            # 更新统计
            self.config.total_trades += 1
            if pnl_pct > 0:
                self.config.winning_trades += 1
            else:
                self.config.losing_trades += 1
            self.config.total_pnl += pnl_pct * 100

            # 记录交易历史
            trade_record = {
                'entry_time': self.config.entry_time.strftime('%Y-%m-%d %H:%M:%S') if self.config.entry_time else 'N/A',
                'direction': self.config.position_type,
                'entry_price': self.config.entry_price,
                'exit_price': exit_price,
                'pnl_pct': pnl_pct * 100,
                'reason': reason,
                'signal_type': self.config.entry_signal_type,
                'confidence': self.config.entry_confidence,
                'take_profit': self.config.take_profit_price,
                'stop_loss': self.config.stop_loss_price
            }
            self.config.position_history.append(trade_record)

            # 只保留最近20笔交易
            if len(self.config.position_history) > 20:
                self.config.position_history = self.config.position_history[-20:]

            # ==================== V7.0.8: 发送黄金平仓通知 ====================
            position = {
                'direction': self.config.position_type,
                'entry_price': self.config.entry_price,
                'entry_time': self.config.entry_time.strftime('%Y-%m-%d %H:%M:%S') if self.config.entry_time else 'N/A',
                'exit_time': exit_price
            }

            self.v708_notifier.notify_golden_exit(
                position=position,
                exit_reason=reason,
                exit_price=exit_price,
                pnl=pnl_pct * 100,
                exit_type=exit_type
            )

            # 发送V7.0.7通知
            self.notifier.notify_exit(
                self.config.position_type,
                self.config.entry_price,
                exit_price,
                pnl_pct * 100,
                reason
            )

            # 重置状态
            self.config.has_position = False
            self.config.position_type = None
            self.config.entry_price = None
            self.config.entry_time = None
            self.config.take_profit_price = None
            self.config.stop_loss_price = None

            # 保存状态
            self.config.save_state()

            logger.info("平仓成功！")

        except Exception as e:
            logger.error(f"平仓异常: {e}", exc_info=True)

    def run_telegram_polling(self):
        """运行Telegram轮询"""
        while True:
            try:
                logger.info("[Telegram] Polling启动...")
                self.webhandler.bot.polling(
                    non_stop=False,
                    interval=1,
                    timeout=60,
                    long_polling_timeout=20
                )
            except Exception as e:
                logger.error(f"[Telegram] Polling异常: {e}")
                logger.info("[Telegram] 5秒后重新启动...")
                time.sleep(5)

    def run(self, start_flask=False):
        """主循环"""
        logger.info("=" * 70)
        logger.info("V7.0.8 智能交易系统启动（V7.0.7 + 黄金策略）")
        logger.info("=" * 70)
        logger.info(f"Telegram Token: {self.config.telegram_token[:20]}...")
        logger.info(f"Telegram Chat ID: {self.config.telegram_chat_id}")
        logger.info(f"Telegram Enabled: {self.config.telegram_enabled}")
        logger.info("")

        # 启动时通知
        self.notifier.send_message("""🚀 V7.0.8系统启动成功！

✅ 保留所有V7.0.7功能
✨ 新增黄金策略识别系统
📊 基于统计学分析（6个月数据）
🔔 三级通知系统（带重试机制）""")

        # 启动Telegram Polling
        if self.config.telegram_enabled and self.webhandler.enabled:
            import threading
            telegram_thread = threading.Thread(
                target=self.run_telegram_polling,
                daemon=False
            )
            telegram_thread.start()
            logger.info("[系统] Telegram Polling已启动（后台线程）")
        else:
            logger.warning("[系统] Telegram未启用")

        # 定时任务
        logger.info("定时任务已设置：")
        logger.info("  - 信号检查: 北京时间 0:00, 4:00, 8:00, 12:00, 16:00, 20:00")
        logger.info("  - 黄金开仓检查: 每小时（V7.0.8新增）")
        logger.info("  - 持仓检查: 每1小时")
        logger.info("")

        # 主循环
        logger.info("进入主循环...")
        logger.info("=" * 70)

        last_signal_check_hour = None
        last_position_check_hour = None

        while True:
            try:
                # 获取当前北京时间
                now_beijing = get_beijing_time()
                current_hour = now_beijing.hour
                current_minute = now_beijing.minute

                # 信号检查：4H K线收盘时间
                if current_hour % 4 == 0 and current_minute < 5:
                    if last_signal_check_hour != current_hour:
                        logger.info(f"[定时] 触发信号检查（北京时间 {now_beijing.strftime('%H:%M')}）")
                        self.check_signals()
                        last_signal_check_hour = current_hour

                # 黄金开仓检查：每1小时（V7.0.8新增）
                if current_minute < 1:
                    if last_position_check_hour != current_hour:
                        logger.info(f"[定时] 触发黄金开仓检查（北京时间 {now_beijing.strftime('%H:%M')}）")
                        self.check_golden_entry()
                        self.check_position()
                        last_position_check_hour = current_hour

                # 每秒检查一次
                time.sleep(1)

            except KeyboardInterrupt:
                logger.info("收到停止信号，正在退出...")
                break
            except Exception as e:
                logger.error(f"主循环异常: {e}", exc_info=True)
                time.sleep(60)


# ==================== [主入口] ====================
if __name__ == "__main__":
    engine = V708TradingEngine()
    engine.run()
