# -*- coding: utf-8 -*-
"""
V7.0.8 快速集成示例
展示如何在现有系统中集成V7.0.8黄金策略
"""

from v708_golden_module import V708Config, V708GoldenDetector, V708TelegramNotifier
import os

# ============ 初始化V7.0.8 ============
print("初始化V7.0.8...")

v708_config = V708Config()
v708_detector = V708GoldenDetector(v708_config)
v708_notifier = V708TelegramNotifier(
    token=os.getenv('TELEGRAM_TOKEN', '8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk'),
    chat_id=os.getenv('TELEGRAM_CHAT_ID', '838429342'),
    enabled=True
)

print("V7.0.8初始化成功！")


# ============ 示例1：处理首次信号 ============
def example_first_signal():
    """示例：处理首次信号"""
    print("\n" + "="*50)
    print("示例1：处理首次信号")
    print("="*50)

    # 模拟一个SHORT首次信号
    signal_type = 'BEARISH_SINGULARITY'
    tension = 0.65  # 张力>0.5
    acceleration = -0.008  # 加速度<0
    volume_ratio = 0.8  # 量能<1.0
    price = 105000.0
    timestamp = "2025-01-20 04:00:00"

    # 检查是否为首次信号
    is_signal, action, message = v708_detector.check_first_signal(
        tension=tension,
        acceleration=acceleration,
        volume_ratio=volume_ratio,
        timestamp=timestamp,
        price=price,
        signal_type=signal_type
    )

    if is_signal:
        print(f"✓ 检测到信号: {action}")
        print(f"  消息: {message}")

        # 计算张力/加速度比
        ratio = abs(tension / acceleration)

        # 发送原始信号通知
        v708_notifier.notify_first_signal(
            signal_type=signal_type,
            tension=tension,
            acceleration=acceleration,
            volume_ratio=volume_ratio,
            price=price,
            timestamp=timestamp,
            direction='short',
            ratio=ratio
        )
        print("✓ 原始信号通知已发送")
    else:
        print(f"✗ 非目标信号: {message}")


# ============ 示例2：检查黄金开仓 ============
def example_golden_entry():
    """示例：检查黄金开仓条件"""
    print("\n" + "="*50)
    print("示例2：检查黄金开仓")
    print("="*50)

    # 模拟后续周期的数据
    current_tension = 0.72  # 张力上升
    current_accel = -0.007
    current_volume = 0.85
    current_price = 104500.0
    current_time = "2025-01-20 08:00:00"

    # 检查是否有黄金开仓机会
    entries = v708_detector.check_golden_entry(
        current_tension=current_tension,
        current_accel=current_accel,
        current_volume=current_volume,
        current_price=current_price,
        current_time=current_time
    )

    if len(entries) > 0:
        for entry in entries:
            print(f"✓ 检测到黄金开仓机会！")
            print(f"  方向: {entry['direction']}")
            print(f"  张力变化: {entry['tension_change']:+.2f}%")
            print(f"  价格优势: {entry['price_advantage']:+.2f}%")
            print(f"  是否黄金机会: {entry['is_golden']}")

            # 发送黄金开仓通知
            v708_notifier.notify_golden_entry(
                entry_info=entry,
                fallback_tp=v708_config.FALLBACK_TP,
                fallback_sl=v708_config.FALLBACK_SL
            )
            print("✓ 黄金开仓通知已发送")
    else:
        print("✗ 未达到黄金开仓条件")


# ============ 示例3：检查黄金平仓 ============
def example_golden_exit():
    """示例：检查黄金平仓条件"""
    print("\n" + "="*50)
    print("示例3：检查黄金平仓")
    print("="*50)

    # 模拟持仓数据
    position = {
        'direction': 'short',
        'entry_price': 104500.0,
        'entry_tension': 0.72,
        'entry_time': '2025-01-20 08:00:00'
    }

    # 模拟当前数据
    current_tension = 0.62  # 张力下降14%
    current_accel = -0.005
    current_volume = 1.3  # 量能放大
    current_price = 103000.0
    hold_periods = 5

    # 检查是否应该平仓
    should_exit, exit_reason, exit_type = v708_detector.check_golden_exit(
        position=position,
        current_tension=current_tension,
        current_accel=current_accel,
        current_volume=current_volume,
        current_price=current_price,
        hold_periods=hold_periods
    )

    # 计算盈亏
    pnl = (position['entry_price'] - current_price) / position['entry_price'] * 100

    if should_exit:
        print(f"✓ 触发平仓条件！")
        print(f"  原因: {exit_reason}")
        print(f"  类型: {exit_type}")
        print(f"  盈亏: {pnl:+.2f}%")

        # 发送黄金平仓通知
        position['exit_time'] = '2025-01-22 04:00:00'
        v708_notifier.notify_golden_exit(
            position=position,
            exit_reason=exit_reason,
            exit_price=current_price,
            pnl=pnl,
            exit_type=exit_type
        )
        print("✓ 黄金平仓通知已发送")
    else:
        print(f"✗ 继续持有: {exit_reason}")


# ============ 主程序 ============
if __name__ == "__main__":
    print("\n" + "="*70)
    print("V7.0.8 快速集成示例")
    print("="*70)

    # 运行示例
    example_first_signal()

    # 模拟等待周期后检查黄金开仓
    print("\n等待1个周期后...")
    example_golden_entry()

    # 模拟持仓5个周期后检查黄金平仓
    print("\n持仓5个周期后...")
    example_golden_exit()

    print("\n" + "="*70)
    print("示例运行完成！")
    print("="*70)
    print("\n提示：在实际系统中，你需要：")
    print("1. 在信号检测循环中调用 check_first_signal()")
    print("2. 在每个周期调用 check_golden_entry()")
    print("3. 在每个周期调用 check_golden_exit()")
    print("4. 所有通知会自动发送到Telegram")
    print("\n详细说明请查看: V708_UPGRADE_GUIDE.md")
