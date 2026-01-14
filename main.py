#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V7.0交易系统 - 主入口
适配Zeabur等云平台的启动要求
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    from v70_trader_runner import main
    main()
