# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 项目AI编程规范
- 全程使用**中文**回复、中文注释、中文讲解

# 项目概述
DouBao Transfer API 是一个 Flask 中转服务，用于将 Anthropic Claude API 请求格式转换为 OpenAI 兼容格式，主要用于连接火山方舟（Volcengine）的豆包大模型。

## 核心功能
- API 格式转换：将 Anthropic Claude API 格式转换为 OpenAI 格式
- 工具调用支持：支持 Function calling（工具调用）功能
- 认证保护：本地 API Key 认证机制
- 日志记录：详细的请求/响应日志记录
- 健康检查：提供 `/health` 健康检查端点

# 开发命令

## 环境设置
```bash
# 安装依赖
pip install -r requirements.txt

# 安装可选依赖（CORS和速率限制）
pip install flask-cors flask-limiter
```

## 运行服务
```bash
# 开发模式（默认端口5187）
python main.py

# 指定端口运行
SERVER_PORT=8080 python main.py

# 生产环境运行
ENV=production python main.py
```

## 测试API
```bash
# 健康检查
curl http://127.0.0.1:5187/health

# 测试消息API（使用默认密钥）
curl -X POST http://127.0.0.1:5187/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-random-key-123456" \
  -d '{
    "model": "claude-3-5-sonnet-20240620",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "你好"}]
  }'

# 测试工具调用
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

## 调试和监控
```bash
# 查看实时日志（服务运行时）
# 日志输出到控制台，包含时间戳、级别、文件名和行号

# 启用调试日志
ENV=development python main.py

# 查看请求统计（需要安装flask-limiter）
# 速率限制信息会在日志中显示
```

# 代码架构

## 整体架构
这是一个单文件Flask应用，采用请求-响应转换模式：
1. 接收Anthropic格式的HTTP请求
2. 转换为OpenAI格式
3. 转发到火山方舟API
4. 将响应转换回Anthropic格式
5. 返回给客户端

## 核心转换逻辑
- **消息格式转换**: `anthropic_to_openai()` 函数处理 `/v1/messages` 端点
- **工具调用转换**: 支持双向工具调用格式转换（Anthropic ↔ OpenAI）
- **系统提示处理**: `convert_system_prompt()` 函数统一系统消息格式
- **内容提取**: `extract_text_from_content()` 函数从复杂内容结构中提取文本

## 关键函数
- `extract_text_from_content(content)`: 从Anthropic内容块中提取纯文本
- `convert_system_prompt(system)`: 转换系统提示为字符串格式
- `validate_message(msg)`: 验证消息格式
- `validate_tools(tools)`: 验证工具定义格式
- `is_safe_json(data)`: JSON安全验证

## 请求处理流程
1. **认证校验** → 验证本地API密钥
2. **请求解析** → 解析JSON请求体
3. **输入验证** → 验证消息和工具格式
4. **格式转换** → Anthropic → OpenAI
5. **API调用** → 转发到火山方舟
6. **响应转换** → OpenAI → Anthropic
7. **错误处理** → 统一错误响应格式

# 环境配置

## 必需配置
在项目根目录创建 `.env` 文件：

```bash
# 火山方舟 API 配置
VOLC_API_KEY=your-volc-api-key-here
VOLC_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

# 模型选择（三选一）
VOLC_MODEL=doubao-seed-2-0-code-preview-260215
# VOLC_MODEL=doubao-seed-1-6-251015
# VOLC_MODEL=deepseek-v3-2-251201

# 本地服务配置
LOCAL_API_KEY=my-random-key-123456
SERVER_HOST=127.0.0.1
SERVER_PORT=5187

