# V4.1.1 Zeabur 部署指南

## 🚀 Zeabur 平台部署

Zeabur是一个现代化的云平台，支持一键部署Python应用。

### 部署前准备

#### 1. 注册Zeabur账号
- 访问：https://zeabur.com
- 注册并登录
- 连接GitHub账号（推荐）

#### 2. 准备GitHub仓库
将V4.1.1文件推送到GitHub仓库：

```bash
# 创建本地仓库
cd V4.1.1云端部署文件
git init
git add .
git commit -m "V4.1.1 双信号版 - 初始部署"

# 推送到GitHub
# 替换为你的仓库地址
git remote add origin https://github.com/你的用户名/btc-physics-v411.git
git branch -M main
git push -u origin main
```

#### 3. 准备必需文件
确保仓库包含：
- ✅ `BTC4小时策略预警v4.1.1_双信号版.py`
- ✅ `requirements_v411.txt`
- ✅ `Dockerfile`（见下方）
- ✅ `.zeabur.yml`（见下方）
- ✅ `dxy_data.csv`

### 创建Dockerfile

在仓库根目录创建 `Dockerfile`：

```dockerfile
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements_v411.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements_v411.txt

# 复制主程序
COPY BTC4小时策略预警v4.1.1_双信号版.py .
COPY dxy_data.csv .

# 创建数据目录
RUN mkdir -p /app/data

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

# 运行程序
CMD ["python", "BTC4小时策略预警v4.1.1_双信号版.py"]
```

### 创建Zeabur配置

在仓库根目录创建 `.zeabur.yml`：

```yaml
# Zeabur部署配置
version: 1

services:
  - name: btc-physics-v411
    type: worker
    runtime: docker
    dockerContext: .
    dockerfilePath: ./Dockerfile
    env:
      - KEY=VALUE
    resources:
      cpu: 0.5
      memory: 512
    ports:
      - port: 80
        protocol: TCP
```

### Zeabur部署步骤

#### 步骤1: 创建新项目
1. 登录Zeabur控制台
2. 点击"Create New Project"
3. 选择"Deploy from GitHub"
4. 选择你的仓库：`btc-physics-v411`

#### 步骤2: 配置服务
1. **服务类型**: Worker（长时间运行的任务）
2. **容器规格**:
   - CPU: 0.5核
   - 内存: 512MB
   - 存储: 1GB
3. **环境变量**（可选）:
   - `TZ`: `Asia/Shanghai`
   - `PYTHONUNBUFFERED`: `1`

#### 步骤3: 配置持久化存储
Zeabur需要配置持久化存储来保存：
- `basic_physics_signals.json`
- `trade_history.json`
- `position_tracker_aligned_status.json`
- `battle_aligned_status.json`
- `physics_alert_v3_1_complete.log`

在Zeabur控制台：
1. 进入服务设置
2. 选择"Volumes"
3. 添加挂载点：`/app/data`

修改Dockerfile：
```dockerfile
# 在复制文件后添加
VOLUME ["/app/data"]

# 修改程序中的文件路径，使用 /app/data/ 目录
```

#### 步骤4: 部署
点击"Deploy"按钮，等待部署完成。

### 步骤5: 查看日志
部署后，在Zeabur控制台查看实时日志：
1. 进入服务详情
2. 点击"Logs"标签
3. 查看程序输出

### 更新Dockerfile以支持持久化

```dockerfile
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 复制依赖文件
COPY requirements_v411.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements_v411.txt

# 复制主程序
COPY BTC4小时策略预警v4.1.1_双信号版.py .
COPY dxy_data.csv .

# 创建数据目录
RUN mkdir -p /app/data

# 设置权限
RUN chmod +x BTC4小时策略预警v4.1.1_双信号版.py

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import sys; sys.exit(0)" || exit 1

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 运行程序
CMD ["python", "BTC4小时策略预警v4.1.1_双信号版.py"]
```

### 环境变量配置

在Zeabur控制台添加环境变量：

