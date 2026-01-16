#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V7.0.7交易系统 - 主入口（⭐ 已更新）
适配Zeabur等云平台的启动要求
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    # ⭐ 运行V7.0.7版本（带telebot库修复）
    from main_v707 import V707TradingEngine
    engine = V707TradingEngine()
    engine.run()
