#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试可能的Zeabur URL
"""

import requests

BOT_TOKEN = "8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk"

# 可能的URL格式
possible_urls = [
    "https://btc-4hour-alert.zeabur.app",
    "https://btc-4hour-alert-6966446c12c8e2c31de92487.zeabur.app",
    "https://service-6966446c12c8e2c31de92487.zeabur.app",
    "https://6966446c12c8e2c31de92487.zeabur.app",
]

print("=" * 70)
print("测试可能的Zeabur URL")
print("=" * 70)

for base_url in possible_urls:
    print(f"\n测试: {base_url}")

    # 测试health端点
    try:
        health_url = f"{base_url}/health"
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200 and response.text == 'OK':
            print(f"  ✅ 找到了！这个URL有效")
            print(f"  ✅ Webhook URL: {base_url}/{BOT_TOKEN}")

            # 设置webhook
            webhook_url = f"{base_url}/{BOT_TOKEN}"
            set_webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
            data = {"url": webhook_url}

            print(f"\n正在设置Webhook...")
            resp = requests.post(set_webhook_url, data=data)
            result = resp.json()

            if result.get('ok'):
                print(f"  ✅ Webhook设置成功！")
                print(f"\n现在可以测试Telegram命令了：")
                print(f"  发送 /status 到bot")
            else:
                print(f"  ❌ Webhook设置失败: {result}")

            break
        else:
            print(f"  ❌ 状态码: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"  ❌ 错误: {str(e)[:50]}")
else:
    print("\n❌ 没有找到有效的URL")
    print("请在Zeabur控制面板查看服务名称或域名设置")
