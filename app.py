"""
Micro-Apex V1.0 — Zeabur 部署入口
"""
import sys
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from micro_apex import main

if __name__ == "__main__":
    main()
