# -*- coding: utf-8 -*-
"""
V7.0交易系统 - 快速验证脚本
用于验证系统是否正常工作
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

print("="*70)
print(" V7.0交易系统 - 快速验证")
print("="*70)

# 1. 检查Python版本
print("\n[1/5] 检查Python版本...")
python_version = sys.version_info
if python_version.major >= 3 and python_version.minor >= 7:
    print(f"[OK] Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
else:
    print(f"[ERROR] Python版本过低: {python_version.major}.{python_version.minor}.{python_version.micro}")
    print("   需要Python 3.7+")
    sys.exit(1)

# 2. 检查依赖包
print("\n[2/5] 检查依赖包...")
required_packages = {
    'numpy': 'numpy',
    'pandas': 'pandas',
    'scipy': 'scipy',
    'requests': 'requests',
    'schedule': 'schedule'
}

missing_packages = []
for module_name, package_name in required_packages.items():
    try:
        __import__(module_name)
        print(f"[OK] {package_name}")
    except ImportError:
        print(f"[MISSING] {package_name} (未安装)")
        missing_packages.append(package_name)

if missing_packages:
    print(f"\n请安装缺失的包:")
    print(f"pip install {' '.join(missing_packages)}")
    sys.exit(1)

# 3. 检查配置文件
print("\n[3/5] 检查配置文件...")
env_file = '.env'
if os.path.exists(env_file):
    print(f"[OK] 配置文件存在: {env_file}")
else:
    print(f"[WARNING] 配置文件不存在: {env_file}")
    print(f"   请复制 .env.example 为 .env 并修改配置")

# 4. 导入系统模块
print("\n[4/5] 导入系统模块...")
try:
    from v70_trader_main import (
        V70TraderConfig, DataFetcher, PhysicsSignalCalculator,
        V70TradingEngine, TelegramNotifier
    )
    print("[OK] v70_trader_main.py")
except Exception as e:
    print(f"[ERROR] 导入失败: {e}")
    sys.exit(1)

try:
    from v70_trader_runner import V70TraderSystem
    print("[OK] v70_trader_runner.py")
except Exception as e:
    print(f"[ERROR] 导入失败: {e}")
    sys.exit(1)

# 5. 测试系统初始化
print("\n[5/5] 测试系统初始化...")
try:
    # 创建配置
    config = V70TraderConfig()
    print("[OK] 配置初始化成功")

    # 创建数据获取器
    fetcher = DataFetcher(config)
    print("[OK] 数据获取器初始化成功")

    # 创建信号计算器
    calculator = PhysicsSignalCalculator(config)
    print("[OK] 信号计算器初始化成功")

    # 创建交易引擎
    engine = V70TradingEngine(config)
    print("[OK] 交易引擎初始化成功")

    # 创建Telegram通知
    telegram = TelegramNotifier(config)
    print("[OK] Telegram通知初始化成功")

    # 创建主系统
    system = V70TraderSystem()
    print("[OK] 主系统初始化成功")

except Exception as e:
    print(f"[ERROR] 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 6. 测试数据获取（可选）
print("\n[测试] 测试数据获取...")
try:
    df = fetcher.fetch_btc_data(interval='4h', limit=10)
    if df is not None and len(df) > 0:
        print(f"[OK] 数据获取成功 (获取{len(df)}条记录)")
        print(f"   最新价格: ${df.iloc[-1]['close']:.2f}")
    else:
        print("[WARNING] 数据获取失败（可能是网络问题）")
except Exception as e:
    print(f"[WARNING] 数据获取异常: {e}")

# 完成
print("\n" + "="*70)
print("[SUCCESS] 验证完成！系统已就绪")
print("="*70)

print("\n下一步:")
print("1. 配置 .env 文件（Telegram Token和Chat ID）")
print("2. 运行测试: python v70_trader_runner.py test")
print("3. 正式启动: python v70_trader_runner.py")
print("   或使用启动脚本: start_windows.bat (Windows)")
print("                  ./start_linux.sh (Linux)")
print("\n详细文档请查看: DEPLOYMENT_GUIDE.md")
print("="*70)
