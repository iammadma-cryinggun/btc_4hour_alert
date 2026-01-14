# -*- coding: utf-8 -*-
"""
V7.0交易系统 - 主程序（第二部分）
包含主循环、定时任务和启动逻辑
"""

from v70_trader_main import (
    V70TraderConfig, DataFetcher, PhysicsSignalCalculator,
    V70TradingEngine, TelegramNotifier, logger
)
import time
from datetime import datetime


class V70TraderSystem:
    """V7.0交易系统主控制器"""

    def __init__(self):
        # 初始化各个模块
        self.config = V70TraderConfig()
        self.fetcher = DataFetcher(self.config)
        self.calculator = PhysicsSignalCalculator(self.config)
        self.engine = V70TradingEngine(self.config)
        self.telegram = TelegramNotifier(self.config)

        # 系统状态
        self.is_running = False
        self.last_check_time = None

        # 加载历史状态
        self.config.load_state()

    def check_signal(self):
        """检查信号（每4小时调用）"""
        try:
            logger.info("="*70)
            logger.info("开始检查信号...")
            logger.info("="*70)

            # 1. 获取最新数据
            df = self.fetcher.fetch_btc_data(interval='4h', limit=100)
            if df is None or len(df) < 50:
                logger.error("数据不足，跳过本次检查")
                return

            # 2. 计算物理指标
            result = self.calculator.calculate_physics_metrics(df)
            if result is None:
                logger.error("物理指标计算失败")
                return

            # 获取最新一行
            latest = result.iloc[-1]
            current_price = latest['close']
            high_price = latest['high']
            low_price = latest['low']
            current_tension = latest['tension']
            current_acceleration = latest['acceleration']

            logger.info(f"[价格] ${current_price:.2f}")
            logger.info(f"[张力] {current_tension:.3f}")
            logger.info(f"[加速度] {current_acceleration:.3f}")

            # 3. 获取DXY数据（验证5完整逻辑）
            dxy_df = self.fetcher.fetch_dxy_data(limit=10)
            dxy_fuel = self.calculator.calculate_dxy_fuel(dxy_df, datetime.now())

            if dxy_fuel > 0:
                logger.info(f"[DXY燃料] {dxy_fuel:.3f} (DXY失速中)")
            else:
                logger.info(f"[DXY燃料] {dxy_fuel:.3f} (DXY加速中)")

            # ⚠️ 重要：DXY燃料默认禁用，以匹配V7.0回测
            if not self.config.USE_DXY_FUEL:
                logger.info(f"[DXY模式] 禁用（匹配V7.0回测，置信度0.6~0.8）")
            else:
                logger.info(f"[DXY模式] 启用（完整验证5逻辑，置信度可达0.9~0.95）⚠️")

            # 4. 诊断市场状态
            signal_type, confidence, description = self.calculator.diagnose_regime(
                current_tension, current_acceleration, dxy_fuel
            )

            # 5. 更新最新信号
            self.config.last_signal_time = datetime.now()
            self.config.last_signal_type = signal_type
            self.config.last_signal_desc = description
            self.config.last_signal_price = current_price
            self.config.last_signal_confidence = confidence
            self.config.last_signal_tension = current_tension
            self.config.last_signal_acceleration = current_acceleration

            # 6. 如果有持仓，先检查出场条件
            if self.config.has_position:
                signal_index = len(result) - 1
                should_exit, reason, exit_type = self.engine.check_exit_conditions(
                    current_price, high_price, low_price,
                    current_tension, current_acceleration, confidence,
                    datetime.now(), signal_index
                )

                if should_exit:
                    self.engine.close_position(current_price, datetime.now(), reason, exit_type)
                    self.telegram.notify_exit(
                        self.config.position_type, self.config.entry_price,
                        current_price, (current_price - self.config.entry_price) / self.config.entry_price,
                        reason, exit_type
                    )
                    self.config.save_state()
                    return

                # 更新ATR历史
                atr = self.engine.calculate_atr(high_price, low_price, current_price)
                self.config.atr_history.append(atr)

                logger.info(f"[持仓] {self.config.position_type.upper()} | "
                           f"@${self.config.entry_price:.2f} | "
                           f"当前${current_price:.2f} | "
                           f"止损${self.config.stop_loss_price:.2f}")

            # 7. 如果无持仓，检查入场条件
            if not self.config.has_position:
                should_enter, entry_reason = self.engine.check_entry_signal(
                    signal_type, confidence, current_price
                )

                if should_enter:
                    # 确定入场方向
                    direction, dir_desc = self.engine.get_entry_direction(signal_type)

                    if direction:
                        # 计算ATR
                        atr = self.engine.calculate_atr(high_price, low_price, current_price)
                        signal_index = len(result) - 1

                        # 开仓
                        success = self.engine.open_position(
                            direction, current_price, datetime.now(), signal_index,
                            signal_type, current_tension, current_acceleration,
                            confidence, atr
                        )

                        if success:
                            self.telegram.notify_entry(
                                direction, current_price, signal_type,
                                confidence, self.config.stop_loss_price
                            )
                            self.config.save_state()

            # 7. 通知新信号（如果有）
            if signal_type and confidence >= self.config.CONF_THRESHOLD:
                self.telegram.notify_signal(
                    signal_type, confidence, description,
                    current_price, current_tension, current_acceleration
                )

            self.last_check_time = datetime.now()
            logger.info("[完成] 信号检查完成")
            logger.info("="*70)

        except Exception as e:
            logger.error(f"检查信号异常: {e}", exc_info=True)

    def check_position_status(self):
        """检查仓位状态（每1小时调用）"""
        try:
            if not self.config.has_position:
                return

            logger.info("[仓位检查] 持仓状态监控中...")

            # 获取最新价格（使用1h数据）
            df = self.fetcher.fetch_btc_data(interval='1h', limit=5)
            if df is None:
                return

            latest = df.iloc[-1]
            current_price = latest['close']
            high_price = latest['high']
            low_price = latest['low']

            # 只检查止损，不检查其他出场条件（因为信号检查会处理）
            if self.config.stop_loss_type == 'ATR':
                current_atr = self.engine.get_current_atr()
                atr_stop_distance = current_atr * self.config.ATR_MULTIPLIER

                if self.config.position_type == 'long':
                    max_adverse = self.config.entry_price - low_price
                    if max_adverse > atr_stop_distance:
                        loss_pct = (low_price - self.config.entry_price) / self.config.entry_price
                        reason = f"ATR止损({loss_pct:.2%})"
                        self.engine.close_position(current_price, datetime.now(), reason, 'stop_loss')
                        self.telegram.notify_exit(
                            self.config.position_type, self.config.entry_price,
                            current_price, loss_pct, reason, 'stop_loss'
                        )
                        self.config.save_state()
                        return
                else:  # short
                    max_adverse = high_price - self.config.entry_price
                    if max_adverse > atr_stop_distance:
                        loss_pct = (self.config.entry_price - high_price) / self.config.entry_price
                        reason = f"ATR止损({loss_pct:.2%})"
                        self.engine.close_position(current_price, datetime.now(), reason, 'stop_loss')
                        self.telegram.notify_exit(
                            self.config.position_type, self.config.entry_price,
                            current_price, loss_pct, reason, 'stop_loss'
                        )
                        self.config.save_state()
                        return

        except Exception as e:
            logger.error(f"检查仓位状态异常: {e}", exc_info=True)

    def send_status_report(self):
        """发送状态报告"""
        try:
            self.telegram.notify_status()
        except Exception as e:
            logger.error(f"发送状态报告异常: {e}")

    def start(self):
        """启动系统"""
        logger.info("🚀 V7.0交易系统启动")
        logger.info("="*70)

        # 加载配置
        self.config.load_state()

        # 初始信号检查
        logger.info("执行初始信号检查...")
        self.check_signal()

        # 设置定时任务
        import schedule
        schedule.every(4).hours.do(self.check_signal)
        schedule.every(1).hours.do(self.check_position_status)
        schedule.every(6).hours.do(self.send_status_report)

        self.is_running = True

        # 启动通知
        self.telegram.send_message("🚀 *V7.0交易系统已启动*\n\n系统开始监控市场...")

        logger.info("✅ 定时任务已设置")
        logger.info("- 信号检查: 每4小时")
        logger.info("- 仓位检查: 每1小时")
        logger.info("- 状态报告: 每6小时")
        logger.info("="*70)

        # 主循环
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except KeyboardInterrupt:
                logger.info("收到停止信号，正在退出...")
                self.stop()
                break
            except Exception as e:
                logger.error(f"主循环异常: {e}", exc_info=True)
                time.sleep(60)

    def stop(self):
        """停止系统"""
        logger.info("正在停止V7.0交易系统...")
        self.is_running = False
        self.config.save_state()
        self.telegram.send_message("🛑 *V7.0交易系统已停止*\n\n系统状态已保存")
        logger.info("✅ 系统已停止")


