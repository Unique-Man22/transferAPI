# Anthropic to OpenAI API 中转服务

这是一个将 Anthropic Claude API 请求格式转换为 OpenAI 兼容格式的 Flask 中转服务，主要用于连接火山方舟（Volcengine）的豆包大模型。

## 功能特性

- **API 格式转换**：将 Anthropic Claude API 格式转换为 OpenAI 格式
- **工具调用支持**：支持 Function calling（工具调用）功能
- **流式响应**：支持流式和非流式两种响应模式
- **Token 统计**：实时统计中转前后的 Token 使用量及损耗
- **定时任务**：自动定期记录累积统计信息
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
- **Token 统计**：安装 `tiktoken` 后自动启用（推荐）

```bash
pip install flask-cors flask-limiter tiktoken apscheduler
```

## 代码结构详解

### 1. 导入和配置 (第 1-50 行)

导入必要的 Flask、requests、日志、定时任务、Token 统计等库，并配置火山方舟 API 密钥、模型、本地服务端口等参数。

### 2. 输入验证函数 (第 55-82 行)

- `validate_message(msg)`: 验证单条消息的格式
- `validate_tools(tools)`: 验证工具定义的格式
- `is_safe_json(data)`: JSON 安全验证

### 3. 日志配置 (第 85-101 行)

`setup_logging()` 函数配置日志系统，当前仅输出到控制台，包含时间戳、日志级别、文件名和行号等信息。

### 4. 工具函数

#### `extract_text_from_content(content)` (第 129-149 行)
从 Anthropic 格式的 content 列表中提取纯文本，支持：
- 普通字符串
- 文本块（`{"type": "text"}`）
- 工具结果块（`{"type": "tool_result"}`）

#### `convert_system_prompt(system)` (第 152-163 行)
将 system prompt 转换为字符串格式，支持字符串和列表两种输入格式。

### 5. 主要 API 端点 (第 166-713 行)

`/v1/messages` 端点处理 Anthropic 格式的请求并返回 Anthropic 格式的响应：

#### 请求处理流程：

1. **认证校验** (第 171-175 行)：验证 `Authorization` 头部中的本地 API Key
2. **请求解析** (第 177-185 行)：解析 JSON 请求体，提取参数
3. **输入验证** (第 187-205 行)：验证消息和工具格式
4. **参数处理** (第 207-218 行)：转换 system prompt、temperature、max_tokens 等参数
5. **工具定义转换** (第 222-246 行)：将 Anthropic 工具格式转换为 OpenAI 格式
6. **消息历史转换** (第 248-302 行)：
   - 添加 system message
   - 处理 assistant 的 tool_use 消息
   - 处理 user 的 tool_result 消息
   - 转换普通文本消息
7. **调用火山方舟 API** (第 306-331 行)：
   - 构造 OpenAI 格式请求
   - 根据 stream 参数选择流式或非流式处理
8. **非流式响应处理** (第 334-408 行)：
   - 处理 OpenAI 格式响应
   - 转换回 Anthropic 格式
   - 调用 Token 统计
9. **流式响应处理** (第 411-643 行)：
   - `handle_stream_response()`: 处理流式响应生成器
   - `convert_openai_chunk_to_claude()`: 转换 OpenAI 流式 chunk 为 Claude 格式
   - `build_full_claude_response_for_stats()`: 构建完整响应用于 Token 统计

### 6. Token 统计 API 端点 (第 652-685 行)

- `GET /stats`: 获取 Token 累积统计信息
- `GET /stats/log`: 记录并返回 Token 累积统计日志
- `POST /stats/reset`: 重置 Token 累积统计

### 7. 健康检查端点 (第 647-649 行)

`/health` 端点提供服务健康状态检查。

### 8. 定时任务 (第 688-698 行)

`setup_scheduler()` 函数设置定时任务，每分钟自动记录一次 Token 累积统计。

### 9. 服务启动 (第 701-715 行)

在 `__main__` 中启动定时任务和 Flask 服务，打印启动信息和使用说明。

## Token 统计模块

项目包含完整的 Token 统计功能，详见 [token_stats.py](token_stats.py)：

### 主要功能

- **双向统计**：同时统计中转前（Claude 端）和中转后（豆包端）的 Token 使用量
- **损耗计算**：自动计算格式转换带来的 Token 损耗
- **累积统计**：记录所有请求的累积统计信息
- **分词器支持**：使用 tiktoken (cl100k_base) 进行准确的 Token 统计
- **降级方案**：未安装 tiktoken 时使用字符估算

### 统计内容

| 类别 | 说明 |
|------|------|
| claude.input_tokens | Claude 格式请求输入 Token 数 |
| claude.output_tokens | Claude 格式响应输出 Token 数 |
| doubao.input_tokens | 豆包格式请求输入 Token 数 |
| doubao.output_tokens | 豆包格式响应输出 Token 数 |
| loss.input_loss | 输入 Token 损耗（豆包 - Claude） |
| loss.output_loss | 输出 Token 损耗（豆包 - Claude） |
| total_requests | 总请求数 |

## 使用方法

### 启动服务

```bash
python main.py
```

服务将在 `http://127.0.0.1:5187` 启动。

### API 调用示例

#### 基础消息请求

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

#### 流式请求

```bash
curl -X POST http://127.0.0.1:5187/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-random-key-123456" \
  -d '{
    "model": "claude-3-5-sonnet-20240620",
    "max_tokens": 1024,
    "stream": true,
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

#### 工具调用请求

```bash
curl -X POST http://127.0.0.1:5187/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-random-key-123456" \
  -d '{
    "model": "claude-3-5-sonnet-20240620",
    "max_tokens": 1024,
    "tools": [{
      "name": "get_weather",
      "description": "获取天气信息",
      "input_schema": {
        "type": "object",
        "properties": {
          "city": {"type": "string", "description": "城市名称"}
        },
        "required": ["city"]
      }
    }],
    "messages": [{"role": "user", "content": "北京天气怎么样？"}]
  }'
```

#### 健康检查

```bash
curl http://127.0.0.1:5187/health
```

#### 获取 Token 统计

```bash
curl http://127.0.0.1:5187/stats
```

#### 记录并获取统计日志

```bash
curl http://127.0.0.1:5187/stats/log
```

#### 重置统计数据

```bash
curl -X POST http://127.0.0.1:5187/stats/reset
```

## 支持的模型

当前配置使用火山方舟的豆包模型：
- `doubao-seed-2-0-code-preview-260215`（默认）
- `doubao-seed-1-6-251015`
- `deepseek-v3-2-251201`

可在配置区域切换注释来选择不同模型。

## 依赖说明

### 核心依赖

- `flask`: Web 框架
- `requests`: HTTP 请求库
- `python-dotenv`: 环境变量管理

### 可选依赖

- `flask-cors`: CORS 跨域支持
- `flask-limiter`: 速率限制
- `tiktoken>=0.5.0`: Token 统计分词器
- `apscheduler`: 定时任务支持

安装完整依赖：

```bash
pip install -r requirements.txt
```
