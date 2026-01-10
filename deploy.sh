#!/bin/bash
# V4.1.1 一键部署脚本（Linux云端服务器）

set -e  # 遇到错误立即退出

echo "============================================"
echo "V4.1.1 云端部署脚本"
echo "============================================"
echo ""

# 检查Python版本
echo "[1/6] 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3未安装，请先安装Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✅ Python版本: $PYTHON_VERSION"

# 安装依赖
echo ""
echo "[2/6] 安装Python依赖..."
if [ -f "requirements_v411.txt" ]; then
    pip3 install -r requirements_v411.txt
    echo "✅ 依赖安装完成"
else
    echo "❌ 找不到requirements_v411.txt"
    exit 1
fi

# 检查必需文件
echo ""
echo "[3/6] 检查必需文件..."
REQUIRED_FILES=("BTC4小时策略预警v4.1.1_双信号版.py" "dxy_data.csv")
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file 存在"
    else
        echo "❌ $file 不存在"
        echo "请确保已上传所有必需文件"
        exit 1
    fi
done

# 测试网络连接
echo ""
echo "[4/6] 测试API连接..."
python3 << EOF
import requests
import sys

# 测试Binance
try:
    resp = requests.get("https://api.binance.com/api/v3/ping", timeout=10)
    if resp.status_code == 200:
        print("✅ Binance API连接正常")
    else:
        print("⚠️ Binance API连接异常")
except Exception as e:
    print(f"❌ Binance API连接失败: {e}")
    sys.exit(1)

# 测试Coinalyze
try:
    resp = requests.get("https://api.coinalyze.net/v1", timeout=10)
    if resp.status_code == 200:
        print("✅ Coinalyze API连接正常")
    else:
        print("⚠️ Coinalyze API连接异常（可能需要配置代理）")
except Exception as e:
    print(f"⚠️ Coinalyze API连接失败: {e}")
    print("如果网络受限，请配置代理（见部署指南）")
EOF

# 创建systemd服务（可选）
echo ""
echo "[5/6] 创建systemd服务..."
SERVICE_FILE="/etc/systemd/system/btc-physics-v411.service"

read -p "是否创建systemd服务？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    CURRENT_DIR=$(pwd)
    CURRENT_USER=$(whoami)

    sudo tee $SERVICE_FILE > /dev/null << EOF
[Unit]
Description=BTC Physics Signal System V4.1.1
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/python3 $CURRENT_DIR/BTC4小时策略预警v4.1.1_双信号版.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    echo "✅ systemd服务已创建: $SERVICE_FILE"
    echo "   启动服务: sudo systemctl start btc-physics-v411"
    echo "   开机自启: sudo systemctl enable btc-physics-v411"
else
    echo "⏭️  跳过systemd服务创建"
fi

# 完成
echo ""
echo "[6/6] 部署准备完成！"
echo "============================================"
echo ""
echo "✅ V4.1.1部署准备完成！"
echo ""
echo "下一步操作："
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "使用systemd启动："
    echo "  sudo systemctl start btc-physics-v411.service"
    echo "  sudo systemctl status btc-physics-v411.service"
    echo ""
else
    echo "直接运行（前台）："
    echo "  python3 BTC4小时策略预警v4.1.1_双信号版.py"
    echo ""
    echo "后台运行（nohup）："
    echo "  nohup python3 BTC4小时策略预警v4.1.1_双信号版.py > output.log 2>&1 &"
    echo ""
fi

echo "查看日志："
echo "  tail -f physics_alert_v3_1_complete.log"
echo ""
echo "Telegram命令："
echo "  /status - 查看持仓"
echo "  /help - 查看帮助"
echo ""
echo "详细文档："
echo "  V4.1.1云端部署指南.md"
echo "  V4.1.1部署清单.md"
echo ""
echo "============================================"
