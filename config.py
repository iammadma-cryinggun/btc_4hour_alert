"""
Micro-Apex V1.0 — 核心配置
===========================
Tony 交易哲学 · 盘口微观流动性动量突破系统

项目位置: D:\\TradeProjects\\micro-apex
"""

# ── 交易所 & 交易对 ──
SYMBOL = "BTCUSDT"
EXCHANGE = "binance"

# ── API 端点 ──
API_BASE = "https://api.binance.com/api/v3"

# ── 订单簿深度级别 ──
OBI_DEPTH_LEVELS = [0, 1, 2, 3, 4]  # 0=最优买卖价, 1=第二档...
OBI_WINDOW_SIZE = 5  # 计算OBI时取最近N次深度快照的移动平均
OBI_CONFIRM_DURATION = 3  # OBI需连续N次快照维持阈值以上

# ── 信号阈值 ──
OBI_THRESHOLD_LONG = 0.35
OBI_THRESHOLD_SHORT = -0.35

# CVD确认: 近10秒主动买入占比需>60%
CVD_CONFIRM_RATIO = 0.60
CVD_LOOKBACK_SECONDS = 10

# 假墙检测: 挂单量/近5分钟均值>5倍 & 在被成交前撤单
SPOOF_RATIO = 5.0
SPOOF_WINDOW_SECONDS = 5

# 冰山单检测: 同价位连续成交但价格不移动
ICEBERG_MAX_PRICE_MOVE = 0.01
ICEBERG_LOOKBACK_SECONDS = 5

# ── 宏观趋势过滤 (1H EMA) ──
TREND_EMA_FAST = 20
TREND_EMA_SLOW = 60
TREND_EMA_LONG = 120
TREND_CONFIRM_BARS = 3

# ── 风控参数 ──
MAX_POSITION_RISK = 0.025     # 单笔最大风险敞口(总资金的2.5%)
MAX_TOTAL_EXPOSURE = 0.60     # 总敞口上限60%
HARD_STOP_LOSS_PCT = 0.03     # 硬止损3%
PROFIT_TRIGGER_PCT = 0.05     # 盈利达5%触发保本
BE_PRECISE_RATIO = 1.5        # 盈利达1.5倍止损距离时移至保本
TIME_STOP_SECONDS = 900       # 时间止损15分钟(900秒)
CIRCUIT_BREAKER_LOSSES = 3    # 连亏3笔触发熔断24h
CIRCUIT_BREAKER_LOSS_CUT = 2  # 连亏2笔下一笔仓位减半

# ── Kelly公式参数 ──
KELLY_FRACTION = 0.5          # 半Kelly
MIN_HISTORY_TRADES = 30       # 至少30笔历史数据才启用Kelly

# ── 轮询配置 ──
POLL_INTERVAL_SECONDS = 2    # REST API轮询间隔(秒)

# ── 输出配置 ──
LOG_FILE = "logs/micro_apex_log.csv"
SIGNAL_LOG = "logs/signals.json"
DEBUG_MODE = True

# ── 信号验证配置 ──
SIGNAL_VALIDATION_WINDOW_MINUTES = 5
SIGNAL_VALIDATION_TICKS = 5
