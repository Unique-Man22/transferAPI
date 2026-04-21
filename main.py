from flask import Flask, request, jsonify
import requests
import logging
import json
import uuid
import os
from dotenv import load_dotenv
load_dotenv()

# 导入定时任务相关模块
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

# 导入Token统计模块
from token_stats import get_token_stats

# 可选依赖的条件导入
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    RATE_LIMIT_AVAILABLE = True
except ImportError:
    RATE_LIMIT_AVAILABLE = False

VOLC_API_KEY = os.environ.get("VOLC_API_KEY")
VOLC_BASE_URL = os.environ.get("VOLC_BASE_URL")
VOLC_MODEL = os.environ.get("VOLC_MODEL")


LOCAL_API_KEY = os.environ.get("LOCAL_API_KEY")
SERVER_HOST = os.environ.get("SERVER_HOST")
SERVER_PORT = int(os.environ.get("SERVER_PORT"))




# 请求限制配置
RATE_LIMIT = os.environ.get("RATE_LIMIT", "100 per minute")

# 最大请求体大小 (10MB)
MAX_CONTENT_LENGTH = 10 * 1024 * 1024

# 请求超时设置 (连接超时10秒, 读取超时300秒)
REQUEST_TIMEOUT = (10, 300)


# ====================================================

# ===================== 输入验证函数 ======================
def validate_message(msg):
    """验证单条消息的格式"""
    if not isinstance(msg, dict):
        return False
    if msg.get("role") not in ["user", "assistant"]:
        return False
    return True

def validate_tools(tools):
    """验证工具定义的格式"""
    if not isinstance(tools, list):
        return False
    for t in tools:
        if not isinstance(t, dict):
            return False
        if not t.get("name"):
            return False
    return True

def is_safe_json(data):
    """简单的安全检查，防止恶意输入"""
    try:
        # 序列化和反序列化来验证
        json.dumps(data)
        return True
    except (TypeError, ValueError):
        return False

# ===================== 日志配置 ======================
def setup_logging():
    log_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    console_handler.setLevel(logging.INFO)

    # 生产环境使用 INFO 级别
    log_level = logging.INFO if os.environ.get("ENV") == "production" else logging.DEBUG
    logging.getLogger().setLevel(log_level)
    logging.getLogger().addHandler(console_handler)


setup_logging()
logger = logging.getLogger(__name__)
app = Flask(__name__)

# 配置最大请求体大小
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 初始化可选的 CORS
if CORS_AVAILABLE:
    CORS(app)
    logger.info("CORS 已启用")
else:
    logger.warning("flask_cors 未安装，CORS 未启用")

# 初始化可选的速率限制
limiter = None
if RATE_LIMIT_AVAILABLE:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[RATE_LIMIT],
        storage_uri="memory://"
    )
    logger.info(f"速率限制已启用: {RATE_LIMIT}")
else:
    logger.warning("flask_limiter 未安装，速率限制未启用")