# 安全配置
RATE_LIMIT=100 per minute
ENV=development
```

## 配置项说明
| 配置项 | 说明 | 默认值 | 必需 |
|--------|------|--------|------|
| VOLC_API_KEY | 火山方舟API密钥 | 无 | 是 |
| VOLC_BASE_URL | 火山方舟API地址 | https://ark.cn-beijing.volces.com/api/v3 | 是 |
| VOLC_MODEL | 使用的模型 | doubao-seed-2-0-code-preview-260215 | 是 |
| LOCAL_API_KEY | 本地服务认证密钥 | my-random-key-123456 | 是 |
| SERVER_HOST | 服务监听地址 | 127.0.0.1 | 否 |
| SERVER_PORT | 服务监听端口 | 5187 | 否 |
| RATE_LIMIT | 请求频率限制 | 100 per minute | 否 |
| ENV | 环境类型 | development | 否 |

# 编码规范
1. **语言规范**：代码注释、文档、日志均使用中文
2. **命名规范**：
   - 变量/函数：蛇形命名法（snake_case）
   - 类：帕斯卡命名法（PascalCase）
   - 常量：全大写+下划线（UPPER_CASE_WITH_UNDERSCORES）
3. **格式规范**：使用4个空格缩进，每行代码不超过120字符
4. **错误处理**：使用try-except捕获异常，记录详细日志
5. **输入验证**：所有外部输入必须经过验证

# 故障排除

## 常见问题

### 1. 服务启动失败
```bash
# 检查端口是否被占用
netstat -ano | findstr :5187

# 检查Python依赖
pip list | grep flask
```

### 2. API调用返回401错误
```bash
# 检查本地API密钥
echo $LOCAL_API_KEY

# 检查请求头
curl -v -H "Authorization: Bearer your-key" ...
```

### 3. 火山方舟API连接失败
```bash
# 检查网络连接
curl -I https://ark.cn-beijing.volces.com/api/v3

# 检查API密钥权限
# 确保火山方舟API密钥有效且未过期
```

### 4. 工具调用不工作
```bash
# 检查工具定义格式
# 确保tools字段符合Anthropic格式规范

# 检查日志中的转换过程
# 查看openai_tools和openai_messages的转换结果
```

### 5. 内存使用过高
```bash
# 检查最大请求体大小配置
# MAX_CONTENT_LENGTH = 10 * 1024 * 1024 (10MB)

# 限制消息数量
# if len(messages) > 100: 返回错误
```

## 日志级别
- **DEBUG**: 开发环境，显示详细转换过程
- **INFO**: 生产环境，显示关键操作和错误
- **WARNING**: 认证失败、输入验证失败
- **ERROR**: API调用失败、格式转换错误

# 扩展功能

## 可选依赖
```bash
# CORS支持（跨域请求）
pip install flask-cors

# 速率限制
pip install flask-limiter
```

安装后功能自动启用，无需代码修改。

## 模型切换
在 `.env` 文件中修改 `VOLC_MODEL`：
- `doubao-seed-2-0-code-preview-260215`（默认）
- `doubao-seed-1-6-251015`
- `deepseek-v3-2-251201`

## 性能优化
- 请求超时设置：连接10秒，读取300秒
- 消息数量限制：最多100条消息
- 请求体大小限制：10MB

# 维护说明

## 代码结构
- [main.py](main.py): 主要应用程序（300+行）
- [requirements.txt](requirements.txt): Python依赖
- [.env](.env): 环境变量配置
- [README.md](README.md): 项目文档

## 修改建议
1. **添加新功能时**：遵循现有模式，添加输入验证和错误处理
2. **修改转换逻辑时**：确保双向转换的一致性
3. **调整配置时**：更新 `.env` 文件和配置说明
4. **处理敏感信息时**：使用环境变量，不硬编码密钥

## 测试建议
- 使用curl测试基本功能
- 测试工具调用场景
- 验证错误处理逻辑
- 检查日志输出格式

# 支持的模型
当前配置使用火山方舟的豆包模型：
- `doubao-seed-2-0-code-preview-260215`（默认）
- `doubao-seed-1-6-251015`
- `deepseek-v3-2-251201`

# 维护者信息
- 维护者：[你的名字]
- 联系方式：[你的邮箱/微信]