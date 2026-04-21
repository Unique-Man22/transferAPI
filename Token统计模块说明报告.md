# Token统计模块说明报告

## 模块概述
TokenStatistics模块是DouBao Transfer API的核心组件之一，负责中转前后的Token统计及损耗计算。它支持将Anthropic Claude格式与OpenAI兼容格式之间的Token转换统计，并提供详细的日志记录。

## 核心功能
1. **分词器管理**：
   - 使用tiktoken的cl100k_base编码作为统一分词器（Claude和豆包共用）
   - 提供降级方案：当tiktoken未安装时，使用字符估算（中文1字符=1token，英文4字符=1token）

2. **内容提取**：
   - 从Claude格式请求/响应中提取核心对话内容（包括system prompt、messages、工具调用）
   - 从OpenAI格式请求/响应中提取核心对话内容（包括messages、多模态文本、工具调用）

3. **Token统计**：
   - 统计中转前（Claude端）的输入/输出Token
   - 统计中转后（豆包端）的输入/输出Token
   - 计算Token损耗（中转前后的差异）

4. **日志记录**：
   - 详细记录Token统计信息，包括中转前后的Token数量及损耗

## 使用方式
通过全局单例模式获取实例：
```python
from token_stats import get_token_stats
token_stats = get_token_stats()
```

调用calculate_stats方法获取统计结果：
```python
stats = token_stats.calculate_stats(
    claude_request=claude_req,
    claude_response=claude_res,
    openai_request=openai_req,
    openai_response=openai_res
)
```

## 关键实现细节
- **多模态支持**：处理包含文本和工具调用的多模态内容
- **鲁棒性**：所有分词操作均有异常处理，确保系统稳定运行
- **性能优化**：使用单例模式避免重复初始化分词器