```bash
# Telegram配置
TELEGRAM_TOKEN=8189663571:AAEvIUEBTfF_MfyKc7rWq5gQvgi4gAxZJrA
TELEGRAM_CHAT_ID=838429342

# 代理配置（可选）
PROXY_ENABLED=false
PROXY_HOST=
PROXY_PORT=

# 日志级别
LOG_LEVEL=INFO
```

### 修改程序以支持环境变量

在主程序中添加环境变量读取：

```python
import os

# 在PhysicsSignalConfigV4_1类的__init__方法中
self.telegram_token = os.getenv('TELEGRAM_TOKEN', "8189663571:AAEvIUEBTfF_MfyKc7rWq5gQvgi4gAxZJrA")
self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', "838429342")
self.proxy_enabled = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
self.proxy_host = os.getenv('PROXY_HOST', '127.0.0.1')
self.proxy_port = os.getenv('PROXY_PORT', '15236')
```

### GitHub Actions自动部署

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
      - uses: actions/checkout@v3

      - name: Deploy to Zeabur
        uses: zeabur/checkout-action@v1
        with:
          deploy_key: ${{ secrets.ZEABUR_DEPLOY_KEY }}
          service_id: ${{ secrets.ZEABUR_SERVICE_ID }}
```

### 监控和维护

#### 查看实时日志
```bash
# 通过Zeabur CLI
zeabur logs btc-physics-v411

# 或在Web控制台查看
```

#### 重启服务
在Zeabur控制台：
1. 进入服务详情
2. 点击"Restart"按钮

#### 查看资源使用
- CPU使用率
- 内存使用
- 网络流量
- 存储空间

### 成本估算

Zeabur定价（参考）：
- **免费套餐**:
  - 512MB内存
  - 0.5核CPU
  - 1GB存储
- **付费套餐**:
  - 按实际使用计费
  - 约$5-10/月（轻度使用）

### 备份策略

Zeabur自动备份：
1. **代码备份**: GitHub仓库
2. **数据备份**: 定期导出持久化存储
3. **日志备份**: 导出到本地或S3

导出数据：
```bash
# 使用Zeabur CLI
zeabur volumes download btc-physics-v411 /app/data
```

### 故障排查

#### 问题1: 服务无法启动
**检查**:
- Dockerfile是否正确
- requirements_v411.txt是否完整
- dxy_data.csv是否存在

**解决**:
```bash
# 查看构建日志
zeabur logs btc-physics-v411

# 本地测试Docker镜像
docker build -t test-v411 .
docker run -it test-v411
```

#### 问题2: 程序运行异常
**检查**:
- 日志输出
- 环境变量是否正确
- 网络连接是否正常

**解决**:
```bash
# 查看实时日志
zeabur logs btc-physics-v411 --follow

# 重启服务
zeabur restart btc-physics-v411
```

#### 问题3: 数据丢失
**检查**:
- 持久化存储是否挂载
- 文件路径是否正确

**解决**:
- 确保使用 `/app/data/` 目录存储数据
- 定期备份到本地

### 优化建议

#### 1. 资源优化
- 根据实际使用调整CPU和内存
- 使用Profiling找出性能瓶颈

#### 2. 网络优化
- 配置CDN加速（如有需要）
- 使用连接池减少API调用延迟

#### 3. 日志优化
- 设置日志轮转
- 定期清理旧日志
- 使用结构化日志

### 部署清单

- [ ] GitHub仓库已创建
- [ ] 代码已推送到GitHub
- [ ] Dockerfile已创建
- [ ] .zeabur.yml已创建
- [ ] dxy_data.csv已包含
- [ ] Zeabur项目已创建
- [ ] 环境变量已配置
- [ ] 持久化存储已设置
- [ ] 服务已部署
- [ ] 日志正常输出
- [ ] Telegram通知正常

---

**Zeabur部署完成！🚀**

**下一步**: 监控服务运行状态，定期检查日志和备份。
