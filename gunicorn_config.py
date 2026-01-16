# -*- coding: utf-8 -*-
"""
Gunicorn配置文件 - 生产环境
适用于Zeabur等云平台
"""

import multiprocessing
import os

# 服务器socket
bind = "0.0.0.0:8080"
backlog = 2048

# Worker进程
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# 最大请求数（避免内存泄漏）
max_requests = 1000
max_requests_jitter = 50

# 日志
accesslog = "-"  # 输出到stdout
errorlog = "-"   # 输出到stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程命名
proc_name = "v707_trading"

# 安全
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# 重启
reload = False
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL（如果需要）
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"
