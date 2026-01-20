# -*- coding: utf-8 -*-
"""V7.0.8快速测试"""
import os
import sys

# 测试导入
try:
    from v708_golden_module import V708Config, V708GoldenDetector, V708TelegramNotifier
    print("[OK] V7.0.8模块导入成功")
except Exception as e:
    print(f"[ERROR] 模块导入失败: {e}")
    sys.exit(1)

# 初始化
config = V708Config()
detector = V708GoldenDetector(config)
notifier = V708TelegramNotifier(
    token=os.getenv('TELEGRAM_TOKEN', '8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk'),
    chat_id=os.getenv('TELEGRAM_CHAT_ID', '838429342'),
    enabled=True
)

print("[OK] V7.0.8初始化成功")

# 测试1：SHORT首次信号
print("\n测试1: SHORT首次信号")
tension = 0.65
accel = -0.008
volume = 0.8
price = 105000.0
timestamp = "2025-01-20 04:00:00"
ratio = abs(tension / accel)

is_signal, action, msg = detector.check_first_signal(
    tension, accel, volume, timestamp, price, 'BEARISH_SINGULARITY'
)

print(f"  信号检测结果: {is_signal}")
print(f"  动作: {action}")
print(f"  消息: {msg}")

if is_signal:
    notifier.notify_first_signal(
        'BEARISH_SINGULARITY', tension, accel, volume, price, timestamp, 'short', ratio
    )
    print("  [OK] 原始信号通知已发送")

# 测试2：检查黄金开仓
print("\n测试2: 检查黄金开仓")
entries = detector.check_golden_entry(
    current_tension=0.72,
    current_accel=-0.007,
    current_volume=0.85,
    current_price=104500.0,
    current_time="2025-01-20 08:00:00"
)

print(f"  检测到 {len(entries)} 个黄金开仓机会")

for entry in entries:
    print(f"  方向: {entry['direction']}")
    print(f"  张力变化: {entry['tension_change']:.2f}%")
    print(f"  价格优势: {entry['price_advantage']:.2f}%")
    print(f"  黄金机会: {entry['is_golden']}")

    notifier.notify_golden_entry(entry, config.FALLBACK_TP, config.FALLBACK_SL)
    print("  [OK] 黄金开仓通知已发送")

# 测试3：检查黄金平仓
print("\n测试3: 检查黄金平仓")
position = {
    'direction': 'short',
    'entry_price': 104500.0,
    'entry_tension': 0.72,
    'entry_time': '2025-01-20 08:00:00'
}

exit_result = detector.check_golden_exit(
    position=position,
    current_tension=0.62,
    current_accel=-0.005,
    current_volume=1.3,
    current_price=103000.0,
    hold_periods=5
)

should_exit, reason, exit_type = exit_result
current_price_test = 103000.0
pnl = (position['entry_price'] - current_price_test) / position['entry_price'] * 100

print(f"  平仓检测: {should_exit}")
print(f"  原因: {reason}")
print(f"  类型: {exit_type}")
print(f"  盈亏: {pnl:.2f}%")

if should_exit:
    position['exit_time'] = '2025-01-22 04:00:00'
    notifier.notify_golden_exit(position, reason, current_price, pnl, exit_type)
    print("  [OK] 黄金平仓通知已发送")

print("\n[OK] V7.0.8测试完成！")
print("\n文件列表:")
print("  - v708_golden_module.py: V7.0.8核心模块")
print("  - V708_UPGRADE_GUIDE.md: 升级指南")
print("  - example_v708_integration.py: 集成示例")
print("  - deploy_v708.sh: 部署脚本")
