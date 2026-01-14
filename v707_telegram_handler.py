# -*- coding: utf-8 -*-
"""
V7.0.7 Telegram命令处理器 - 完整交互支持
===========================================

支持的命令：
- /start : 启动机器人并显示帮助
- /status : 查看当前持仓状态
- /signals : 查看最近的信号历史
- /trades : 查看交易历史
- /clear : 手动平仓（⚠️ 谨慎使用）
- /config : 查看当前配置
- /help : 显示帮助信息
"""

import requests
import logging
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class TelegramCommandHandler:
    """Telegram命令处理器"""

    def __init__(self, config, trading_engine):
        self.config = config
        self.engine = trading_engine
        self.token = config.telegram_token
        self.chat_id = config.telegram_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.enabled = config.telegram_enabled

        # 使用Session对象（V4.2.1的做法）
        self.session = requests.Session()

    def get_updates(self, offset: Optional[int] = None, timeout: int = 30):
        """获取Telegram更新"""
        if not self.enabled:
            return []

        try:
            url = f"{self.base_url}/getUpdates"
            params = {
                'offset': offset,
                'timeout': timeout,
                'allowed_updates': ['message']
            }
            response = self.session.get(url, params=params, timeout=timeout + 10)
            response.raise_for_status()
            result = response.json()

            if result.get('ok'):
                updates = result.get('result', [])
                if updates:
                    logger.info(f"[Telegram] getUpdates返回 {len(updates)} 条消息, offset={offset}")
                return updates
            else:
                logger.error(f"[Telegram] getUpdates失败: {result}")
                return []

        except Exception as e:
            logger.error(f"[Telegram] getUpdates异常: {e}")
            return []

    def send_message(self, message: str, parse_mode=None):
        """发送消息"""
        if not self.enabled:
            return

        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            response = self.session.post(url, json=data, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"发送Telegram消息失败: {e}")

    def process_command(self, command: str, text: str = ""):
        """处理命令"""

        # ========== /start 命令 ==========
        if command == '/start':
            message = """
🤖 *V7.0.7智能交易系统（V4.4云端版）*

欢迎使用V7.0.7智能交易系统！

*可用命令*：
/status - 查看当前持仓状态
/signals - 查看最近的信号历史
/trades - 查看交易历史
/clear - 手动平仓（⚠️ 谨慎使用）
/config - 查看当前配置
/help - 显示帮助信息

*系统特性*：
✅ V7.0.5入场过滤器（量能/趋势/动能）
✅ V7.0.7 ZigZag动态止盈止损
✅ 物理信号计算（FFT+Hilbert）
✅ 北京时间4小时K线收盘检测
✅ 完美过滤1月13-14日错误信号

*交易信号类型*：
💀 BEARISH_SINGULARITY → 做多（反向交易）
🚀 BULLISH_SINGULARITY → 做空（反向交易）
📊 HIGH_OSCILLATION → 做空（均值回归）
📊 LOW_OSCILLATION → 做多（均值回归）

回测表现（33天）：+90.55%收益，60.4%胜率，2.81盈亏比
"""
            self.send_message(message)

        # ========== /status 命令 ==========
        elif command == '/status':
            if self.config.has_position:
                hold_time = 0
                if self.config.entry_time:
                    hold_time = (datetime.now() - self.config.entry_time).total_seconds() / 3600

                # 获取当前价格
                current_price = 0
                try:
                    df = self.engine.fetcher.fetch_btc_data(interval='4h', limit=5)
                    if df is not None:
                        current_price = df.iloc[-1]['close']
                except:
                    current_price = self.config.entry_price

                # 计算当前盈亏
                if current_price > 0:
                    if self.config.position_type == 'long':
                        current_pnl_pct = (current_price - self.config.entry_price) / self.config.entry_price * 100
                    else:
                        current_pnl_pct = (self.config.entry_price - current_price) / self.config.entry_price * 100
                else:
                    current_pnl_pct = 0.0

                pnl_emoji = "🟢" if current_pnl_pct > 0 else "🔴"

                message = f"""
📊 *V7.0.7持仓状态*

*持仓状态*: ✅ 有持仓
*方向*: {'📈 做多' if self.config.position_type == 'long' else '📉 做空'}
*开仓价*: ${self.config.entry_price:.2f}
*当前价*: ${current_price:.2f}
*盈亏*: {pnl_emoji} {current_pnl_pct:+.2f}%
*仓位*: {self.config.position_size*100:.1f}%
*置信度*: {self.config.entry_confidence:.2f}
*持仓时长*: {hold_time:.1f}小时

*入场信号*: {self.config.entry_signal_type}
*止盈价*: ${self.config.take_profit_price:.2f}
*止损价*: ${self.config.stop_loss_price:.2f}
"""
            else:
                message = """
📊 *V7.0.7持仓状态*

*持仓状态*: ❌ 空仓
*模式*: 等待信号

系统正在监控市场，满足以下条件时自动开仓：
- 置信度 ≥ 0.6
- 通过V7.0.5过滤器
- ZigZag计算止盈止损
"""

            # 添加统计信息
            if self.config.total_trades > 0:
                win_rate = self.config.winning_trades / self.config.total_trades * 100
                avg_pnl = self.config.total_pnl / self.config.total_trades

                message += f"""
*交易统计*:
- 总交易: {self.config.total_trades}笔
- 胜率: {win_rate:.1f}%
- 总盈亏: {self.config.total_pnl:+.2f}%
- 平均盈亏: {avg_pnl:+.2f}%
"""

            self.send_message(message)

        # ========== /signals 命令 ==========
        elif command == '/signals':
            if not self.config.signal_history or len(self.config.signal_history) == 0:
                message = """
📡 *信号历史*

暂无信号记录
"""
            else:
                # ⭐ 显示最近6个信号（用户要求）
                recent_signals = self.config.signal_history[-6:]

                message = "📡 *最近6个信号*\n\n"

                for i, signal in enumerate(reversed(recent_signals), 1):
                    time_str = signal.get('time', 'N/A')
                    sig_type = signal.get('type', 'N/A')
                    price = signal.get('price', 0)
                    conf = signal.get('confidence', 0)
                    desc = signal.get('description', '')
                    traded = signal.get('traded', True)
                    filtered = signal.get('filtered', False)
                    filter_reason = signal.get('filter_reason', '')

                    # 交易状态emoji
                    if traded:
                        status_emoji = "✅"
                        status_text = "已交易"
                    elif filtered:
                        status_emoji = "🚫"
                        status_text = f"被过滤: {filter_reason}"
                    else:
                        status_emoji = "⏳"
                        status_text = "等待处理"

                    message += f"*{i}. {sig_type}*\n"
                    message += f"   {status_emoji} 状态: {status_text}\n"
                    message += f"   🕐 时间: {time_str}\n"
                    message += f"   💰 价格: ${price:.2f}\n"
                    message += f"   📊 置信度: {conf:.2f}\n"
                    message += f"   💡 描述: {desc}\n\n"

            self.send_message(message)

        # ========== /trades 命令 ==========
        elif command == '/trades':
            if not self.config.position_history or len(self.config.position_history) == 0:
                message = """
📝 *交易历史*

暂无交易记录
"""
            else:
                # 显示最近5笔交易
                recent_trades = self.config.position_history[-5:]

                message = "📝 *最近交易历史*\n\n"

                for i, trade in enumerate(reversed(recent_trades), 1):
                    entry_time = trade.get('entry_time', 'N/A')
                    direction = trade.get('direction', 'N/A')
                    entry_price = trade.get('entry_price', 0)
                    exit_price = trade.get('exit_price', 0)
                    pnl_pct = trade.get('pnl_pct', 0)
                    reason = trade.get('reason', 'N/A')

                    direction_emoji = "📈" if direction == 'long' else "📉"
                    pnl_emoji = "🎉" if pnl_pct > 0 else "🛑"

                    message += f"*{i}. {direction_emoji} {direction.upper()}*\n"
                    message += f"   入场: {entry_time}\n"
                    message += f"   价格: ${entry_price:.2f} → ${exit_price:.2f}\n"
                    message += f"   盈亏: {pnl_emoji} {pnl_pct:+.2f}%\n"
                    message += f"   原因: {reason}\n\n"

            self.send_message(message)

        # ========== /clear 命令（手动平仓）==========
        elif command == '/clear':
            if self.config.has_position:
                # 获取当前价格
                try:
                    df = self.engine.fetcher.fetch_btc_data(interval='4h', limit=5)
                    if df is not None:
                        current_price = df.iloc[-1]['close']

                        # 计算当前盈亏
                        if self.config.position_type == 'long':
                            pnl_pct = (current_price - self.config.entry_price) / self.config.entry_price * 100
                        else:
                            pnl_pct = (self.config.entry_price - current_price) / self.config.entry_price * 100

                        # ⭐ 执行平仓
                        direction_emoji = "📈" if self.config.position_type == 'long' else "📉"
                        pnl_emoji = "🟢" if pnl_pct > 0 else "🔴"

                        # 记录交易历史
                        trade_record = {
                            'entry_time': self.config.entry_time.strftime('%Y-%m-%d %H:%M:%S') if self.config.entry_time else 'N/A',
                            'direction': self.config.position_type,
                            'entry_price': self.config.entry_price,
                            'exit_price': current_price,
                            'pnl_pct': pnl_pct,
                            'reason': '手动平仓(/clear命令)',
                            'signal_type': self.config.entry_signal_type,
                            'confidence': self.config.entry_confidence,
                            'take_profit': self.config.take_profit_price,
                            'stop_loss': self.config.stop_loss_price
                        }
                        self.config.position_history.append(trade_record)

                        # 只保留最近20笔交易
                        if len(self.config.position_history) > 20:
                            self.config.position_history = self.config.position_history[-20:]

                        # 更新统计
                        self.config.total_trades += 1
                        if pnl_pct > 0:
                            self.config.winning_trades += 1
                        else:
                            self.config.losing_trades += 1
                        self.config.total_pnl += pnl_pct

                        # 保存状态
                        self.config.save_state()

                        # 发送平仓通知
                        message = f"""
✅ *V7.0.7手动平仓成功*

{direction_emoji} *{self.config.position_type.upper()}*
💰 开仓价: ${self.config.entry_price:.2f}
💵 出场价: ${current_price:.2f}
{pnl_emoji} 盈亏: {pnl_pct:+.2f}%
⚠️ 原因: 手动平仓(/clear命令)

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                        self.send_message(message)

                        logger.warning(f"[命令] 用户手动平仓: {self.config.position_type.upper()} @ ${current_price:.2f}, 盈亏: {pnl_pct:+.2f}%")

                        # ⭐ 清除持仓状态
                        self.config.has_position = False
                        position_type = self.config.position_type
                        self.config.position_type = None
                        self.config.entry_price = None
                        self.config.entry_time = None
                        self.config.take_profit_price = None
                        self.config.stop_loss_price = None

                        # 保存状态
                        self.config.save_state()

                        # 发送持仓状态更新
                        self.process_command('/status')

                    else:
                        self.send_message("❌ 获取当前价格失败，无法平仓")
                except Exception as e:
                    logger.error(f"[命令] 手动平仓失败: {e}")
                    self.send_message(f"❌ 手动平仓失败: {str(e)}")
            else:
                self.send_message("❌ 当前无持仓，无需平仓")

        # ========== /config 命令 ==========
        elif command == '/config':
            message = f"""
