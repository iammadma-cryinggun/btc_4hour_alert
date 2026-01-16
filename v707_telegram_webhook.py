# -*- coding: utf-8 -*-
"""
V7.0.7 Telegram命令处理器（Polling模式）
===========================================

使用Telebot Polling模式，参考SOL系统
优势：
- ✅ 配置简单，无需设置Webhook
- ✅ 适合后台worker进程
- ✅ 和SOL系统完全一致
"""

import telebot
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ⭐ 北京时间（UTC+8）
BEIJING_TZ_OFFSET = timedelta(hours=8)


def get_beijing_time():
    """获取当前北京时间"""
    return datetime.utcnow() + BEIJING_TZ_OFFSET


class TelegramWebhookHandler:
    """Telegram命令处理器（Polling模式）"""

    def __init__(self, config, trading_engine):
        self.config = config
        self.engine = trading_engine
        self.token = config.telegram_token
        self.chat_id = config.telegram_chat_id
        self.enabled = config.telegram_enabled

        # 初始化bot和注册处理器
        if self.enabled and self.token:
            try:
                self.bot = telebot.TeleBot(self.token)
                logger.info("[Telegram] WebHandler TeleBot初始化成功")
                self._register_handlers()
            except Exception as e:
                logger.error(f"[Telegram] WebHandler初始化失败: {e}")
                self.bot = None
                self.enabled = False
        else:
            logger.warning("[Telegram] 未启用或token为空")
            self.bot = None

        # Flask应用（保留但不使用）
        self.app = None

    def _register_handlers(self):
        """注册Telegram消息处理器"""
        if not self.bot:
            return

        from telebot import types

        @self.bot.message_handler(commands=['start', 'help'])
        def send_help(message):
            if message.chat.id != int(self.chat_id):
                return
            help_text = """
🤖 V7.0.7交易系统 - 交互式控制

可用命令：
/status - 查看当前持仓状态
/signals - 查看最近6个信号
/trades - 查看交易历史
/clear - 手动平仓
/config - 查看系统配置

V7.0.7特性：
- V7.0.5入场过滤器（量能/趋势/动能）
- V7.0.7 ZigZag动态止盈止损
- Webhook模式（无409冲突）
            """
            try:
                self.bot.reply_to(message, help_text)
            except Exception as e:
                logger.error(f"[Telegram] 发送帮助失败: {e}")

        @self.bot.message_handler(commands=['status'])
        def send_status(message):
            if message.chat.id != int(self.chat_id):
                return

            try:
                now_beijing = get_beijing_time()
                if self.config.has_position:
                    hold_time = 0
                    if self.config.entry_time:
                        hold_time = (now_beijing - self.config.entry_time).total_seconds() / 3600

                    current_price = 0
                    try:
                        df = self.engine.fetcher.fetch_btc_data(interval='4h', limit=5)
                        if df is not None:
                            current_price = df.iloc[-1]['close']
                    except:
                        pass

                    if current_price > 0:
                        if self.config.position_type == 'long':
                            current_pnl_pct = (current_price - self.config.entry_price) / self.config.entry_price * 100
                        else:
                            current_pnl_pct = (self.config.entry_price - current_price) / self.config.entry_price * 100
                    else:
                        current_pnl_pct = 0.0

                    pnl_emoji = "🟢" if current_pnl_pct > 0 else "🔴"

                    # 计算止盈止损百分比
                    tp_pct = 0
                    sl_pct = 0
                    if self.config.take_profit_price:
                        tp_pct = (self.config.take_profit_price - self.config.entry_price) / self.config.entry_price * 100
                    if self.config.stop_loss_price:
                        sl_pct = (self.config.stop_loss_price - self.config.entry_price) / self.config.entry_price * 100

                    status_text = f"""📊 V7.0.7持仓状态

📍 方向: {'📈 做多' if self.config.position_type == 'long' else '📉 做空'}
💰 入场价: ${self.config.entry_price:.2f}
💵 当前价: ${current_price:.2f}
{pnl_emoji} 盈亏: {current_pnl_pct:+.2f}%
🎯 止盈: ${self.config.take_profit_price:.2f} ({tp_pct:+.2f}%)
🛑 止损: ${self.config.stop_loss_price:.2f} ({sl_pct:+.2f}%)
⏱ 持仓时长: {hold_time:.1f}小时
📊 入场置信度: {self.config.entry_confidence:.2f}

📈 总交易: {self.config.total_trades}
✅ 盈利: {self.config.winning_trades}
❌ 亏损: {self.config.losing_trades}
💵 总盈亏: {self.config.total_pnl:.2f}%
"""
                else:
                    status_text = f"""📊 V7.0.7系统状态

⭕ 当前状态: 空仓
📈 总交易: {self.config.total_trades}
✅ 盈利: {self.config.winning_trades}
❌ 亏损: {self.config.losing_trades}
💵 总盈亏: {self.config.total_pnl:.2f}%

⏰ {now_beijing.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)
"""

                self.bot.reply_to(message, status_text)
            except Exception as e:
                logger.error(f"[Telegram] 发送状态失败: {e}")

        @self.bot.message_handler(commands=['signals'])
        def send_signals(message):
            if message.chat.id != int(self.chat_id):
                return

            try:
                signals = self.config.signal_history[-6:]  # 最近6个信号

                if not signals:
                    self.bot.reply_to(message, "暂无信号历史")
                    return

                signals_text = "📊 最近6个信号:\n\n"
                for sig in signals:
                    traded_emoji = "✅" if sig.get('traded', False) else "❌"
                    filtered_emoji = "🚫" if sig.get('filtered', False) else "✅"

                    signals_text += f"""{traded_emoji} {sig.get('type', 'N/A')}
💰 ${sig.get('price', 0):.2f} | C={sig.get('confidence', 0):.2f}
{filtered_emoji} {sig.get('filter_reason', sig.get('reason', 'N/A'))}
⏰ {sig.get('time', 'N/A')}

"""

                self.bot.reply_to(message, signals_text)
            except Exception as e:
                logger.error(f"[Telegram] 发送信号失败: {e}")

        @self.bot.message_handler(commands=['trades'])
        def send_trades(message):
            if message.chat.id != int(self.chat_id):
                return

            try:
                trades = self.config.trade_history

                if not trades:
                    self.bot.reply_to(message, "暂无交易历史")
                    return

                trades_text = f"📊 交易历史 (最近{len(trades)}笔):\n\n"
                for trade in trades[-10:]:  # 最近10笔
                    direction_emoji = "📈" if trade.get('direction') == 'long' else "📉"
                    pnl_emoji = "🟢" if trade.get('pnl_pct', 0) > 0 else "🔴"

                    trades_text += f"""{direction_emoji} {trade.get('direction', 'N/A').upper()}
💰 入场: ${trade.get('entry_price', 0):.2f}
💵 出场: ${trade.get('exit_price', 0):.2f}
{pnl_emoji} 盈亏: {trade.get('pnl_pct', 0):+.2f}%
⏰ {trade.get('entry_time', 'N/A')} → {trade.get('exit_time', 'N/A')}
📝 {trade.get('exit_reason', 'N/A')}

"""

                self.bot.reply_to(message, trades_text)
            except Exception as e:
                logger.error(f"[Telegram] 发送交易历史失败: {e}")

        @self.bot.message_handler(commands=['clear'])
        def manual_close(message):
            if message.chat.id != int(self.chat_id):
                return

            try:
                if not self.config.has_position:
                    self.bot.reply_to(message, "❌ 当前无持仓")
                    return

                # 获取当前价格
                current_price = 0
                try:
                    df = self.engine.fetcher.fetch_btc_data(interval='4h', limit=5)
                    if df is not None:
                        current_price = df.iloc[-1]['close']
                except Exception as e:
                    logger.error(f"[Telegram] 获取价格失败: {e}")

                if current_price == 0:
                    self.bot.reply_to(message, "❌ 获取当前价格失败，无法平仓")
                    return

                # 计算盈亏
                if self.config.position_type == 'long':
                    pnl_pct = (current_price - self.config.entry_price) / self.config.entry_price * 100
                else:
                    pnl_pct = (self.config.entry_price - current_price) / self.config.entry_price * 100

                # 更新统计
                self.config.total_trades += 1
                if pnl_pct > 0:
                    self.config.winning_trades += 1
                else:
                    self.config.losing_trades += 1
                self.config.total_pnl += pnl_pct

                # 记录交易
                trade_record = {
                    'entry_time': self.config.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'exit_time': get_beijing_time().strftime('%Y-%m-%d %H:%M:%S'),
                    'direction': self.config.position_type,
                    'entry_price': self.config.entry_price,
                    'exit_price': current_price,
                    'pnl_pct': pnl_pct,
                    'exit_reason': '手动平仓(/clear命令)'
                }
                self.config.trade_history.append(trade_record)

                direction_emoji = "📈" if self.config.position_type == 'long' else "📉"
                pnl_emoji = "🟢" if pnl_pct > 0 else "🔴"

                # 发送平仓通知
                now_beijing = get_beijing_time()
                message_text = f"""✅ V7.0.7手动平仓成功

{direction_emoji} {self.config.position_type.upper()}
💰 开仓价: ${self.config.entry_price:.2f}
💵 出场价: ${current_price:.2f}
{pnl_emoji} 盈亏: {pnl_pct:+.2f}%
⚠️ 原因: 手动平仓(/clear命令)

⏰ {now_beijing.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)
"""

                # 清除持仓状态
                self.config.has_position = False
                self.config.position_type = None
                self.config.entry_price = None
                self.config.entry_time = None
                self.config.take_profit_price = None
                self.config.stop_loss_price = None

                # 保存状态
                self.config.save_state()

                logger.warning(f"[命令] 用户手动平仓: {self.config.position_type.upper()} @ ${current_price:.2f}, 盈亏: {pnl_pct:+.2f}%")

                self.bot.reply_to(message, message_text)
            except Exception as e:
                logger.error(f"[Telegram] 手动平仓失败: {e}")
                self.bot.reply_to(message, f"❌ 手动平仓失败: {str(e)}")

        @self.bot.message_handler(commands=['config'])
        def send_config(message):
            if message.chat.id != int(self.chat_id):
                return

            try:
                config_text = f"""⚙️ V7.0.7系统配置

V7.0.5过滤器参数:
- BULLISH量能阈值: {self.config.BULLISH_VOLUME_THRESHOLD}
- HIGH_OSC EMA阈值: {self.config.HIGH_OSC_EMA_THRESHOLD*100:.0f}%
- HIGH_OSC量能阈值: {self.config.HIGH_OSC_VOLUME_THRESHOLD}
- BEARISH EMA阈值: {self.config.BEARISH_EMA_THRESHOLD*100:.0f}%

V7.0.7 ZigZag参数:
- ZigZag深度: {self.config.ZIGZAG_DEPTH}
- ZigZag偏差: {self.config.ZIGZAG_DEVIATION}%
- 最大持仓周期: {self.config.MAX_HOLD_PERIODS}周期（7天）

交易参数:
- 基础仓位: {self.config.BASE_POSITION_SIZE*100:.1f}%

运行配置:
- 信号检测: 北京时间4小时K线收盘
- 持仓检查: 每1小时
- Webhook模式: ✅
"""
                self.bot.reply_to(message, config_text)
            except Exception as e:
                logger.error(f"[Telegram] 发送配置失败: {e}")

        logger.info("[Telegram] 消息处理器已注册")

    def _setup_flask_routes(self):
        """设置Flask路由"""

        @self.app.route(f'/{self.token}', methods=['POST'])
        def webhook():
            """Telegram webhook端点"""
            if request.headers.get('content-type') == 'application/json':
                json_string = request.get_data().decode('utf-8')
                update = telebot.types.Update.de_json(json_string)
                self.bot.process_new_updates([update])
                return 'OK', 200
            else:
                return 'Invalid Content-Type', 403

        @self.app.route('/health', methods=['GET'])
        def health():
            """健康检查端点（Zeabur需要）"""
            return 'OK', 200

        @self.app.route('/', methods=['GET'])
        def index():
            """根路径"""
            return 'V7.0.7 Telegram Webhook Handler', 200

    def send_message(self, message, parse_mode='Markdown'):
        """发送消息到Telegram（供其他模块调用）"""
        if not self.bot:
            logger.warning("[Telegram] Bot未初始化，无法发送消息")
            return False

        try:
            self.bot.send_message(self.chat_id, message, parse_mode=parse_mode)
            logger.info("[Telegram] 消息已发送")
            return True
        except Exception as e:
            logger.error(f"[Telegram] 发送消息失败: {e}")
            return False

    def set_webhook(self, webhook_url):
        """设置Telegram Webhook"""
        if not self.bot:
            logger.error("[Telegram] Bot未初始化，无法设置webhook")
            return False

        try:
            success = self.bot.set_webhook(url=webhook_url)
            if success:
                logger.info(f"[Telegram] Webhook设置成功: {webhook_url}")
                return True
            else:
                logger.error(f"[Telegram] Webhook设置失败: {webhook_url}")
                return False
        except Exception as e:
            logger.error(f"[Telegram] 设置webhook异常: {e}")
            return False

    def remove_webhook(self):
        """删除Telegram Webhook"""
        if not self.bot:
            return False

        try:
            self.bot.delete_webhook()
            logger.info("[Telegram] Webhook已删除")
            return True
        except Exception as e:
            logger.error(f"[Telegram] 删除webhook失败: {e}")
            return False

    def run_flask(self, port=8080, host='0.0.0.0'):
        """运行Flask服务器（阻塞）"""
        if not self.enabled:
            logger.warning("[Telegram] 未启用，跳过Flask启动")
            return

        logger.info(f"[Telegram] Flask服务器启动在 {host}:{port}")
        logger.info(f"[Telegram] Webhook路径: /{self.token}")
        self.app.run(host=host, port=port)

    def run_flask_threaded(self, port=8080, host='0.0.0.0'):
        """在后台线程运行Flask服务器"""
        if not self.enabled:
            logger.warning("[Telegram] 未启用，跳过Flask启动")
            return None

        flask_thread = threading.Thread(
            target=self.run_flask,
            kwargs={'port': port, 'host': host},
            daemon=True
        )
        flask_thread.start()
        logger.info(f"[Telegram] Flask服务器已启动（后台线程）")
        return flask_thread