def extract_text_from_content(content):
    """从Anthropic格式的content列表中提取纯文本"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif block.get("type") == "tool_result":
                    # 工具结果也转换为文本
                    res = block.get("content", "")
                    if isinstance(res, list):
                        for sub in res:
                            if isinstance(sub, dict) and sub.get("type") == "text":
                                texts.append(sub.get("text", ""))
                    elif isinstance(res, str):
                        texts.append(res)
        return "\n".join(texts)
    return str(content)


def convert_system_prompt(system):
    """转换system prompt为字符串"""
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        texts = []
        for block in system:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
        return "\n".join(texts)
    return str(system)


@app.route('/v1/messages', methods=['POST'])
def anthropic_to_openai():
    logger.info(f"收到新请求 | IP: {request.remote_addr} | 请求方法: {request.method}")
    logger.debug(f"原始请求头: {dict(request.headers)}")

    # 1. 校验本地密钥
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {LOCAL_API_KEY}":
        logger.warning(f"认证失败 | IP: {request.remote_addr}")
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.json
        if not data or not is_safe_json(data):
            logger.warning(f"无效的JSON数据 | IP: {request.remote_addr}")
            return jsonify({"error": "Invalid JSON body"}), 400
        logger.debug(f"原始Anthropic格式请求体: {data}")
    except Exception as e:
        logger.error(f"解析请求体失败 | IP: {request.remote_addr} | 错误: {str(e)}")
        return jsonify({"error": "Invalid JSON body"}), 400

    # 2. 输入验证
    messages = data.get("messages", [])
    if not isinstance(messages, list):
        logger.warning(f"无效的messages格式 | IP: {request.remote_addr}")
        return jsonify({"error": "messages must be an array"}), 400

    if len(messages) > 100:  # 限制消息数量
        logger.warning(f"消息数量过多 | IP: {request.remote_addr} | 数量: {len(messages)}")
        return jsonify({"error": "Too many messages"}), 400

    for msg in messages:
        if not validate_message(msg):
            logger.warning(f"无效的消息格式 | IP: {request.remote_addr}")
            return jsonify({"error": "Invalid message format"}), 400

    tools = data.get("tools")
    if tools and not validate_tools(tools):
        logger.warning(f"无效的工具格式 | IP: {request.remote_addr}")
        return jsonify({"error": "Invalid tools format"}), 400

    # 转换system prompt
    system_prompt = convert_system_prompt(data.get("system", ""))
    temperature = data.get("temperature", 0.7)
    max_tokens = data.get("max_tokens", 4096)
    tool_choice = data.get("tool_choice", "auto")
    stream = data.get("stream", False)

    # 验证数值参数
    if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
        temperature = 0.7
    if not isinstance(max_tokens, int) or max_tokens < 1 or max_tokens > 128000:
        max_tokens = 4096

    logger.info(f"请求参数 | 消息数: {len(messages)} | 携带工具: {bool(tools)}")

    # 2. 转换工具定义 (Anthropic -> OpenAI)
    openai_tools = None
    if tools:
        openai_tools = []
        for t in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {})
                }
            })

    # 转换 tool_choice 策略
    openai_tool_choice = "auto"
    if isinstance(tool_choice, dict):
        if tool_choice.get("type") == "tool" and tool_choice.get("name"):
            openai_tool_choice = {"type": "function", "function": {"name": tool_choice["name"]}}
        elif tool_choice.get("type") == "any":
            openai_tool_choice = "auto"
        else:
            openai_tool_choice = tool_choice
    elif tool_choice in ("none", "auto", "required"):
        openai_tool_choice = tool_choice

    # 3. 转换消息历史
    openai_messages = []

    # 添加system message
    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        # 处理tool_use消息（assistant的工具调用请求）
        if role == "assistant" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        openai_messages.append({"role": "assistant", "content": block.get("text", "")})
                    elif block.get("type") == "tool_use":
                        # OpenAI格式的工具调用
                        openai_messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": block.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": json.dumps(block.get("input", {}))
                                }
                            }]
                        })
        # 处理tool_result消息（用户的工具执行结果）
        elif role == "user" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_result":
                        # 转换为OpenAI的tool角色消息
                        res_content = block.get("content", "")
                        if isinstance(res_content, list):
                            res_content = "\n".join(
                                b.get("text", "") for b in res_content
                                if isinstance(b, dict) and b.get("type") == "text"
                            )
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": block.get("tool_use_id", ""),
                            "content": str(res_content)
                        })
                    elif block.get("type") == "text":
                        openai_messages.append({"role": "user", "content": block.get("text", "")})
        else:
            # 普通消息，提取文本内容
            text_content = extract_text_from_content(content)
            if text_content:
                openai_messages.append({"role": role, "content": text_content})

    logger.debug(f"转换后的OpenAI格式消息: {openai_messages}")

    # 4. 构造火山方舟请求体
    volc_url = f"{VOLC_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {VOLC_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": VOLC_MODEL,
        "messages": openai_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream
    }
    if openai_tools:
        payload["tools"] = openai_tools
        payload["tool_choice"] = openai_tool_choice

    logger.info(f"开始请求火山方舟API | URL: {volc_url} | 模型: {VOLC_MODEL} | 流式: {stream}")
    logger.debug(f"火山方舟请求体: {payload}")

    if stream:
        # 处理流式响应
        return handle_stream_response(data, payload, volc_url, headers)
    else:
        # 处理非流式响应
        return handle_non_stream_response(data, payload, volc_url, headers)


def handle_non_stream_response(claude_request: dict, payload: dict, volc_url: str, headers: dict):
    """处理非流式响应"""
    try:
        resp = requests.post(volc_url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        openai_response = resp.json()

        if not openai_response.get("choices") or len(openai_response["choices"]) == 0:
            logger.error("火山方舟响应异常 | choices字段为空")
            return jsonify({"error": "Volc API returned empty choices"}), 500

        choice = openai_response["choices"][0]
        message = choice["message"]
        usage = openai_response.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # 转换响应格式 (OpenAI -> Anthropic)
        content_list = []
        finish_reason = message.get("finish_reason", "stop")

        # 处理工具调用响应
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, TypeError):
                    args = {}
                content_list.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": args
                })
            if finish_reason == "tool_calls":
                finish_reason = "tool_use"
        # 处理纯文本响应
        elif message.get("content"):
            content_list.append({"type": "text", "text": message["content"]})
            if finish_reason == "length":
                finish_reason = "max_tokens"

        claude_response = {
            "id": f"msg-{uuid.uuid4()}",
            "type": "message",
            "role": "assistant",
            "content": content_list,
            "model": "DouBao",
            "stop_reason": finish_reason,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            }
        }

        # Token统计（不影响主流程）
        try:
            token_stats = get_token_stats()
            token_stats.calculate_stats(
                claude_request=claude_request,
                claude_response=claude_response,
                openai_request=payload,
                openai_response=openai_response
            )
        except Exception as e:
            logger.warning(f"Token统计失败: {e}", exc_info=True)

        response_type = 'tool_use' if any(c.get('type') == 'tool_use' for c in content_list) else 'text'
        logger.info(f"请求处理完成 | IP: {request.remote_addr} | 响应类型: {response_type} | 流式: False")
        return jsonify(claude_response)

    except Exception as e:
        logger.error(f"非流式响应处理失败: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


def handle_stream_response(claude_request: dict, payload: dict, volc_url: str, headers: dict):
    """处理流式响应"""
    from flask import Response

    # 在请求上下文中获取客户端IP
    client_ip = request.remote_addr if request else "unknown"

    # 用于收集完整响应以进行Token统计
    full_openai_response = {
        "choices": [{
            "message": {
                "content": "",
                "tool_calls": []
            },
            "finish_reason": None
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0}
    }
    accumulated_text = ""
    current_tool_calls = {}

    def generate():
        nonlocal accumulated_text, current_tool_calls
        try:
            resp = requests.post(volc_url, json=payload, headers=headers, stream=True, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            msg_id = f"msg-{uuid.uuid4()}"
            first_event = True

            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        openai_chunk = json.loads(data)

                        # 提取内容用于统计
                        if openai_chunk.get('choices'):
                            choice = openai_chunk['choices'][0]
                            delta = choice.get('delta', {})

                            # 收集文本内容
                            if 'content' in delta and delta['content']:
                                nonlocal accumulated_text
                                accumulated_text += delta['content']

                            # 收集工具调用
                            if 'tool_calls' in delta:
                                for tc in delta['tool_calls']:
                                    idx = tc.get('index', 0)
                                    if idx not in current_tool_calls:
                                        current_tool_calls[idx] = {
                                            "id": tc.get('id', ''),
                                            "type": "function",
                                            "function": {
                                                "name": "",
                                                "arguments": ""
                                            }
                                        }
                                    if 'id' in tc:
                                        current_tool_calls[idx]['id'] = tc['id']
                                    if 'function' in tc:
                                        if 'name' in tc['function']:
                                            current_tool_calls[idx]['function']['name'] += tc['function']['name']
                                        if 'arguments' in tc['function']:
                                            current_tool_calls[idx]['function']['arguments'] += tc['function']['arguments']

                            # 更新finish_reason
                            if 'finish_reason' in choice and choice['finish_reason']:
                                full_openai_response['choices'][0]['finish_reason'] = choice['finish_reason']

                        # 提取usage（如果有）
                        if 'usage' in openai_chunk and openai_chunk['usage']:
                            full_openai_response['usage'] = openai_chunk['usage']

                        # 转换为Claude流式格式并发送
                        claude_event = convert_openai_chunk_to_claude(openai_chunk, msg_id)
                        if claude_event:
                            if first_event:
                                first_event = False
                            yield f"data: {json.dumps(claude_event, ensure_ascii=False)}\n\n"

                    except json.JSONDecodeError as e:
                        logger.warning(f"解析流式数据失败: {e}")
                        continue

            # 流结束后，构建完整的响应数据用于Token统计
            full_openai_response['choices'][0]['message']['content'] = accumulated_text
            if current_tool_calls:
                full_openai_response['choices'][0]['message']['tool_calls'] = list(current_tool_calls.values())

            # 构建完整的Claude响应用于统计
            claude_response = build_full_claude_response_for_stats(
                msg_id, accumulated_text, current_tool_calls,
                full_openai_response['choices'][0]['finish_reason'],
                full_openai_response['usage']
            )

            # Token统计（不影响主流程）
            try:
                token_stats = get_token_stats()
                token_stats.calculate_stats(
                    claude_request=claude_request,
                    claude_response=claude_response,
                    openai_request=payload,
                    openai_response=full_openai_response
                )
            except Exception as e:
                logger.warning(f"Token统计失败: {e}", exc_info=True)

            logger.info(f"流式请求处理完成 | IP: {client_ip}")

        except Exception as e:
            logger.error(f"流式响应处理失败: {e}", exc_info=True)
            yield f"data: {{\"type\": \"error\", \"message\": \"Stream error\"}}\n\n"

    return Response(generate(), mimetype='text/event-stream')


def convert_openai_chunk_to_claude(openai_chunk: dict, msg_id: str) -> dict:
    """将OpenAI流式chunk转换为Claude格式"""
    if not openai_chunk.get('choices'):
        return None

    choice = openai_chunk['choices'][0]
    delta = choice.get('delta', {})
    finish_reason = choice.get('finish_reason')

    event = {
        "type": "message_delta",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "model": "DouBao"
        },
        "delta": {},
        "usage": None
    }

    # 处理文本内容
    if 'content' in delta and delta['content']:
        event['delta'] = {
            "type": "text_delta",
            "text": delta['content']
        }

    # 处理工具调用
    elif 'tool_calls' in delta:
        for tc in delta['tool_calls']:
            if tc.get('function', {}).get('name'):
                event['delta'] = {
                    "type": "tool_use",
                    "id": tc.get('id', ''),
                    "name": tc['function']['name'],
                    "input": {}
                }
            elif tc.get('function', {}).get('arguments'):
                event['delta'] = {
                    "type": "input_json_delta",
                    "partial_json": tc['function']['arguments']
                }

    # 处理结束
    if finish_reason:
        claude_stop_reason = finish_reason
        if finish_reason == "tool_calls":
            claude_stop_reason = "tool_use"
        elif finish_reason == "length":
            claude_stop_reason = "max_tokens"

        event['delta'] = {"stop_reason": claude_stop_reason}

        # 添加usage（如果有）
        if 'usage' in openai_chunk and openai_chunk['usage']:
            event['usage'] = {
                "input_tokens": openai_chunk['usage'].get('prompt_tokens', 0),
                "output_tokens": openai_chunk['usage'].get('completion_tokens', 0)
            }

    return event


def build_full_claude_response_for_stats(
    msg_id: str,
    text: str,
    tool_calls: dict,
    finish_reason: str,
    usage: dict
) -> dict:
    """构建完整的Claude响应用于Token统计"""
    content_list = []

    if tool_calls:
        for idx in sorted(tool_calls.keys()):
            tc = tool_calls[idx]
            try:
                args = json.loads(tc['function']['arguments'])
            except (json.JSONDecodeError, TypeError):
                args = {}
            content_list.append({
                "type": "tool_use",
                "id": tc['id'],
                "name": tc['function']['name'],
                "input": args
            })
    elif text:
        content_list.append({"type": "text", "text": text})

    claude_stop_reason = finish_reason
    if finish_reason == "tool_calls":
        claude_stop_reason = "tool_use"
    elif finish_reason == "length":
        claude_stop_reason = "max_tokens"

    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "content": content_list,
        "model": "DouBao",
        "stop_reason": claude_stop_reason,
        "usage": {
            "input_tokens": usage.get('prompt_tokens', 0),
            "output_tokens": usage.get('completion_tokens', 0),
            "total_tokens": usage.get('prompt_tokens', 0) + usage.get('completion_tokens', 0)
        }
    }


# 健康检查
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


# Token统计接口
@app.route('/stats', methods=['GET'])
def get_stats():
    """获取Token累积统计信息"""
    token_stats = get_token_stats()
    stats = token_stats.get_accumulated_stats()
    return jsonify({
        "status": "ok",
        "data": stats
    }), 200


@app.route('/stats/log', methods=['GET'])
def log_stats():
    """记录并返回Token累积统计日志"""
    token_stats = get_token_stats()
    token_stats.log_accumulated_stats()
    stats = token_stats.get_accumulated_stats()
    return jsonify({
        "status": "ok",
        "message": "累积统计已记录到日志",
        "data": stats
    }), 200


@app.route('/stats/reset', methods=['POST'])
def reset_stats():
    """重置Token累积统计"""
    token_stats = get_token_stats()
    token_stats.reset_accumulated_stats()
    return jsonify({
        "status": "ok",
        "message": "累积统计已重置"
    }), 200


def setup_scheduler():
    """设置定时任务"""
    scheduler = BackgroundScheduler()
    # 每分钟记录一次累积统计
    scheduler.add_job(
        lambda: get_token_stats().log_accumulated_stats(),
        'interval',
        minutes=1
    )
    scheduler.start()
    logger.info("定时任务已启动，每分钟记录一次累积统计")


if __name__ == '__main__':
    setup_scheduler()
    logger.info("=" * 50)
    logger.info("中转服务启动（已激活Claude内置工具）")
    logger.info(f"地址: http://{SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"伪装模型: claude-3-5-sonnet-20240620")
    logger.info("=" * 50)

    print(f"\n✅ 服务启动成功！支持 read_file 工具")
    print(f"🌍 接口：http://{SERVER_HOST}:{SERVER_PORT}/v1/messages")
    print(f"🔑 Key：{LOCAL_API_KEY}")
    print(f"🤖 伪装：Claude 3.5 Sonnet（激活工具）")
    print(f"📝 日志：仅控制台输出（已移除日志文件）\n")

    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)