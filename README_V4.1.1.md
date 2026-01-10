# V4.1.1 云端部署文件包

## 📦 文件清单

### 核心程序
- `BTC4小时策略预警v4.1.1_双信号版.py` - **主程序**（必需）

### 文档文件
- `README_V4.1.1.md` - **本文件**（部署导航）
- `V4.1.1云端部署指南.md` - **完整部署文档**（详细步骤）
- `V4.1.1更新说明.md` - 版本更新日志
- `V4.1.1部署清单.md` - 部署检查清单

### 配置文件
- `requirements_v411.txt` - Python依赖列表
- `start_v411.bat` - Windows快速启动脚本

### 数据文件（需要准备）
⚠️ **以下文件需要单独准备**：
- `dxy_data.csv` - DXY数据（从本地复制）

### 运行时生成（自动创建）
- `position_tracker_aligned_status.json` - 持仓状态
- `battle_aligned_status.json` - 战备状态
- `basic_physics_signals.json` - 基础信号记录
- `trade_history.json` - 交易历史
- `physics_alert_v3_1_complete.log` - 运行日志

## 🚀 快速开始

### 1. 本地测试
```bash
# Windows
start_v411.bat

# Linux/Mac
python3 BTC4小时策略预警v4.1.1_双信号版.py
```

### 2. 云端部署
**请参考**: `V4.1.1云端部署指南.md`

**快速步骤**：
1. 上传所有文件到服务器
2. 安装依赖：`pip3 install -r requirements_v411.txt`
3. 准备`dxy_data.csv`文件
4. 配置代理（如需要）
5. 后台运行：`nohup python3 BTC4小时策略预警v4.1.1_双信号版.py > output.log 2>&1 &`

### 3. 验证运行
```bash
# 查看进程
ps aux | grep BTC4小时策略预警

# 查看日志
tail -f physics_alert_v3_1_complete.log

# 检查基础信号
tail -10 basic_physics_signals.json
```

## 📊 V4.1.1 核心特性

### ✅ 双信号系统
1. **基础物理信号**（验证4原始）
   - 每4H计算并记录
   - 用于复盘分析
   - 不参与交易

2. **V4.1 Smart Ape信号**
   - 完整交易系统
   - 多重过滤机制
   - EMA21入场
   - Smart Ape风控

### ✅ 完整功能保留
- EMA21入场机制 ✅
- 黄金阈值过滤 ✅
- 逻辑失效止损 ✅
- 爆仓潮止盈 ✅
- 人机结合加仓 ✅
- Telegram交互 ✅
- 三维风控 ✅

## 📖 文档导航

### 新手入门
1. 📖 阅读：`V4.1.1更新说明.md`（了解新功能）
2. 📋 检查：`V4.1.1部署清单.md`（环境检查）
3. 🚀 部署：`V4.1.1云端部署指南.md`（详细步骤）

### 运维管理
- 查看日志：`tail -f physics_alert_v3_1_complete.log`
- 查看基础信号：`cat basic_physics_signals.json | tail -10`
- 重启服务：`sudo systemctl restart btc-physics-v411.service`

### 复盘分析
- 导出`basic_physics_signals.json`
- 用pandas分析基础信号表现
- 对比基础信号 vs V4.1信号

## ⚙️ 系统要求

- **Python**: 3.8+
- **内存**: 最低2GB
- **网络**: 需要访问Binance和Coinalyze API
- **代理**: 可能需要（访问Coinalyze）

## 🔧 配置说明

### 必需配置
- `telegram_token` (第180行)
- `telegram_chat_id` (第181行)

### 可选配置
- 代理设置（第173-177行）
- 微信Server酱（第184行）
- 仓位比例（第137行）

## 📞 技术支持

### 常见问题
详见：`V4.1.1云端部署指南.md` 的"常见问题"章节

### 检查清单
详见：`V4.1.1部署清单.md`

### 日志分析
```bash
# 查看基础信号记录
grep "基础信号" physics_alert_v3_1_complete.log

# 查看错误信息
grep "ERROR" physics_alert_v3_1_complete.log

# 查看Smart Ape风控
grep "Smart Ape" physics_alert_v3_1_complete.log
```

## 🎯 版本信息

- **当前版本**: V4.1.1 双信号版
- **发布日期**: 2026-01-09
- **基于**: V4.1 Smart Ape Edition
- **回测收益**: +803% (2年，V4.1 Smart Ape)

## 📝 更新记录

### V4.1.1 (2026-01-09)
- ✅ 新增基础物理信号4H记录
- ✅ 新增复盘数据支持
- ✅ 保留V4.1所有功能100%

### V4.1 (2026-01-08)
- ✅ Smart Ape黄金阈值过滤
- ✅ 逻辑失效止损
- ✅ 爆仓潮止盈

---

**准备好了吗？开始部署V4.1.1！🚀**

**第一步**: 阅读 `V4.1.1云端部署指南.md`
