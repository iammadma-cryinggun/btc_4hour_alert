# Micro-Apex Memory Index

## Project Overview
- **名称**: Micro-Apex V1.0 — 盘口微观流动性动量突破系统
- **哲学基础**: 《交易之王》Tony 交易哲学
- **核心思想**: OBI订单簿失衡 + CVD成交差 + 多时间框架趋势过滤 + 半凯利风控
- **位置**: `D:\TradeProjects\micro-apex\`

## Architecture
| 文件 | 用途 |
|------|------|
| `micro_apex.py` | 核心入口 (REST轮询模式) |
| `config.py` | 核心配置 (交易对、API、风控参数) |
| `obi_engine.py` | 订单簿失衡率(OBI)计算 |
| `cvd_engine.py` | 累积成交量差(CVD)计算 |
| `iceberg_spoof_detector.py` | 冰山委托 & 大单假墙检测 |
| `trend_filter.py` | 多时间框架趋势过滤 (1H/4H EMA) |
| `signal_engine.py` | 信号触发 + 半凯利仓位 + 连亏断路器 |
| `signal_validator.py` | 信号验证模块 |

## Tony Philosophy Mappings
- 永远不要逆势 → 1H/4H EMA趋势过滤
- OBI订单失衡 → OBI>0.35确认买压主导
- CVD成交差 → CVD买方占比>60%确认
- 半Kelly仓位 → Kelly公式*0.5动态仓位
- 连亏断路器 → 3笔连亏→24h熔断
- 移动保本 → 盈利5%后移至保本位
- 时间止损 → 15分钟未脱离成本区→平仓
- 假墙反杀 → 检测Spoofing后反向信号

## Desktop Backups (已归类)
- `desktop_backups/` — 桌面原始副本(旧版/草稿)，供追溯
- `docs/notes/` — OCR笔记(交易之王语录合集)

## Running
```bash
cd D:\TradeProjects\micro-apex
python micro_apex.py
```
