"""
V4.2 云端环境配置适配器
自动检测运行环境并调整配置
"""
import os
import logging

logger = logging.getLogger(__name__)

def detect_environment():
    """检测运行环境"""

    # 检测是否在云环境
    env_indicators = [
        'ZEABUR',          # Zeabur
        'HEROKU',          # Heroku
        'RENDER',          # Render
        'VERCEL',          # Vercel
        'CLOUD_RUN',       # Cloud Run
        'AWS',             # AWS
        'AZURE',           # Azure
        'DOCKER',          # Docker
        'KUBERNETES',      # Kubernetes
    ]

    for indicator in env_indicators:
        if os.getenv(indicator):
            return 'cloud'

    # 检测是否在本地环境
    if os.path.exists('/.dockerenv'):
        return 'docker'

    return 'local'

def adjust_proxy_config(config_class):
    """根据环境调整代理配置"""

    env = detect_environment()
    logger.info(f"检测到运行环境: {env}")

    if env == 'cloud' or env == 'docker':
        # 云环境禁用代理
        logger.info("云环境检测到，禁用代理配置")
        config_class.proxy_enabled = False
        config_class.proxy_host = None
        config_class.proxy_port = None
        config_class.proxy_http = None
        config_class.proxy_https = None
    else:
        # 本地环境启用代理
        logger.info("本地环境，启用代理配置")
        # 保持原有代理配置

    return config_class
