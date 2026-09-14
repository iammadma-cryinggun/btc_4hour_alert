# Micro-Apex V1.0 — 盘口微观流动性动量突破系统

## 项目描述
基于《交易之王》Tony 交易哲学的量化交易系统。
核心思想: OBI订单簿失衡 + CVD成交差 + 多时间框架趋势过滤 + 半凯利风控。

## 架构
- `obi_engine.py` — 订单簿失衡率(OBI)计算引擎
- `cvd_engine.py` — 累积成交量差(CVD)计算引擎
- `iceberg_spoof_detector.py` — 冰山委托 & 大单假墙检测
- `trend_filter.py` — 多时间框架趋势过滤器(1H/4H EMA)
- `signal_engine.py` — 信号触发 + 半凯利仓位 + 连亏断路器
- `micro_apex.py` — 核心入口(REST轮询模式)

## 运行
```bash
cd D:\TradeProjects\micro-apex
python micro_apex.py
```

## Tony哲学核心映射
| Tony原则 | 系统实现 |
|----------|---------|
| 永远不要逆势 | 1H/4H EMA趋势过滤 |
| OBI订单失衡 | OBI>0.35确认买压主导 |
| CVD成交差 | CVD买方占比>60%确认 |
| 半Kelly仓位 | Kelly公式*0.5动态仓位 |
| 连亏断路器 | 3笔连亏→24h熔断 |
| 移动保本 | 盈利5%后移至保本位 |
| 时间止损 | 15分钟未脱离成本区→平仓 |
| 假墙反杀 | 检测Spoofing后反向信号 |