# ==================== [启动脚本] ====================
def main():
    """Main entry point for cloud deployment and direct execution"""
    import sys

    print("""
================================================================================
V7.0 非线性动力学交易系统 - 实盘版本
================================================================================

策略: Combat Robust V7.0
回测: 85.01%收益, -31.8%最大回撤, 90.2%止盈率

核心特性:
- T0-T2惯性保护（前8小时只触发ATR硬止损）
- 1.5×ATR动态止损
- 严格动能衰减判断
- 时间窗口到期（5周期自动平仓）
- Telegram实时通知

================================================================================
    """)

    # 创建系统实例
    system = V70TraderSystem()

    # 处理命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == 'status':
            # 显示状态
            system.send_status_report()
        elif command == 'test':
            # 测试运行（执行一次信号检查）
            logger.info("🧪 测试模式：执行单次信号检查")
            system.check_signal()
        elif command == 'close':
            # 强制平仓
            if system.config.has_position:
                # 获取当前价格
                df = system.fetcher.fetch_btc_data(interval='1h', limit=1)
                if df is not None:
                    current_price = df.iloc[-1]['close']
                    system.engine.close_position(
                        current_price, datetime.now(),
                        "手动平仓", 'manual'
                    )
                    system.telegram.send_message("🔴 *手动平仓*\n\n已手动平仓")
                    system.config.save_state()
                else:
                    logger.error("无法获取当前价格")
            else:
                logger.info("当前无持仓")
        else:
            print(f"未知命令: {command}")
            print("可用命令: status, test, close")
    else:
        # 正常启动
        try:
            system.start()
        except Exception as e:
            logger.error(f"系统异常: {e}", exc_info=True)
            system.stop()


if __name__ == "__main__":
    main()
