# V7.0.7 系统部署指南

## 部署前准备

### 1. 环境要求
- Python 3.8+
- pip包管理器
- 稳定的网络连接（访问Binance API）

### 2. 依赖安装

```bash
pip install numpy pandas scipy requests schedule python-dotenv
```

或使用requirements.txt：

```bash
pip install -r requirements.txt
```

## 本地部署

### Windows

1. 配置环境变量
```bash
copy .env.example .env
```

2. 编辑.env文件，确认Telegram token正确

3. 运行
```bash
python main_v707.py
```

### Linux/Mac

1. 配置环境变量
```bash
cp .env.example .env
```

2. 运行
```bash
python3 main_v707.py
```

### 后台运行

#### 使用screen（推荐）

```bash
# 创建screen会话
screen -S v707_trader

# 运行程序
python3 main_v707.py

# 分离会话（Ctrl+A, 然后按D）

# 重新连接
screen -r v707_trader
```

#### 使用nohup

```bash
nohup python3 main_v707.py > v707.log 2>&1 &

# 查看日志
tail -f v707.log
```

## 云端部署（Zeabur）

### 方法1：通过GitHub集成

1. **推送代码到GitHub**
   ```bash
   git add .
   git commit -m "Deploy V7.0.7 to Zeabur"
   git push origin main
   ```

2. **在Zeabur创建服务**
   - 登录 https://zeabur.com
   - 点击"New Service"
   - 选择"Git" → 连接你的GitHub仓库
   - 选择`V4.4云端部署文件/btc_4hour_alert`目录
   - 选择"Python"模板

3. **配置环境变量**
   在Zeabur服务配置页面添加：
   ```
   TELEGRAM_TOKEN=8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk
   TELEGRAM_CHAT_ID=838429342
   TELEGRAM_ENABLED=True
   ```

4. **部署**
   - 点击"Deploy"
   - 等待部署完成

5. **查看日志**
   - 在Zeabur控制台查看实时日志

### 方法2：手动部署

1. **准备代码包**
   ```bash
   cd V4.4云端部署文件/btc_4hour_alert
   zip -r v707_deployment.zip *
   ```

2. **上传到Zeabur**
   - 创建新服务 → 选择"Prebuilt Image"
   - 选择"Python"
   - 上传代码包

3. **配置环境变量**（同方法1）

4. **部署**

## 验证部署

### 1. 检查日志

启动后应该看到：
```
================================================================================
V7.0.7 智能交易系统启动
================================================================================
Telegram Token: 8505180201:AAGOSkhXRu77OlRMu0PZCbKtYMEr1tRGAk...
Telegram Chat ID: 838429342
Telegram Enabled: True

定时任务已设置：
  - 每4小时检查信号
  - 每1小时检查持仓

执行初始信号检查...
================================================================================
```

### 2. Telegram通知

启动后会收到系统状态通知：
```
📊 V7.0.7系统状态

⭕ 当前状态: 空仓
📈 总交易: 0
✅ 盈利: 0
❌ 亏损: 0
💵 总盈亏: 0.0%
```

## 常见问题

### Q1: Telegram通知收不到？

**A:** 检查以下几点：
1. Telegram token是否正确（应该是850518开头）
2. Chat ID是否正确（838429342）
3. 网络是否能访问Telegram API
4. 检查日志中的错误信息

### Q2: 程序启动后立即退出？

**A:** 检查：
1. Python版本是否≥3.8
2. 依赖包是否安装完整
3. 查看日志文件`v707_trader.log`

### Q3: 如何更新代码？

**A:**
```bash
# 拉取最新代码
git pull

# 重启程序
# 如果使用screen:
screen -r v707_trader
# Ctrl+C停止，然后重新运行
python3 main_v707.py

# 或直接重启进程
pkill -f main_v707.py
nohup python3 main_v707.py > v707.log 2>&1 &
```

### Q4: 状态文件损坏怎么办？

**A:** 删除`v707_trader_state.json`，程序会重新初始化

```bash
rm v707_trader_state.json
python3 main_v707.py
```

## 监控和维护

### 查看实时日志

```bash
tail -f v707_trader.log
```

### 查看持仓状态

程序会自动保存状态到`v707_trader_state.json`，可以查看：

```bash
cat v707_trader_state.json | python -m json.tool
```

### 定期检查

建议每天检查一次：
1. 日志文件大小
2. 持仓状态
3. 盈亏统计
4. Telegram通知是否正常

## 性能优化

### 减少API调用

当前配置：
- 信号检查：每4小时
- 持仓检查：每1小时

如有需要，可在`main_v707.py`中调整：
```python
schedule.every(4).hours.do(self.check_signals)  # 信号检查频率
schedule.every(1).hours.do(self.check_position)   # 持仓检查频率
```

### 日志轮转

为避免日志文件过大，建议配置logrotate：

```bash
# /etc/logrotate.d/v707_trader
/path/to/v707_trader.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

## 安全建议

1. ⚠️ **不要将.env文件提交到Git**
   - 确保.gitignore包含`.env`

2. ⚠️ **定期备份状态文件**
   ```bash
   cp v707_trader_state.json v707_trader_state.json.backup
   ```

3. ⚠️ **使用API时注意限额**
   - Binance API有频率限制
   - 当前配置已优化，不会超限

## 故障恢复

### 程序崩溃重启

创建监控脚本`monitor.sh`：

```bash
#!/bin/bash
while true; do
    if ! pgrep -f "python3 main_v707.py" > /dev/null; then
        echo "V7.0.7未运行，正在重启..."
        cd /path/to/V4.4云端部署文件/btc_4hour_alert
        nohup python3 main_v707.py >> v707.log 2>&1 &
    fi
    sleep 60
done
```

运行监控：
```bash
nohup bash monitor.sh > monitor.log 2>&1 &
```

## 更新日志

### V7.0.7 (2026-01-15)
- ✅ 集成V7.0.5入场过滤器
- ✅ 集成V7.0.7 ZigZag动态止盈止损
- ✅ 更新Telegram Token为V4.4专用
- ✅ 优化持仓检查逻辑
- ✅ 完善错误处理

---

**祝交易顺利！**