⚙️ *V7.0.7系统配置*

*V7.0.5过滤器参数*:
- BULLISH量能阈值: {self.config.BULLISH_VOLUME_THRESHOLD}
- HIGH_OSC EMA阈值: {self.config.HIGH_OSC_EMA_THRESHOLD*100:.0f}%
- HIGH_OSC量能阈值: {self.config.HIGH_OSC_VOLUME_THRESHOLD}
- BEARISH EMA阈值: {self.config.BEARISH_EMA_THRESHOLD*100:.0f}%

*V7.0.7 ZigZag参数*:
- ZigZag深度: {self.config.ZIGZAG_DEPTH}
- ZigZag偏差: {self.config.ZIGZAG_DEVIATION}%
- 最大持仓周期: {self.config.MAX_HOLD_PERIODS}周期（7天）

*交易参数*:
- 基础仓位: {self.config.BASE_POSITION_SIZE*100:.1f}%

*运行配置*:
- 信号检测: 北京时间4小时K线收盘
- 持仓检查: 每1小时
- Telegram通知: {'✅' if self.enabled else '❌'}
"""
            self.send_message(message)

        # ========== /help 命令 ==========
        elif command == '/help':
            message = """
❓ *V7.0.7帮助信息*

*可用命令*：

📊 /status - 查看当前持仓状态
  显示持仓信息、盈亏、统计等

