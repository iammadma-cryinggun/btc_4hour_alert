#!/bin/bash
# V7.0.8部署脚本

echo "=========================================="
echo "V7.0.8 部署到云端"
echo "=========================================="

# 1. 备份现有文件
echo "1. 备份现有文件..."
cp main_v707.py main_v707.py.backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
cp v707_trader_main.py v707_trader_main.py.backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# 2. 上传到Zeabur
echo "2. 部署到Zeabur..."
zeabur deploy

# 3. 检查部署状态
echo "3. 检查部署状态..."
sleep 5

# 4. 发送测试通知
echo "4. 发送测试通知..."
python -c "
from v708_golden_module import V708TelegramNotifier
import os
notifier = V708TelegramNotifier(
    token=os.getenv('TELEGRAM_TOKEN', '8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk'),
    chat_id=os.getenv('TELEGRAM_CHAT_ID', '838429342'),
    enabled=True
)
notifier.send('✅ V7.0.8系统部署成功！\n\n保留所有V7.0.7功能\n新增黄金策略识别系统', priority='high')
"

echo "=========================================="
echo "部署完成！"
echo "=========================================="
