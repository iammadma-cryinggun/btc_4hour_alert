# V4.1.1 GitHub 部署指南

## 🎯 目标仓库
```
https://github.com/iammadma-cryinggun/btc_4hour_alert
```

## 📦 部署文件清单

### 必需文件（10个）
1. ✅ `BTC4小时策略预警v4.1.1_纯净版.py` - 主程序
2. ✅ `requirements_v411.txt` - Python依赖
3. ✅ `dxy_data.csv` - DXY数据
4. ✅ `Dockerfile` - Docker镜像配置
5. ✅ `.zeabur.yml` - Zeabur部署配置
6. ✅ `.gitignore` - Git忽略文件
7. ✅ `README_V4.1.1.md` - 部署导航
8. ✅ `Zeabur部署指南.md` - Zeabur详细指南
9. ✅ `V4.1.1更新说明.md` - 版本说明
10. ✅ `V4.1.1部署清单.md` - 部署检查清单

## 🚀 快速部署到GitHub

### 步骤1: 准备本地文件
```bash
# 创建工作目录
mkdir btc_4hour_alert
cd btc_4hour_alert

# 复制所有文件到这里
# （从V4.1.1云端部署文件复制所有必需文件）
```

### 步骤2: 初始化Git仓库
```bash
git init
git add .
git commit -m "V4.1.1 双信号版 - 初始部署

- 基础物理信号4H记录（复盘用）
- V4.1 Smart Ape完整交易系统
- Zeabur一键部署支持
"
```

### 步骤3: 推送到GitHub
```bash
# 添加远程仓库
git remote add origin https://github.com/iammadma-cryinggun/btc_4hour_alert.git

# 推送到main分支
git branch -M main
git push -u origin main
```

## 🔐 GitHub访问配置

### 方式1: HTTPS（推荐）
```bash
# 使用GitHub Personal Access Token
# 1. 生成Token: https://github.com/settings/tokens
# 2. 权限: repo (full control)

# 推送时输入用户名和Token
git push -u origin main
# Username: iammadma-cryinggun
# Password: <你的Token>
```

### 方式2: SSH（需配置）
```bash
# 1. 生成SSH密钥
ssh-keygen -t rsa -b 4096 -C "你的邮箱"

# 2. 添加公钥到GitHub
# 复制 ~/.ssh/id_rsa.pub 内容到
# https://github.com/settings/keys

# 3. 使用SSH推送
git remote set-url origin git@github.com:iammadma-cryinggun/btc_4hour_alert.git
git push -u origin main
```

## 🌐 Zeabur一键部署

### 步骤1: 登录Zeabur
1. 访问：https://zeabur.com
2. 使用GitHub账号登录

### 步骤2: 创建新项目
1. 点击"Create New Project"
2. 项目名称：`btc-physics-v411`
3. 选择区域：推荐Hong Kong或Singapore

### 步骤3: 导入GitHub仓库
1. 选择"Deploy from GitHub"
2. 选择仓库：`iammadma-cryinggun/btc_4hour_alert`
3. 选择分支：`main`
4. Zeabur会自动识别`.zeabur.yml`配置

### 步骤4: 配置服务
Zeabur会自动读取配置，但需要确认：
- ✅ Service Name: `btc-physics-v411`
- ✅ Type: Worker
- ✅ CPU: 0.5核
- ✅ Memory: 512MB
- ✅ Regions: Hong Kong

### 步骤5: 部署
点击"Deploy"按钮，等待：
1. 构建Docker镜像（约2-3分钟）
2. 启动容器
3. 运行程序

### 步骤6: 验证部署
在Zeabur控制台：
1. 查看日志（Logs标签）
2. 确认无错误信息
3. 检查Telegram是否收到启动通知

## 📝 环境变量配置

在Zeabur控制台添加环境变量：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `TZ` | `Asia/Shanghai` | 时区 |
| `PYTHONUNBUFFERED` | `1` | Python输出不缓存 |
| `TELEGRAM_TOKEN` | `8189663571:AA...` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | `838429342` | Telegram Chat ID |
| `PROXY_ENABLED` | `false` | 是否启用代理 |
| `PROXY_HOST` | `127.0.0.1` | 代理主机 |
| `PROXY_PORT` | `15236` | 代理端口 |

## 💾 持久化存储配置

在Zeabur控制台添加Volume：
- **路径**: `/app/data`
- **大小**: 1GB
- **用途**: 保存运行时数据

## 🔄 持续集成（自动部署）

### GitHub Actions配置
创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy to Zeabur

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v3

      - name: Deploy to Zeabur
        uses: zeabur/checkout-action@v1
        with:
          deploy_key: ${{ secrets.ZEABUR_DEPLOY_KEY }}
          service_id: ${{ secrets.ZEABUR_SERVICE_ID }}
```

### 配置Secrets
在GitHub仓库设置中添加：
1. `ZEABUR_DEPLOY_KEY`: 从Zeabur获取
2. `ZEABUR_SERVICE_ID`: 从Zeabur获取

### 自动部署流程
```
代码推送 → GitHub Actions → Zeabur → 自动构建 → 自动部署
```

## 📊 监控和维护

### 查看日志
```bash
# Zeabur CLI
zeabur logs btc-physics-v411 --follow

# 或在Web控制台查看
```

### 重启服务
在Zeabur控制台点击"Restart"按钮

### 查看资源使用
- CPU使用率
- 内存使用
- 网络流量
- 存储空间

### 导出数据
```bash
# 使用Zeabur CLI
zeabur volumes download btc-physics-v411 /app/data
```

## 🛠️ 故障排查

### 问题1: 部署失败
**检查**:
- GitHub仓库是否公开
- `.zeabur.yml`是否正确
- `Dockerfile`是否存在

**解决**:
```bash
# 本地测试Docker构建
docker build -t test-v411 .
docker run -it test-v411
```

### 问题2: 程序无法启动
**检查**:
- 环境变量是否配置
- `dxy_data.csv`是否存在
- 日志错误信息

**解决**:
```bash
# 查看详细日志
zeabur logs btc-physics-v411

# 重启服务
zeabur restart btc-physics-v411
```

### 问题3: 无法接收Telegram通知
**检查**:
- `TELEGRAM_TOKEN`是否正确
- `TELEGRAM_CHAT_ID`是否正确
- 网络是否可访问Telegram

**解决**:
```python
# 手动测试Telegram
import requests
token = "你的token"
chat_id = "你的chat_id"
resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": "测试消息"})
print(resp.json())
```

## 📋 部署清单

### GitHub仓库
- [ ] 仓库已创建
- [ ] 文件已上传
- [ ] README已添加
- [ ] Gitignore已配置

### Zeabur配置
- [ ] 账号已登录
- [ ] 项目已创建
- [ ] GitHub仓库已连接
- [ ] 环境变量已配置
- [ ] 持久化存储已设置

### 服务运行
- [ ] 服务已部署
- [ ] 日志正常输出
- [ ] Telegram通知正常
- [ ] 基础信号正常记录
- [ ] V4.1交易系统正常

## 🎉 部署完成

部署成功后，你会：
1. ✅ 在Zeabur看到运行中的服务
2. ✅ 收到Telegram启动通知
3. ✅ 每小时记录基础物理信号
4. ✅ V4.1 Smart Ape系统正常运行

---

**准备部署？开始第一步！🚀**

**仓库地址**: https://github.com/iammadma-cryinggun/btc_4hour_alert