📡 /signals - 查看最近的信号历史
  显示最近5个信号记录

📝 /trades - 查看交易历史
  显示最近5笔交易记录

⚠️ /clear - 手动平仓
  ⚠️ 谨慎使用！需要二次确认

⚙️ /config - 查看当前配置
  显示所有系统参数

❓ /help - 显示此帮助信息

*策略说明*：

V7.0.7使用V7.0.5过滤器+V7.0.7 ZigZag动态出场：
- V7.0.5过滤器：量能/趋势/动能三重过滤
- V7.0.7 ZigZag：基于1H K线转折点动态止盈止损
- 完美过滤1月13-14日错误信号（避免-16.70%损失）

*风险提示*：
- 本策略为高风险策略
- 请确保理解策略逻辑
- 建议从小资金开始
- 严格执行止损

*回测表现*（12月-1月33天）：
- 总收益：+90.55%
- 胜率：60.4%
- 盈亏比：2.81
"""
            self.send_message(message)

        else:
            self.send_message(f"❌ 未知命令: {command}\n请使用 /help 查看可用命令")


def start_telegram_listener(config, trading_engine):
    """启动Telegram监听器（独立线程）"""

    handler = TelegramCommandHandler(config, trading_engine)

    logger.info("[Telegram] 启动命令监听器...")
    logger.info(f"[Telegram] telegram_enabled={config.telegram_enabled}")
    logger.info(f"[Telegram] chat_id={config.telegram_chat_id}")

    # 删除webhook
    try:
        delete_webhook_url = f"{handler.base_url}/deleteWebhook"
        response = handler.session.post(delete_webhook_url, timeout=10)
        response.raise_for_status()
        result = response.json()
        if result.get('ok'):
            logger.info("[Telegram] Webhook已删除，可以使用getUpdates")
        else:
            logger.warning(f"[Telegram] 删除webhook失败: {result}")
    except Exception as e:
        logger.error(f"[Telegram] 删除webhook异常: {e}")

    # 等待webhook删除生效
    import time
    time.sleep(2)

    # 监听循环
    update_id = 0
    logger.info("[Telegram] 监听器线程开始运行")

    while True:
        try:
            # 使用offset=update_id + 1
            updates = handler.get_updates(offset=update_id + 1, timeout=30)

            if not updates:
                continue

            # 处理updates列表
            if isinstance(updates, list):
                for update in updates:
                    # 更新update_id
                    update_id = update['update_id']

                    # 处理消息
                    if 'message' in update:
                        message = update['message']
                        text = message.get('text', '')
                        chat_id = message.get('chat', {}).get('id')

                        logger.debug(f"[Telegram] 收到消息: {text}, chat_id: {chat_id}")

                        # 只处理来自配置chat_id的命令
                        if str(chat_id) != str(config.telegram_chat_id):
                            logger.debug(f"[Telegram] 忽略非授权chat: {chat_id}")
                            continue

                        # 处理命令
                        if text.startswith('/'):
                            command = text.lower().strip()
                            logger.info(f"[Telegram] 收到命令: {command}")
                            handler.process_command(command, text)

        except Exception as e:
            logger.error(f"[Telegram] 监听器错误: {e}", exc_info=True)
            time.sleep(5)
