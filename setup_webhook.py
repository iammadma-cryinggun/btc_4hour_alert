#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Telegram Webhook设置脚本
运行此脚本可以自动设置Telegram Webhook
"""

import requests

BOT_TOKEN = "8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk"

def get_webhook_info():
    """获取当前Webhook信息"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    response = requests.get(url)
    return response.json()

def delete_webhook():
    """删除当前Webhook"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    response = requests.get(url)
    return response.json()

def set_webhook(webhook_url):
    """设置Webhook"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    data = {"url": webhook_url}
    response = requests.post(url, data=data)
    return response.json()

if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("Telegram Webhook设置工具")
    print("=" * 70)

    # 1. 查看当前Webhook状态
    print("\n1. 当前Webhook状态:")
    info = get_webhook_info()
    print(f"   URL: {info.get('result', {}).get('url', '未设置')}")

    # 2. 设置新Webhook
    if len(sys.argv) > 1:
        webhook_url = sys.argv[1]
        print(f"\n2. 设置Webhook: {webhook_url}")

        result = set_webhook(webhook_url)
        if result.get('ok'):
            print("   ✅ Webhook设置成功！")
        else:
            print(f"   ❌ Webhook设置失败: {result}")
    else:
        print("\n2. 使用方法:")
        print("   python setup_webhook.py https://your-app.zeabur.app")
        print("   (不要加TOKEN，脚本会自动添加)")
