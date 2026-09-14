"""
Micro-Apex V1.0 — Zeabur 部署入口
"""
import sys
import os
import traceback

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

try:
    from micro_apex import main
    print("Micro-Apex loaded successfully")
except Exception as e:
    print(f"Failed to import micro_apex: {e}")
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
