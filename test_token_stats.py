"""
Token统计模块测试脚本
"""
import json
from token_stats import get_token_stats


def test_basic_text():
    """测试基础文本Token统计"""
    print("=" * 60)
    print("测试1: 基础文本Token统计")
    print("=" * 60)

    token_stats = get_token_stats()

    # 模拟Claude格式请求
    claude_request = {
        "model": "claude-3-5-sonnet-20240620",
        "max_tokens": 4096,
        "system": "你是一个有用的助手。",
        "messages": [
            {"role": "user", "content": "你好，请介绍一下你自己。"}
        ]
    }

    # 模拟Claude格式响应
    claude_response = {
        "id": "msg-123",
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "text", "text": "你好！我是Claude，一个由Anthropic开发的AI助手。"}
        ],
        "model": "DouBao",
        "stop_reason": "stop",
        "usage": {
            "input_tokens": 50,
            "output_tokens": 30,
            "total_tokens": 80
        }
    }

    # 模拟OpenAI格式请求
    openai_request = {
        "model": "doubao-pro",
        "messages": [
            {"role": "system", "content": "你是一个有用的助手。"},
            {"role": "user", "content": "你好，请介绍一下你自己。"}
        ],
        "temperature": 0.7,
        "max_tokens": 4096
    }

    # 模拟OpenAI格式响应
    openai_response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "doubao-pro",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "你好！我是Claude，一个由Anthropic开发的AI助手。"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 55,
            "completion_tokens": 35,
            "total_tokens": 90
        }
    }

    # 计算统计
    stats = token_stats.calculate_stats(
        claude_request=claude_request,
        claude_response=claude_response,
        openai_request=openai_request,
        openai_response=openai_response
    )

    print("\n统计结果:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print()


def test_tool_calling():
    """测试工具调用Token统计"""
    print("=" * 60)
    print("测试2: 工具调用Token统计")
    print("=" * 60)

    token_stats = get_token_stats()

    # 模拟Claude格式请求（带工具定义）
    claude_request = {
        "model": "claude-3-5-sonnet-20240620",
        "max_tokens": 4096,
        "messages": [
            {"role": "user", "content": "今天北京天气怎么样？"}
        ],
        "tools": [
            {
                "name": "get_weather",
                "description": "获取指定城市的天气信息",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "城市名称"}
                    },
                    "required": ["city"]
                }
            }
        ]
    }

    # 模拟Claude格式响应（工具调用）
    claude_response = {
        "id": "msg-456",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_123",
                "name": "get_weather",
                "input": {"city": "北京"}
            }
        ],
        "model": "DouBao",
        "stop_reason": "tool_use",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120
        }
    }

    # 模拟OpenAI格式请求
    openai_request = {
        "model": "doubao-pro",
        "messages": [
            {"role": "user", "content": "今天北京天气怎么样？"}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "获取指定城市的天气信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "城市名称"}
                        },
                        "required": ["city"]
                    }
                }
            }
        ],
        "temperature": 0.7,
        "max_tokens": 4096
    }

    # 模拟OpenAI格式响应（工具调用）
    openai_response = {
        "id": "chatcmpl-456",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "doubao-pro",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"city": "北京"}'
                            }
                        }
                    ]
                },
                "finish_reason": "tool_calls"
            }
        ],
        "usage": {
            "prompt_tokens": 110,
            "completion_tokens": 25,
            "total_tokens": 135
        }
    }

    # 计算统计
    stats = token_stats.calculate_stats(
        claude_request=claude_request,
        claude_response=claude_response,
        openai_request=openai_request,
        openai_response=openai_response
    )

    print("\n统计结果:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print()


def test_multi_turn_conversation():
    """测试多轮对话Token统计"""
    print("=" * 60)
    print("测试3: 多轮对话Token统计")
    print("=" * 60)

    token_stats = get_token_stats()

    # 模拟Claude格式请求（多轮对话）
    claude_request = {
        "model": "claude-3-5-sonnet-20240620",
        "max_tokens": 4096,
        "messages": [
            {"role": "user", "content": "什么是Python？"},
            {"role": "assistant", "content": "Python是一种高级编程语言。"},
            {"role": "user", "content": "它有什么特点？"}
        ]
    }

    # 模拟Claude格式响应
    claude_response = {
        "id": "msg-789",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": "Python的主要特点包括：\n1. 简单易学\n2. 开源免费\n3. 丰富的库支持\n4. 跨平台\n5. 面向对象"
            }
        ],
        "model": "DouBao",
        "stop_reason": "stop",
        "usage": {
            "input_tokens": 80,
            "output_tokens": 60,
            "total_tokens": 140
        }
    }

    # 模拟OpenAI格式请求
    openai_request = {
        "model": "doubao-pro",
        "messages": [
            {"role": "user", "content": "什么是Python？"},
            {"role": "assistant", "content": "Python是一种高级编程语言。"},
            {"role": "user", "content": "它有什么特点？"}
        ],
        "temperature": 0.7,
        "max_tokens": 4096
    }

    # 模拟OpenAI格式响应
    openai_response = {
        "id": "chatcmpl-789",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "doubao-pro",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Python的主要特点包括：\n1. 简单易学\n2. 开源免费\n3. 丰富的库支持\n4. 跨平台\n5. 面向对象"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 85,
            "completion_tokens": 65,
            "total_tokens": 150
        }
    }

    # 计算统计
    stats = token_stats.calculate_stats(
        claude_request=claude_request,
        claude_response=claude_response,
        openai_request=openai_request,
        openai_response=openai_response
    )

    print("\n统计结果:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Token统计模块测试")
    print("=" * 60 + "\n")

    try:
        test_basic_text()
        test_tool_calling()
        test_multi_turn_conversation()

        print("=" * 60)
        print("所有测试完成！")
        print("=" * 60)
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