# 便捷函数
def create_webhook_handler(config, trading_engine):
    """创建Webhook处理器"""
    return TelegramWebhookHandler(config, trading_engine)


if __name__ == "__main__":
    # 测试代码
    class TestConfig:
        telegram_token = "8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk"
        telegram_chat_id = "838429342"
        telegram_enabled = True
        has_position = False
        signal_history = []
        trade_history = []
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        total_pnl = 0.0

        # V7.0.5参数
        BULLISH_VOLUME_THRESHOLD = 0.95
        HIGH_OSC_EMA_THRESHOLD = 0.02
        HIGH_OSC_VOLUME_THRESHOLD = 1.1
        BEARISH_EMA_THRESHOLD = -0.05

        # V7.0.7参数
        ZIGZAG_DEPTH = 12
        ZIGZAG_DEVIATION = 5
        MAX_HOLD_PERIODS = 168
        BASE_POSITION_SIZE = 0.30

        entry_time = None
        entry_price = None
        position_type = None
        entry_confidence = 0.0
        take_profit_price = None
        stop_loss_price = None

        def save_state(self):
            pass

    class TestEngine:
        class Fetcher:
            def fetch_btc_data(self, interval, limit):
                return None

        fetcher = Fetcher()

    # 测试webhook
    config = TestConfig()
    engine = TestEngine()
    handler = create_webhook_handler(config, engine)

    print("Webhook服务器启动在 http://0.0.0.0:8080")
    print("Webhook URL: https://your-domain.com/<TOKEN>")
    handler.run_flask()
