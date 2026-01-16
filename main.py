#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V7.0.7 交易系统 - Zeabur/GitHub自动部署入口
⭐ Zeabur会自动运行这个文件
"""

import os
import sys

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    # ⭐ 导入并启动完整的交易系统
    print("[启动] V7.0.7交易系统启动中...")

    # 导入交易引擎
    from main_v707 import V707TradingEngine

    # 创建并运行引擎
    engine = V707TradingEngine()
    engine.run()  # 这会启动Flask Webhook服务器和主循环
