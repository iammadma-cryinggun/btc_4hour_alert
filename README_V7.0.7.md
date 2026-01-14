# V7.0.7 智能交易系统 - 云端部署版

## 版本说明

**V7.0.7** - 基于V7.0.5过滤器 + V7.0.7 ZigZag动态止盈止损的智能交易系统

### 核心特性

#### 1. V7.0.5 入场过滤器
- **量能过滤**：BULLISH_SINGULARITY量能>0.95时过滤
- **趋势过滤**：主升浪/主跌浪检测（EMA偏离±5%）
- **动能过滤**：HIGH_OSCILLATION需要向下动能且未放量

#### 2. V7.0.7 ZigZag动态止盈止损
- **基于1H K线转折点**：自动识别支撑/阻力位
- **动态调整**：止盈止损随市场波动实时更新
- **做多**：止盈@最近peak×1.2，止损@最近valley×0.88
- **做空**：止盈@最近valley×0.88，止损@peak与entry中点（max+3%）

#### 3. Telegram实时通知
- 新信号通知（保留EMOJI）
- 开仓/平仓通知
- 持仓状态查询

### 回测表现

**12月-1月数据（33天）：**
- 总收益：**+90.55%**
- 胜率：**60.4%**
- 盈亏比：**2.81**
- **完美过滤1月13-14日8笔连续亏损信号**（避免-16.70%损失）

### V7.0.7 vs V7.0.5 vs V7.0.1

| 版本 | 策略 | 总收益 | 胜率 | 盈亏比 |
|------|------|--------|------|--------|
| V7.0.1 | 固定止盈止损 | +21.54% | 40.7% | 1.61 |
| V7.0.5 | V7.0.5过滤器 | +88.47% | 56.6% | 1.81 |
| **V7.0.7** | **V7.0.5+ZigZag** | **+90.55%** | **60.4%** | **2.81** |

## 快速开始

### 1. 配置环境变量

复制`.env.example`为`.env`并配置：

```bash
cp .env.example .env
```

`.env`文件内容：
```env
TELEGRAM_TOKEN=8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk
TELEGRAM_CHAT_ID=838429342
TELEGRAM_ENABLED=True
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行系统

**Windows:**
```bash
python main_v707.py
```

**Linux:**
```bash
python3 main_v707.py
```

### 4. 后台运行（推荐）

**使用screen（Linux）：**
```bash
screen -S v707_trader
python3 main_v707.py
# 按Ctrl+A+D分离
# 重新连接：screen -r v707_trader
```

**使用nohup：**
```bash
nohup python3 main_v707.py > v707.log 2>&1 &
```

## 系统架构

```
V7.0.7 智能交易系统
├─ 信号计算
│  └─ FFT+Hilbert物理计算（继承v4.2数学家策略）
│
├─ V7.0.5入场过滤器
│  ├─ 量能过滤
│  ├─ EMA趋势过滤
│  └─ 动能过滤
│
├─ V7.0.7 ZigZag出场管理器
│  ├─ 1H K线转折点检测
│  ├─ 动态止盈计算
│  └─ 动态止损计算
│
└─ Telegram通知
   ├─ 信号通知
   ├─ 开仓通知
   └─ 平仓通知
```

## 文件说明

- `main_v707.py` - 主程序入口
- `v707_trader_main.py` - 核心交易逻辑（前半部分）
- `v707_trader_complete.py` - 完整交易逻辑（合并版）
- `V705_entry_filter.py` - V7.0.5入场过滤器
- `V707_zigzag_exit.py` - V7.0.7 ZigZag出场管理器

## 运行频率

- **信号检查**：每4小时（在4H K线收盘时）
- **持仓检查**：每1小时

## 日志

- 运行日志：`v707_trader.log`
- 状态文件：`v707_trader_state.json`

## 云端部署

### Zeabur部署

1. 推送代码到GitHub
2. 在Zeabur创建新服务
3. 选择Python环境
4. 配置环境变量
5. 部署

### Docker部署

```bash
docker build -t v707-trader .
docker run -d --name v707-trader --env-file .env v707-trader
```

## 注意事项

1. ⚠️ **首次运行**：系统会立即执行一次信号检查
2. ⚠️ **状态保存**：系统状态自动保存到`v707_trader_state.json`
3. ⚠️ **重启恢复**：重启后会自动恢复持仓状态
4. ⚠️ **Telegram Token**：已更新为V4.4专用token，不要与V4.3混淆

## V4.4 vs V4.3 对比

| 特性 | V4.3 | V4.4 |
|------|------|------|
| 入场过滤器 | 无 | V7.0.5过滤器 |
| 出场策略 | V7.0 Combat | V7.0.7 ZigZag |
| 回测收益（33天）| +21.54% | +90.55% |
| 胜率（33天） | 40.7% | 60.4% |
| 过滤1月13-14 | ❌ 未过滤 | ✅ 完美过滤 |
| Telegram Token | 818966... | 850518... |

## 技术支持

- GitHub Issues：[提交问题](https://github.com/yourusername/v44/issues)
- Telegram：@your_username

---

**V7.0.7 智能交易系统** - 让交易更智能，让盈利更稳定！
