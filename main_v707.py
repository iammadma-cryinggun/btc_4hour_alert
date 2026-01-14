# -*- coding: utf-8 -*-
"""
================================================================================
V7.0.7 智能交易系统 - 主程序
================================================================================
完整版本：集成V7.0.5过滤器 + V7.0.7 ZigZag动态止盈止损

使用方法：
1. 复制此文件到服务器
2. 配置.env文件中的TELEGRAM_TOKEN
3. 运行：python main_v707.py

================================================================================
"""

import sys
import os
import time
import schedule

# 导入主模块
from v707_trader_main import (
    V707TraderConfig,
    DataFetcher,
    PhysicsSignalCalculator,
    V705EntryFilter,
    V707ZigZagExitManager,
    TelegramNotifier
)

import logging
logger = logging.getLogger(__name__)


# ==================== [V7.0.7 交易引擎] ====================
class V707TradingEngine:
    """V7.0.7完整交易引擎"""

    def __init__(self):
        self.config = V707TraderConfig()
        self.fetcher = DataFetcher(self.config)
        self.calculator = PhysicsSignalCalculator(self.config)
        self.filter = V705EntryFilter(self.config)
        self.exit_manager = V707ZigZagExitManager(self.config)
        self.notifier = TelegramNotifier(self.config)

        # 加载状态
        self.config.load_state()

    def check_signals(self):
        """检查交易信号（每4小时）"""
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
            logger.info(f"价格: ${current_price:.2f} | 张力: {tension:.3f} | 加速度: {acceleration:.3f}")
            logger.info(f"量能比率: {volume_ratio:.2f} | EMA偏离: {price_vs_ema*100:.2f}%")

            # 保存最新信号
            self.config.last_signal_time = current_time
            self.config.last_signal_type = signal_type
            self.config.last_signal_desc = description
            self.config.last_signal_price = current_price
            self.config.last_signal_confidence = confidence

            # V7.0.5过滤
            should_pass, filter_reason = self.filter.apply_filter(
                signal_type, acceleration, volume_ratio, price_vs_ema, df_metrics
            )

            if not should_pass:
                logger.warning(f"[V7.0.5过滤器] {filter_reason}")
                return

            logger.info(f"[V7.0.5过滤器] {filter_reason}")

            # 检查是否已有持仓
            if self.config.has_position:
                logger.info("已有持仓，忽略新信号")
                return

            # 确定入场方向
            direction_map = {
                'BEARISH_SINGULARITY': 'long',
                'LOW_OSCILLATION': 'long',
                'BULLISH_SINGULARITY': 'short',
                'HIGH_OSCILLATION': 'short'
            }

            direction = direction_map.get(signal_type)
            if direction is None:
                logger.warning(f"未知信号类型: {signal_type}")
                return

            # 计算止盈止损（使用1H数据）
            df_1h = self.fetcher.fetch_btc_data(interval='1h', limit=300)
            if df_1h is None:
                logger.warning("获取1H数据失败，使用回退止盈止损")
                if direction == 'long':
                    tp = current_price * 1.05
                    sl = current_price * 0.975
                else:
                    tp = current_price * 0.95
                    sl = current_price * 1.025
            else:
                tp, sl = self.exit_manager.calculate_tp_sl(df_1h, current_price, direction)

            logger.info(f"[开仓] {direction.upper()} @ ${current_price:.2f}")
            logger.info(f"  止盈: ${tp:.2f} ({(tp/current_price - 1)*100:+.2f}%)")
            logger.info(f"  止损: ${sl:.2f} ({(sl/current_price - 1)*100:+.2f}%)")

            # 开仓
            self.config.has_position = True
            self.config.position_type = direction
            self.config.entry_price = current_price
            self.config.entry_time = current_time
            self.config.entry_index = len(df_4h) - 1
            self.config.position_size = self.config.BASE_POSITION_SIZE
            self.config.entry_signal_type = signal_type
            self.config.entry_confidence = confidence
            self.config.take_profit_price = tp
            self.config.stop_loss_price = sl
            self.config.df_1h_klines = df_1h

            # 保存状态
            self.config.save_state()

            # 通知
            self.notifier.notify_entry(direction, current_price, signal_type, confidence, tp, sl)

            logger.info("开仓成功！")

        except Exception as e:
            logger.error(f"检查信号异常: {e}", exc_info=True)

    def check_position(self):
        """检查持仓状态（每1小时）"""
        try:
            if not self.config.has_position:
                return

            logger.info("-" * 70)
            logger.info("检查持仓状态...")

            # 获取1H数据
            df_1h = self.fetcher.fetch_btc_data(interval='1h', limit=300)
            if df_1h is None:
                logger.error("获取1H数据失败")
                return

            # 获取4H数据
            df_4h = self.fetcher.fetch_btc_data(interval='4h', limit=300)
            if df_4h is None:
                logger.error("获取4H数据失败")
                return

            current_price = df_1h.iloc[-1]['close']
            current_time = df_1h.index[-1]
            hold_periods = (len(df_4h) - 1) - self.config.entry_index

            logger.info(f"持仓时长: {hold_periods}周期 | 当前价格: ${current_price:.2f}")

            # 计算当前盈亏
            if self.config.position_type == 'long':
                pnl_pct = (current_price - self.config.entry_price) / self.config.entry_price
            else:
                pnl_pct = (self.config.entry_price - current_price) / self.config.entry_price

            logger.info(f"当前盈亏: {pnl_pct*100:+.2f}%")

            # V7.0.7 ZigZag出场检查
            should_exit, reason, exit_price = self.exit_manager.check_exit(
                df_1h, self.config.entry_price, self.config.position_type
            )

            # 超时检查
            if not should_exit and hold_periods >= self.config.MAX_HOLD_PERIODS:
                should_exit = True
                reason = f"超时({hold_periods}周期)"
                exit_price = current_price

            if should_exit:
                # 平仓
                if exit_price is None:
                    exit_price = current_price

                # 重新计算盈亏
                if self.config.position_type == 'long':
                    pnl_pct = (exit_price - self.config.entry_price) / self.config.entry_price
                else:
                    pnl_pct = (self.config.entry_price - exit_price) / self.config.entry_price

                logger.info(f"[平仓] {self.config.position_type.upper()} @ ${exit_price:.2f}")
                logger.info(f"  盈亏: {pnl_pct*100:+.2f}%")
                logger.info(f"  原因: {reason}")

                # 更新统计
                self.config.total_trades += 1
                if pnl_pct > 0:
                    self.config.winning_trades += 1
                else:
                    self.config.losing_trades += 1
                self.config.total_pnl += pnl_pct * 100

                # 通知
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
            logger.error(f"检查持仓异常: {e}", exc_info=True)

    def run(self):
        """主循环"""
        logger.info("=" * 70)
        logger.info("V7.0.7 智能交易系统启动")
        logger.info("=" * 70)
        logger.info(f"Telegram Token: {self.config.telegram_token[:20]}...")
        logger.info(f"Telegram Chat ID: {self.config.telegram_chat_id}")
        logger.info(f"Telegram Enabled: {self.config.telegram_enabled}")
        logger.info("")

        # 启动时通知
        self.notifier.notify_status()

        # 设置定时任务
        schedule.every(4).hours.do(self.check_signals)
        schedule.every(1).hours.do(self.check_position)

        logger.info("定时任务已设置：")
        logger.info("  - 每4小时检查信号")
        logger.info("  - 每1小时检查持仓")
        logger.info("")

        # 立即执行一次信号检查
        logger.info("执行初始信号检查...")
        self.check_signals()

        # 主循环
        logger.info("进入主循环...")
        logger.info("=" * 70)

        while True:
            try:
                schedule.run_pending()
                time.sleep(60)
            except KeyboardInterrupt:
                logger.info("收到停止信号，正在退出...")
                break
            except Exception as e:
                logger.error(f"主循环异常: {e}", exc_info=True)
                time.sleep(60)


# ==================== [主入口] ====================
if __name__ == "__main__":
    engine = V707TradingEngine()
    engine.run()
