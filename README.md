# V7.0.7 智能交易系统 - 云端部署版

> **V4.4 最新版本** | 集成V7.0.5过滤器 + V7.0.7 ZigZag动态止盈止损

## 快速开始

### 1. 配置环境

```bash
cp .env.example .env
# 编辑.env文件，确认Telegram token正确
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行系统

```bash
python main_v707.py
```

## 核心特性

✅ **V7.0.5入场过滤器**
- 量能过滤：避免高位放量
- 趋势过滤：避开主升/跌浪
- 动能过滤：确认反转信号

✅ **V7.0.7 ZigZag动态止盈止损**
- 基于1H K线转折点
- 自动识别支撑/阻力位
- 动态调整止盈止损

✅ **完美过滤1月13-14日错误信号**
- 避免损失：+16.70%
- 回测胜率：60.4%

## 性能表现

**12月-1月回测（33天）：**

| 版本 | 策略 | 总收益 | 胜率 | 盈亏比 |
|------|------|--------|------|--------|
| V7.0.1 | 固定止盈止损 | +21.54% | 40.7% | 1.61 |
| V7.0.5 | V7.0.5过滤器 | +88.47% | 56.6% | 1.81 |
| **V7.0.7** | **V7.0.5+ZigZag** | **+90.55%** | **60.4%** | **2.81** |

## 文件说明

- `main_v707.py` - **主程序入口**（推荐使用）
- `README_V7.0.7.md` - 详细文档
- `DEPLOYMENT_GUIDE_V7.0.7.md` - 部署指南

## Telegram配置

⭐ **V4.4专用Token**（已更新）：
```
8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk
```

## 云端部署

详见：[DEPLOYMENT_GUIDE_V7.0.7.md](DEPLOYMENT_GUIDE_V7.0.7.md)

### Zeabur一键部署

1. 推送代码到GitHub
2. Zeabur创建服务 → 选择GitHub仓库
3. 选择`V4.4云端部署文件/btc_4hour_alert`目录
4. 配置环境变量（Telegram token等）
5. 部署

## 系统要求

- Python 3.8+
- 稳定网络连接
- 访问Binance API

## 注意事项

⚠️ **重要**：
- Telegram token已更新为V4.4专用
- 首次运行会立即检查信号
- 状态自动保存到`v707_trader_state.json`

## 技术支持

- 文档：[README_V7.0.7.md](README_V7.0.7.md)
- 部署：[DEPLOYMENT_GUIDE_V7.0.7.md](DEPLOYMENT_GUIDE_V7.0.7.md)

---

**V7.0.7 - 让交易更智能，让盈利更稳定！**
