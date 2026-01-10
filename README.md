# BTC 4小时物理奇点预警系统 V4.1.1

## 🎯 项目简介

基于物理模型的BTC自动交易信号系统，采用双信号架构：

### 📊 双信号系统
1. **基础物理信号**（验证4原始）
   - 每4小时计算并记录
   - 用于复盘分析
   - 不参与实际交易

2. **V4.1 Smart Ape信号**
   - 完整交易系统
   - EMA21入场 + 多重过滤
   - Smart Ape动态风控

## ✨ 核心特性

### 基础物理信号
- ✅ FFT低通滤波 + Hilbert变换
- ✅ 张力加速度计算
- ✅ DXY燃料增强
- ✅ 每4H自动记录
- ✅ JSON格式保存

### V4.1 Smart Ape
- ✅ EMA21入场机制
- ✅ 黄金阈值过滤（空单LS<2.0）
- ✅ 逻辑失效止损（LS变化±0.5）
- ✅ 爆仓潮止盈（清算量>95分位）
- ✅ 人机结合加仓
- ✅ 三维动态风控
- ✅ Telegram交互

## 📈 回测表现

**V4.1 Smart Ape（2年数据）**：
- 总收益：+803%
- 胜率：49.5%
- 最大回撤：31.73%
- 风险调整收益：61.6

## 🚀 快速开始

### 方式1: Zeabur一键部署（推荐）

1. **GitHub部署**
   ```bash
   # 克隆仓库
   git clone https://github.com/iammadma-cryinggun/btc_4hour_alert.git
   cd btc_4hour_alert

   # 本地测试
   pip3 install -r requirements_v411.txt
   python3 BTC4小时策略预警v4.1.1_纯净版.py
   ```

2. **Zeabur部署**
   - 访问：https://zeabur.com
   - 导入GitHub仓库
   - 自动读取`.zeabur.yml`配置
   - 一键部署

详细步骤：见 [Zeabur部署指南.md](Zeabur部署指南.md)

### 方式2: 本地运行

#### Windows
```bash
# 双击运行
start_v411.bat
```

#### Linux/Mac
```bash
# 安装依赖
pip3 install -r requirements_v411.txt

# 运行程序
python3 BTC4小时策略预警v4.1.1_纯净版.py
```

### 方式3: 服务器部署

```bash
# 使用一键部署脚本
chmod +x deploy.sh
./deploy.sh
```

详细步骤：见 [V4.1.1云端部署指南.md](V4.1.1云端部署指南.md)

## 📖 文档导航

### 新手入门
1. [README_V4.1.1.md](README_V4.1.1.md) - 部署导航
2. [文件清单.md](文件清单.md) - 文件说明
3. [V4.1.1更新说明.md](V4.1.1更新说明.md) - 版本特性

### 部署指南
4. [GitHub快速部署指南.md](GitHub快速部署指南.md) - GitHub+Zeabur
5. [Zeabur部署指南.md](Zeabur部署指南.md) - Zeabur详细配置
6. [V4.1.1云端部署指南.md](V4.1.1云端部署指南.md) - 通用部署
7. [V4.1.1部署清单.md](V4.1.1部署清单.md) - 部署检查

## 🛠️ 技术栈

- **语言**: Python 3.8+
- **核心库**:
  - numpy (数值计算)
  - pandas (数据处理)
  - scipy (FFT、Hilbert变换)
  - requests (API调用)
  - schedule (定时任务)

- **数据源**:
  - Binance API (BTC价格)
  - Coinalyze API (LS-Ratio, OI, FR, 清算)
  - DXY数据 (本地CSV)

- **部署**:
  - Docker (容器化)
  - Zeabur (云平台)

## 📊 数据文件

### 输入文件
- `dxy_data.csv` - DXY指数数据

### 输出文件（自动生成）
- `basic_physics_signals.json` - 基础信号记录
- `trade_history.json` - 交易历史
- `position_tracker_aligned_status.json` - 持仓状态
- `battle_aligned_status.json` - 战备状态
- `physics_alert_v3_1_complete.log` - 运行日志

## ⚙️ 配置说明

### 必需配置
- `TELEGRAM_TOKEN` - Telegram Bot Token
- `TELEGRAM_CHAT_ID` - Telegram Chat ID

### 可选配置
- `PROXY_ENABLED` - 是否启用代理
- `PROXY_HOST` - 代理主机
- `PROXY_PORT` - 代理端口

## 💬 Telegram交互

启动后可以发送：
- `/status` - 查看当前持仓
- `/help` - 查看所有命令
- `/close` - 平仓当前持仓
- `我已平仓` - 手动标记平仓

## 📈 系统监控

### 实时日志
```bash
tail -f physics_alert_v3_1_complete.log
```

### 基础信号
```bash
tail -10 basic_physics_signals.json
```

### 系统状态
```bash
ps aux | grep BTC4小时策略预警
```

## 🔒 安全建议

1. **保护敏感信息**
   - 不要在公开仓库提交API密钥
   - 使用环境变量存储Token
   - 定期更换API密钥

2. **网络安全**
   - 配置防火墙
   - 使用HTTPS代理
   - 限制API访问频率

3. **数据备份**
   - 定期备份JSON文件
   - 导出交易历史
   - 保存运行日志

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

本项目仅供学习和研究使用。

## ⚠️ 免责声明

本系统仅供学习研究使用，不构成投资建议。加密货币交易有风险，投资需谨慎。

---

**版本**: V4.1.1 双信号版
**发布**: 2026-01-09
**仓库**: https://github.com/iammadma-cryinggun/btc_4hour_alert

**Happy Trading! 🚀**
