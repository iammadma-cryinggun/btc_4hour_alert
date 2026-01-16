#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V7.0.7 交易系统 - Zeabur生产入口
⭐ 使用Polling模式（参考SOL系统）
"""

import os
import sys

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    # ⭐ 直接启动交易引擎（使用Polling模式）
    from main_v707 import V707TradingEngine

    engine = V707TradingEngine()
    engine.run()  # 使用Polling模式
