# Zeabur部署指南

## 🚀 快速部署到Zeabur

### 前置准备

1. **GitHub仓库**：https://github.com/iammadma-codinggun/btc_4hour_alert
2. **Zeabur账户**：注册 https://zeabur.com
3. **Telegram Bot**：需要创建Bot并获取Token和Chat ID

### 部署步骤

#### 1. 连接GitHub仓库

1. 登录Zeabur
2. 点击"New Project"
3. 选择"Deploy from GitHub"
4. 授权并选择 `btc_4hour_alert` 仓库

#### 2. 创建服务

1. 选择服务类型：**Docker**
2. 服务名称：`btc-4hour-alert`（或自定义）
3. 构建路径：根目录 `/`
4. Dockerfile路径：`Dockerfile`

#### 3. 配置环境变量

在Zeabur服务的"Environment Variables"中添加：

```bash
# Telegram配置（必需）
TELEGRAM_TOKEN=你的Bot_Token
TELEGRAM_CHAT_ID=你的Chat_ID

# 交易参数（可选）
LEVERAGE=5
BASE_POSITION=0.30
```

**获取Telegram Token和Chat ID**：

1. **创建Bot**：
   - 在Telegram搜索 @BotFather
   - 发送 `/newbot`
   - 按提示设置Bot名称
   - 保存返回的Token

2. **获取Chat ID**：
   - 在Telegram搜索 @userinfobot
   - 发送任意消息
   - 保存返回的Chat ID

#### 4. 部署

点击"Deploy"按钮，Zeabur将：
1. 从GitHub拉取代码
2. 构建Docker镜像
3. 启动容器

### 验证部署

#### 查看日志

在Zeabur控制台查看日志，应该看到：

```
======================================================================
V7.0 非线性动力学交易系统
======================================================================

正在启动系统...
[OK] 配置初始化成功
[OK] 数据获取器初始化成功
...
```

#### 测试Telegram通知

在Telegram向你的Bot发送任意消息，应该收到系统状态回复：

```
📊 V7.0系统状态
====================

📍 持仓状态: 无持仓
...
```

### 监控和维护

#### 自动重启

- 如果容器崩溃，Zeabur会自动重启
- 系统状态会持久化保存

#### 更新代码

1. 推送新代码到GitHub
2. 在Zeabur点击"Redeploy"
3. 无需停机

#### 查看资源使用

- CPU使用率
- 内存占用
- 网络流量

### 常见问题

#### 1. 容器反复重启

**原因**：缺少Telegram配置

**解决**：
- 检查环境变量是否正确设置
- 查看日志确认错误信息

#### 2. Telegram消息发送失败

**原因**：Token或Chat ID错误

**解决**：
1. 验证Token格式：`数字:字母数字混合`
2. 验证Chat ID：纯数字
3. 确保Bot已添加到对应群组（如果是群组Chat ID）

#### 3. 数据获取失败

**原因**：网络连接问题

**解决**：
- Zeabur默认有网络访问，无需配置代理
- 等待下次重试（每小时自动检查）

### 系统特性

#### ✅ 已实现

- ✅ 信号计算：验证5完整逻辑（FFT+Hilbert+DXY燃料）
- ✅ DXY实时数据：FRED官方API
- ✅ V7.0交易逻辑：T0-T2惯性保护+ATR动态止损
- ✅ Telegram通知：所有交易细节实时推送
- ✅ 状态持久化：容器重启后自动恢复
- ✅ 定时任务：4小时信号检查+1小时仓位检查

#### 📊 性能

- 回测收益：+85.01%
- 最大回撤：-31.8%
- 止盈率：90.2%
- 平均持仓：4.3周期（17.2小时）

### 安全建议

1. **不要泄露Token**：
   - 不要将.env文件提交到Git
   - 使用环境变量而非配置文件

2. **定期监控**：
   - 检查Telegram通知
   - 查看Zeabur日志
   - 监控资源使用

3. **风险控制**：
   - 建议先用小资金测试
   - 设置合理的杠杆倍数
   - 定期检查系统状态

### 技术支持

- GitHub Issues: https://github.com/iammadma-codinggun/btc_4hour_alert/issues
- 文档: README.md, DEPLOYMENT_GUIDE.md

---

**最后更新**: 2026-01-13
**版本**: V7.0 Production
**状态**: ✅ 已部署到Zeabur
