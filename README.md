# Anthropic to OpenAI API 中转服务

这是一个将 Anthropic Claude API 请求格式转换为 OpenAI 兼容格式的 Flask 中转服务，主要用于连接火山方舟（Volcengine）的豆包大模型。

## 功能特性

- **API 格式转换**：将 Anthropic Claude API 格式转换为 OpenAI 格式
- **工具调用支持**：支持 Function calling（工具调用）功能
- **认证保护**：本地 API Key 认证机制
- **日志记录**：详细的请求/响应日志记录
- **健康检查**：提供 `/health` 健康检查端点

## 配置说明

### 方式一：环境变量配置（推荐）

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
# 编辑 .env 文件
```

### 方式二：直接修改代码

在 `main.py` 文件顶部的配置区域修改默认值（不推荐用于生产环境）。

### 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| VOLC_API_KEY | 火山方舟 API 密钥 | （必填） |
| VOLC_BASE_URL | 火山方舟 API 地址 | https://ark.cn-beijing.volces.com/api/v3 |
| VOLC_MODEL | 使用的模型 | doubao-seed-2-0-code-preview-260215 |
| LOCAL_API_KEY | 本地服务认证密钥 | my-random-key-123456 |
| SERVER_HOST | 服务监听地址 | 127.0.0.1 |
| SERVER_PORT | 服务监听端口 | 5187 |
| RATE_LIMIT | 请求频率限制 | 100 per minute |
| ENV | 环境类型（development/production） | development |

### 可选功能

- **CORS 支持**：安装 `flask-cors` 后自动启用
- **速率限制**：安装 `flask-limiter` 后自动启用

```bash
pip install flask-cors flask-limiter
```

## 代码结构详解

### 1. 导入和配置 (第 1-21 行)

导入必要的 Flask、requests、日志等库，并配置火山方舟 API 密钥、模型、本地服务端口等参数。

### 2. 日志配置 (第 23-41 行)

`setup_logging()` 函数配置日志系统，当前仅输出到控制台，包含时间戳、日志级别、文件名和行号等信息。

### 3. 工具函数

#### `extract_text_from_content(content)` (第 44-64 行)
从 Anthropic 格式的 content 列表中提取纯文本，支持：
- 普通字符串
- 文本块（`{"type": "text"}`）
- 工具结果块（`{"type": "tool_result"}`）

#### `convert_system_prompt(system)` (第 67-78 行)
将 system prompt 转换为字符串格式，支持字符串和列表两种输入格式。

### 4. 主要 API 端点 (第 81-277 行)

`/v1/messages` 端点处理 Anthropic 格式的请求并返回 Anthropic 格式的响应：

#### 请求处理流程：

1. **认证校验** (第 86-90 行)：验证 `Authorization` 头部中的本地 API Key
2. **请求解析** (第 92-107 行)：解析 JSON 请求体，提取参数
3. **工具定义转换** (第 109-133 行)：将 Anthropic 工具格式转换为 OpenAI 格式
4. **消息历史转换** (第 135-191 行)：
   - 添加 system message
   - 处理 assistant 的 tool_use 消息
   - 处理 user 的 tool_result 消息
   - 转换普通文本消息
5. **调用火山方舟 API** (第 193-269 行)：
   - 构造 OpenAI 格式请求
   - 发送 POST 请求到火山方舟
   - 处理响应并转换回 Anthropic 格式
6. **错误处理** (第 271-276 行)：捕获网络异常和响应格式错误

### 5. 健康检查端点 (第 280-282 行)

`/health` 端点提供服务健康状态检查。

### 6. 服务启动 (第 285-298 行)

在 `__main__` 中启动 Flask 服务，打印启动信息和使用说明。

## 使用方法

### 启动服务

```bash
python main.py
```

服务将在 `http://127.0.0.1:5187` 启动。

### API 调用示例

使用 Anthropic 客户端风格调用：

```bash
curl -X POST http://127.0.0.1:5187/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-random-key-123456" \
  -d '{
    "model": "claude-3-5-sonnet-20240620",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 健康检查

```bash
curl http://127.0.0.1:5187/health
```

## 支持的模型

当前配置使用火山方舟的豆包模型：
- `doubao-seed-2-0-code-preview-260215`（默认）
- `doubao-seed-1-6-251015`
- `deepseek-v3-2-251201`

可在配置区域切换注释来选择不同模型。
