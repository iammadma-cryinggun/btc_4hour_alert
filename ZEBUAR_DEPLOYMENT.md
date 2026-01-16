# V7.0.7 Zeabur部署配置（Webhook模式 + Gunicorn）

## 部署说明

**⭐ 重要更新**: 现在使用Gunicorn生产级服务器，解决Flask开发服务器不稳定的问题。

### ✅ 改进内容

1. ✅ **Gunicorn WSGI服务器**（替代Flask开发服务器）
2. ✅ **多Worker进程**（更好性能）
3. ✅ **自动重启**（崩溃恢复）
4. ✅ **生产级日志**
5. ✅ **无需手动管理进程**

### 1. 环境变量配置

在Zeabur服务配置中添加以下环境变量：

```bash
# 必需环境变量
TELEGRAM_TOKEN=8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk
TELEGRAM_CHAT_ID=838429342

# 可选：Webhook URL（推荐设置）
# 格式: https://your-zeabur-app.zeabur.app
# 系统会自动附加 /{TOKEN} 路径
TELEGRAM_WEBHOOK_URL=https://your-app-name.zeabur.app

# 端口配置（默认8080，Zeabur会自动分配PORT）
PORT=8080
```

### 2. Webhook URL设置

#### 自动设置（推荐）

如果设置了`TELEGRAM_WEBHOOK_URL`环境变量，系统启动时会自动设置webhook。

#### 手动设置（可选）

如果想手动设置webhook，可以通过Telegram API：

```bash
curl -F "url=https://your-app-name.zeabur.app/<YOUR_TOKEN>" \
     https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook
```

示例：
```bash
curl -F "url=https://btc-alert.zeabur.app/8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk" \
     https://api.telegram.org/bot8505180201:AAGOSkhXHRu77OlRMu0PZCbKtYMEr1tRGAk/setWebhook
```

### 3. 验证部署

#### 检查服务健康

访问健康检查端点：
```
https://your-app-name.zeabur.app/health
```

应该返回：`OK`

#### 检查Webhook状态

通过Telegram API查询：
```bash
curl https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo
```

返回示例：
```json
{
  "ok": true,
  "result": {
    "url": "https://your-app-name.zeabur.app/<TOKEN>",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "last_error_date": 0,
    "last_error_message": ""
  }
}
```

#### 测试Telegram命令

发送命令到bot：
```
/start - 启动机器人
/status - 查看系统状态
/config - 查看系统配置
```

### 4. Webhook模式优势

#### vs Polling模式（旧版）

| 特性 | Polling模式 | Webhook模式（新版） |
|------|------------|-------------------|
| Bot实例数量 | 2个（冲突！） | 1个（无冲突） |
| Telegram错误 | ❌ 409 Conflict | ✅ 无错误 |
| 性能 | 轮询（低效） | 事件驱动（高效） |
| 云端友好 | 一般 | ✅ 完美 |
| 资源消耗 | 较高 | 较低 |

### 5. 故障排除

#### 问题：Webhook未设置

**症状**：Telegram命令无响应

**解决**：
1. 检查`TELEGRAM_WEBHOOK_URL`环境变量是否正确
2. 查看日志中是否有"设置Webhook成功"的消息
3. 手动调用`setWebhook` API

#### 问题：409 Conflict仍然存在

**症状**：日志中仍然出现409错误

**解决**：
1. 确认旧版本已停止运行
2. 删除webhook后重新设置：
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/deleteWebhook
   # 等待5秒
   curl -F "url=https://your-app.zeabur.app/<TOKEN>" \
        https://api.telegram.org/bot<TOKEN>/setWebhook
   ```

#### 问题：健康检查失败

**症状**：`/health`端点无法访问

**解决**：
1. 检查Zeabur服务是否正在运行
2. 查看日志中是否有"Flask服务器已启动"的消息
3. 确认端口配置正确（Zeabur会自动设置PORT环境变量）

### 6. 日志检查

正常启动日志应包含：

```
[Telegram] WebHandler TeleBot初始化成功
[Telegram] 消息处理器已注册
[Telegram] Flask服务器已启动（后台线程）
[系统] Flask Webhook服务器已启动（端口 8080）
[Telegram] Webhook设置成功: https://your-app.zeabur.app/<TOKEN>
V7.0.7 智能交易系统启动（Webhook模式）
```

### 7. 回滚到Polling模式

如果Webhook模式出现问题，可以临时回滚：

1. 删除webhook：
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/deleteWebhook
   ```

2. 在Zeabur中切换回旧的commit（02d9d60）

3. 重新部署

但建议优先修复Webhook问题，因为Polling模式有409冲突bug。

---

## 更新日志

### 2026-01-15
- ✅ 实现Webhook模式
- ✅ 解决409 Conflict错误
- ✅ 添加Flask支持
- ✅ 优化bot实例管理

### 2026-01-15 (之前)
- ⚠️ Polling模式（存在409冲突）
- ✅ V7.0.5过滤器集成
- ✅ V7.0.7 ZigZag出场
