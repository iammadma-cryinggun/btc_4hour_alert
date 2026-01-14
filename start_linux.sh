#!/bin/bash
# V7.0交易系统 - Linux启动脚本

echo "==============================================================================="
echo "V7.0 非线性动力学交易系统"
echo "==============================================================================="
echo ""
echo "正在启动系统..."
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] Python3未安装"
    echo "请先安装Python 3.7+"
    exit 1
fi

# 检查依赖是否安装
python3 -c "import numpy, pandas, scipy, requests, schedule" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[提示] 正在安装依赖包..."
    pip3 install -r requirements.txt
fi

# 启动系统
echo "[启动] V7.0交易系统"
python3 v70_trader_runner.py
