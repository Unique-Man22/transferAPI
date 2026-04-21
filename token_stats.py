"""
Token统计模块
负责中转前/中转后的Token统计及损耗计算
"""
import logging
import json
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 尝试导入分词器
# 注意：Anthropic库本身不提供分词器，Claude分词器需要使用tiktoken或其他方式
# 这里我们使用tiktoken作为Claude和豆包的统一分词器
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken库未安装，将使用简单字符估算")


class TokenStatistics:
    """Token统计类"""

    def __init__(self):
        self.claude_tokenizer = None
        self.doubao_tokenizer = None
        self._init_tokenizers()

        # 累积统计
        self.accumulated_stats = {
            "total_requests": 0,
            "claude": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0
            },
            "doubao": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0
            },
            "loss": {
                "input_loss": 0,
                "output_loss": 0,
                "total_loss": 0
            }
        }

    def _init_tokenizers(self):
        """初始化分词器"""
        # 使用tiktoken作为Claude和豆包的统一分词器
        if TIKTOKEN_AVAILABLE:
            try:
                # 使用cl100k_base编码（OpenAI的GPT-4编码，与Claude类似）
                self.claude_tokenizer = tiktoken.get_encoding("cl100k_base")
                self.doubao_tokenizer = tiktoken.get_encoding("cl100k_base")
                logger.info("分词器初始化成功（使用tiktoken cl100k_base）")
            except Exception as e:
                logger.warning(f"分词器初始化失败: {e}")

    def _count_tokens_claude(self, text: str) -> int:
        """使用Claude分词器统计Token"""
        if self.claude_tokenizer:
            try:
                return len(self.claude_tokenizer.encode(text))
            except Exception as e:
                logger.warning(f"Claude分词器统计失败: {e}")
        # 降级方案：按字符估算（中文约1字符=1token，英文约4字符=1token）
        return self._estimate_tokens(text)

    def _count_tokens_doubao(self, text: str) -> int:
        """使用豆包分词器统计Token"""
        if self.doubao_tokenizer:
            try:
                return len(self.doubao_tokenizer.encode(text))
            except Exception as e:
                logger.warning(f"豆包分词器统计失败: {e}")
        # 降级方案：按字符估算
        return self._estimate_tokens(text)

    def _estimate_tokens(self, text: str) -> int:
        """简单估算Token数量"""
        if not text:
            return 0
        # 中文约1字符=1token，英文约4字符=1token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return chinese_chars + (other_chars // 4)

    def _extract_claude_content(self, data: Dict[str, Any], is_input: bool = True) -> str:
        """
        从Claude格式请求/响应中提取核心对话内容
        仅统计对话内容，排除JSON字段名等冗余信息
        """
        texts = []

        if is_input:
            # Claude格式请求
            # 提取system prompt
            if "system" in data:
                system_text = self._convert_to_text(data["system"])
                if system_text:
                    texts.append(system_text)

            # 提取messages
            messages = data.get("messages", [])
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                content_text = self._convert_to_text(content)
                if content_text:
                    texts.append(f"{role}: {content_text}")
        else:
            # Claude格式响应
            content = data.get("content", [])
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        # 工具调用也统计
                        tool_name = block.get("name", "")
                        tool_input = json.dumps(block.get("input", {}), ensure_ascii=False)
                        texts.append(f"tool_use: {tool_name}({tool_input})")

        return "\n".join(texts)

    def _extract_openai_content(self, data: Dict[str, Any], is_input: bool = True) -> str:
        """
        从OpenAI格式请求/响应中提取核心对话内容
        仅统计对话内容，排除JSON字段名等冗余信息
        """
        texts = []

        if is_input:
            # OpenAI格式请求
            messages = data.get("messages", [])
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if content:
                    if isinstance(content, str):
                        texts.append(f"{role}: {content}")
                    elif isinstance(content, list):
                        # 处理多模态内容
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                texts.append(f"{role}: {item.get('text', '')}")
        else:
            # OpenAI格式响应
            choices = data.get("choices", [])
            if choices:
                choice = choices[0]
                message = choice.get("message", {})

                # 文本内容
                content = message.get("content", "")
                if content:
                    texts.append(content)

                # 工具调用
                tool_calls = message.get("tool_calls", [])
                for tc in tool_calls:
                    func = tc.get("function", {})
                    func_name = func.get("name", "")
                    func_args = func.get("arguments", "")
                    texts.append(f"tool_call: {func_name}({func_args})")

        return "\n".join(texts)

    def _convert_to_text(self, content) -> str:
        """将各种格式的content转换为纯文本"""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        res = block.get("content", "")
                        if isinstance(res, list):
                            for sub in res:
                                if isinstance(sub, dict) and sub.get("type") == "text":
                                    texts.append(sub.get("text", ""))
                        elif isinstance(res, str):
                            texts.append(res)
            return "\n".join(texts)
        return str(content) if content else ""

    def calculate_stats(
        self,
        claude_request: Dict[str, Any],
        claude_response: Dict[str, Any],
        openai_request: Dict[str, Any],
        openai_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        计算完整的Token统计信息

        Args:
            claude_request: 原始Claude格式请求
            claude_response: 转换后的Claude格式响应
            openai_request: 转换后的OpenAI格式请求
            openai_response: 原始OpenAI格式响应

        Returns:
            包含所有统计信息的字典
        """
        # 提取核心内容
        claude_input_text = self._extract_claude_content(claude_request, is_input=True)
        claude_output_text = self._extract_claude_content(claude_response, is_input=False)
        openai_input_text = self._extract_openai_content(openai_request, is_input=True)
        openai_output_text = self._extract_openai_content(openai_response, is_input=False)

        # 统计中转前（Claude端）Tokens
        claude_input_tokens = self._count_tokens_claude(claude_input_text)
        claude_output_tokens = self._count_tokens_claude(claude_output_text)
        claude_total_tokens = claude_input_tokens + claude_output_tokens

        # 统计中转后（火山豆包端）Tokens
        doubao_input_tokens = self._count_tokens_doubao(openai_input_text)
        doubao_output_tokens = self._count_tokens_doubao(openai_output_text)
        doubao_total_tokens = doubao_input_tokens + doubao_output_tokens

        # 计算损耗
        input_loss = doubao_input_tokens - claude_input_tokens
        output_loss = doubao_output_tokens - claude_output_tokens
        total_loss = input_loss + output_loss

        # 构建统计结果
        stats = {
            # 中转前（Claude端）
            "claude": {
                "input_tokens": claude_input_tokens,
                "output_tokens": claude_output_tokens,
                "total_tokens": claude_total_tokens
            },
            # 中转后（火山豆包端）
            "doubao": {
                "input_tokens": doubao_input_tokens,
                "output_tokens": doubao_output_tokens,
                "total_tokens": doubao_total_tokens
            },
            # Token损耗
            "loss": {
                "input_loss": input_loss,
                "output_loss": output_loss,
                "total_loss": total_loss
            }
        }

        # 累积统计
        self.accumulated_stats["total_requests"] += 1
        self.accumulated_stats["claude"]["input_tokens"] += claude_input_tokens
        self.accumulated_stats["claude"]["output_tokens"] += claude_output_tokens
        self.accumulated_stats["claude"]["total_tokens"] += claude_total_tokens
        self.accumulated_stats["doubao"]["input_tokens"] += doubao_input_tokens
        self.accumulated_stats["doubao"]["output_tokens"] += doubao_output_tokens
        self.accumulated_stats["doubao"]["total_tokens"] += doubao_total_tokens
        self.accumulated_stats["loss"]["input_loss"] += input_loss
        self.accumulated_stats["loss"]["output_loss"] += output_loss
        self.accumulated_stats["loss"]["total_loss"] += total_loss

        # 记录日志
        self._log_stats(stats)

        return stats

    def _log_stats(self, stats: Dict[str, Any]):
        """记录Token统计日志"""
        logger.info("=" * 60)
        logger.info("Token统计信息")
        logger.info("=" * 60)
        logger.info(f"中转前(Claude) - 输入: {stats['claude']['input_tokens']} tokens, "
                   f"输出: {stats['claude']['output_tokens']} tokens, "
                   f"总计: {stats['claude']['total_tokens']} tokens")
        logger.info(f"中转后(豆包)  - 输入: {stats['doubao']['input_tokens']} tokens, "
                   f"输出: {stats['doubao']['output_tokens']} tokens, "
                   f"总计: {stats['doubao']['total_tokens']} tokens")
        logger.info(f"Token损耗      - 输入: {stats['loss']['input_loss']} tokens, "
                   f"输出: {stats['loss']['output_loss']} tokens, "
                   f"总计: {stats['loss']['total_loss']} tokens")
        logger.info("=" * 60)

    def get_accumulated_stats(self) -> Dict[str, Any]:
        """获取累积统计信息"""
        return self.accumulated_stats.copy()

    def reset_accumulated_stats(self):
        """重置累积统计"""
        self.accumulated_stats = {
            "total_requests": 0,
            "claude": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0
            },
            "doubao": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0
            },
            "loss": {
                "input_loss": 0,
                "output_loss": 0,
                "total_loss": 0
            }
        }
        logger.info("累积统计已重置")

    def log_accumulated_stats(self):
        """记录累积统计日志"""
        logger.info("=" * 60)
        logger.info("累积Token统计信息")
        logger.info("=" * 60)
        logger.info(f"总请求数: {self.accumulated_stats['total_requests']}")
        logger.info(f"Claude端总计 - 输入: {self.accumulated_stats['claude']['input_tokens']} tokens, "
                   f"输出: {self.accumulated_stats['claude']['output_tokens']} tokens, "
                   f"总计: {self.accumulated_stats['claude']['total_tokens']} tokens")
        logger.info(f"豆包端总计  - 输入: {self.accumulated_stats['doubao']['input_tokens']} tokens, "
                   f"输出: {self.accumulated_stats['doubao']['output_tokens']} tokens, "
                   f"总计: {self.accumulated_stats['doubao']['total_tokens']} tokens")
        logger.info(f"总Token损耗  - 输入: {self.accumulated_stats['loss']['input_loss']} tokens, "
                   f"输出: {self.accumulated_stats['loss']['output_loss']} tokens, "
                   f"总计: {self.accumulated_stats['loss']['total_loss']} tokens")
        logger.info("=" * 60)


# 全局单例
_token_stats_instance: Optional[TokenStatistics] = None


def get_token_stats() -> TokenStatistics:
    """获取Token统计单例"""
    global _token_stats_instance
    if _token_stats_instance is None:
        _token_stats_instance = TokenStatistics()
    return _token_stats_instance
