# -*- coding: utf-8 -*-
"""
V7.0.7 生产环境启动脚本（Gunicorn + Flask Webhook）
=================================================================

适用于Zeabur等云平台的生产级部署

启动命令：
    gunicorn -c gunicorn_config.py main_production:app

或使用Python直接启动（开发环境）：
    python main_production.py

=================================================================
"""

import os
import sys
import logging

# 导入主程序
from main_v707 import V707TradingEngine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 全局变量（用于WSGI服务器）
trading_engine = None
flask_app = None


def create_app():
    """创建Flask应用（用于Gunicorn）"""
    global trading_engine, flask_app

    # 创建交易引擎
    trading_engine = V707TradingEngine()

    # 获取Flask应用
    flask_app = trading_engine.webhandler.app

    logger.info("[启动] Flask应用已创建")

    return flask_app


# WSGI应用入口（Gunicorn需要）
app = create_app()


def run_development():
    """开发服务器启动（仅用于测试）"""
    global trading_engine

    # 创建交易引擎
    trading_engine = V707TradingEngine()

    # 启动主循环（后台线程）
    import threading
    main_loop_thread = threading.Thread(
        target=trading_engine.run,
        daemon=True
    )
    main_loop_thread.start()

    # 启动Flask开发服务器
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"[启动] Flask开发服务器启动在端口 {port}")
    logger.warning("[警告] 这是开发服务器，生产环境请使用Gunicorn")

    trading_engine.webhandler.run_flask(port=port, host='0.0.0.0')


if __name__ == "__main__":
    # 开发模式：直接运行此脚本
    run_development()
