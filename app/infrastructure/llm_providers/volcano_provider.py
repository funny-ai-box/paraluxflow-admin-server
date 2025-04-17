# 需要安装: pip install --upgrade "volcengine-python-sdk[ark]" numpy
import time
import json
import logging
from typing import Dict, Any, List, Optional

# 从 volcenginesdkarkruntime 导入 Ark 客户端和特定异常
from volcenginesdkarkruntime import Ark
from volcenginesdkarkruntime._exceptions import ArkAPIError
import httpx
from openai import OpenAI # 保持用于 Chat Completion (如果API兼容)
import numpy as np # 如果需要进行文档中的 doubao 特殊处理

from app.infrastructure.llm_providers.base import LLMProviderInterface
from app.core.exceptions import APIException
from app.core.status_codes import EXTERNAL_API_ERROR, TIMEOUT, RATE_LIMITED

logger = logging.getLogger(__name__)

class VolcanoProvider(LLMProviderInterface):
    """火山引擎API服务提供商 (包括 Chat 和 Embeddings)"""

    def __init__(self):
        """初始化火山引擎提供商"""
        self.openai_client = None # 用于 Chat Completion (通过 OpenAI 接口形式)
        self.ark_client = None    # 用于 Embeddings (通过 Ark SDK)
        self.default_chat_model = "deepseek-r1-250120" # 默认聊天模型
        self.default_embedding_model = "doubao-embedding-large-text-240915" # 默认向量模型
        self.max_retries = 3
        self.retry_delay = 2  # 初始重试延迟（秒）

    def initialize(self, api_key: str, **kwargs) -> None:
        """初始化火山引擎客户端 (包括 OpenAI 兼容接口和 Ark SDK)

        Args:
            api_key: 火山引擎API密钥 (同时用于两个客户端)
            **kwargs: 其他初始化参数，可包含:
                      - default_chat_model: 默认聊天模型名称
                      - default_embedding_model: 默认向量模型名称
                      - max_retries: 最大重试次数
                      - timeout: 请求超时时间 (用于 OpenAI 客户端)
        """
        print("初始化火山引擎客户端...")
        print(api_key)
        try:
            # 更新可选配置
            self.default_chat_model = kwargs.get("default_model", # 兼容旧参数名
                                                 kwargs.get("default_chat_model", self.default_chat_model))
            self.default_embedding_model = kwargs.get("default_embedding_model", self.default_embedding_model)
            self.max_retries = kwargs.get("max_retries", self.max_retries)

            # --- 初始化 OpenAI 兼容客户端 (用于 Chat) ---
            timeout_seconds = kwargs.get("timeout", 300)
            print(f"设置 OpenAI 客户端超时时间为 {timeout_seconds} 秒")
            print(f"默认聊天模型为 {self.default_chat_model}")
            print(f"API Key: {api_key[:4]}...{api_key[-4:]}") # Mask API key in logs

            # 假设火山引擎的 /api/v3 Chat 接口兼容 OpenAI 格式
            self.openai_client = OpenAI(
                    api_key=api_key,
                    base_url = "https://ark.cn-beijing.volces.com/api/v3",
                    timeout=timeout_seconds,
                    max_retries=0 # 使用自定义的重试逻辑 _execute_with_retry
                )
            print(f"火山引擎 OpenAI 兼容客户端初始化成功 (用于 Chat)")
            logger.info(f"火山引擎 OpenAI 兼容客户端初始化成功. 默认模型: {self.default_chat_model}")

            # --- 初始化 Ark SDK 客户端 (用于 Embeddings) ---
            try:
                self.ark_client = Ark(api_key=api_key)
                # Ark client doesn't seem to have an explicit timeout setting in constructor
                # It might rely on underlying http client's default or env vars
                print(f"火山引擎 Ark SDK 客户端初始化成功 (用于 Embeddings)")
                print(f"默认向量模型为: {self.default_embedding_model}")
                logger.info(f"火山引擎 Ark SDK 客户端初始化成功. 默认向量模型: {self.default_embedding_model}")
            except Exception as e:
                logger.error(f"失败初始化火山引擎 Ark SDK 客户端: {str(e)}")
                # Decide if this is fatal. Let's allow proceeding if Chat client worked.
                self.ark_client = None
                print(f"警告: 火山引擎 Ark SDK 客户端初始化失败，Embeddings 功能将不可用。")


        except Exception as e:
            logger.error(f"失败初始化火山引擎提供商: {str(e)}")
            raise APIException(f"火山引擎初始化失败: {str(e)}", EXTERNAL_API_ERROR)

    def _handle_api_error(self, operation: str, error: Exception) -> None:
        """处理API错误

        Args:
            operation: 操作名称
            error: 捕获的异常

        Raises:
            APIException: 转换后的API异常
        """
        error_msg = f"火山引擎 {operation} 失败: {type(error).__name__} - {str(error)}"
        logger.error(error_msg, exc_info=True) # Log traceback for better debugging

        status_code = EXTERNAL_API_ERROR # Default
        http_status = 500 # Default

        # 优先处理更具体的错误类型
        if isinstance(error, ArkAPIError):
             # ArkAPIError might contain more specific info, e.g., error.code, error.message
             # You might map specific Ark error codes/messages to RATE_LIMITED etc. if known
             # For now, treat it as a general external error unless it clearly indicates rate limiting
             if "rate limit" in str(error).lower(): # Basic check
                 status_code = RATE_LIMITED
                 http_status = 429
             # Add checks for other specific Ark errors if needed
             # else: status_code remains EXTERNAL_API_ERROR
        elif isinstance(error, httpx.TimeoutException) or "timeout" in str(error).lower():
            status_code = TIMEOUT
            http_status = 503
        elif isinstance(error, httpx.ConnectError) or "connection" in str(error).lower():
             status_code = TIMEOUT # Treat connection errors similar to timeout
             http_status = 503
        elif "rate limit" in str(error).lower(): # General rate limit check for non-Ark errors
            status_code = RATE_LIMITED
            http_status = 429
        # Add more specific error checks if the underlying library provides them (e.g., openai.APIError subclasses)

        raise APIException(error_msg, status_code, http_status)

    def _execute_with_retry(self, operation_func, operation_name, *args, **kwargs):
        """使用重试机制执行API操作

        Args:
            operation_func: 要执行的操作函数
            operation_name: 操作名称（用于日志）
            *args, **kwargs: 传递给操作函数的参数 (注意: operation_func 需要能接收它们)
                             或者让 operation_func 访问闭包中的变量. 当前实现使用闭包方式.

        Returns:
            操作结果

        Raises:
            APIException: 当所有重试都失败时
        """
        retry_count = 0
        delay = self.retry_delay

        while retry_count <= self.max_retries:
            try:
                # Execute the function passed (which should handle its own args/kwargs or use closure)
                return operation_func()
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"火山引擎 {operation_name} 在 {self.max_retries + 1} 次尝试后仍然失败 (Timeout/Connection).")
                    self._handle_api_error(operation_name, e) # Let handler raise final APIException

                # 计算指数退避延迟
                wait_time = delay * (2 ** (retry_count - 1))
                logger.warning(f"火山引擎 {operation_name} 失败 (Timeout/Connection)，正在重试 ({retry_count}/{self.max_retries})，等待 {wait_time:.2f} 秒...")
                time.sleep(wait_time)
            # Catch Ark specific errors that might be transient (though less likely than network issues)
            # Example: If ArkAPIError represents a temporary server overload, you *could* retry it.
            # except ArkAPIError as e:
            #    if should_retry_ark_error(e): # Needs a function to check error code/message
            #        # ... retry logic ...
            #    else:
            #        logger.error(f"火山引擎 {operation_name} 发生不可重试的 ArkAPIError: {e}")
            #        self._handle_api_error(operation_name, e)
            except Exception as e:
                # 其他错误 (包括大多数 ArkAPIError, OpenAI client errors) 直接失败，不重试
                logger.error(f"火山引擎 {operation_name} 发生不可重试错误: {e}")
                self._handle_api_error(operation_name, e) # Let handler raise APIException

        # This part should theoretically not be reached if logic is correct,
        # but as a safeguard:
        raise APIException(f"火山引擎 {operation_name} 在所有重试后失败。", EXTERNAL_API_ERROR)


    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 1.0,
        stop_sequences: Optional[List[str]] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成文本 (通过 Chat Completion 实现)

        Args:
            prompt: 提示词
            max_tokens: 最大生成的token数量
            temperature: 温度参数，控制随机性
            top_p: 核采样参数
            stop_sequences: 停止生成的序列
            model: 使用的模型，默认使用初始化时设置的聊天模型
            **kwargs: 其他参数 (传递给 Chat Completion API)

        Returns:
            包含生成文本及元数据的字典
        """
        # 火山引擎推荐使用 Chat API，即使是单轮生成
        logger.info(f"调用 generate_text (内部使用 generate_chat_completion)")
        return self.generate_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_sequences=stop_sequences,
            model=model, # Pass model override if provided
            **kwargs
        )

    # --- NEW METHOD: generate_embeddings ---
    def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        # Add specific args for embeddings if needed, e.g., instruction prefixes
        query_instruction: Optional[str] = None, # For doubao query-type inputs
        **kwargs
    ) -> Dict[str, Any]:
        """生成文本嵌入向量

        Args:
            texts: 需要生成嵌入的文本列表.
            model: 使用的向量模型，默认使用初始化时设置的向量模型.
            query_instruction: (可选) doubao-embedding 模型建议为查询类型文本添加的前缀.
                               如果提供，将加在每个输入文本前。
            **kwargs: 其他参数，例如 'extra_headers' 传递给 Ark SDK.

        Returns:
            包含嵌入向量列表及元数据的字典:
            {
                "embeddings": [[float], [float], ...],
                "model": str,
                "usage": {"prompt_tokens": int, "total_tokens": int}
            }
        """
        if not self.ark_client:
            raise APIException("火山引擎 Ark SDK 客户端未初始化或初始化失败，无法生成 Embeddings。", EXTERNAL_API_ERROR)

        if not texts:
            return {"embeddings": [], "model": model or self.default_embedding_model, "usage": {"prompt_tokens": 0, "total_tokens": 0}}

        # Define the actual API call logic within a function for the retry wrapper
        def operation_func():
            used_model = model or self.default_embedding_model
            processed_input = texts
            # Apply query instruction if provided (as suggested for doubao)
            if query_instruction :
                 processed_input = [query_instruction + text for text in texts]
                 logger.info(f"为 doubao-embedding 应用查询指令前缀: '{query_instruction}'")

            params = {
                "model": used_model,
                "input": processed_input,
            }

            # Pass through relevant kwargs like extra_headers
            if "extra_headers" in kwargs:
                params["extra_headers"] = kwargs["extra_headers"]
                logger.debug(f"使用自定义 Headers: {kwargs['extra_headers']}")

            print(f"发送到火山引擎 Embeddings API ({used_model}) 的请求...")
            # print(f"  - 文本数量: {len(params['input'])}")
            # print(f"  - Params: {params}") # Be careful logging full input texts

            # Log first few chars of first text for context
            if params['input']:
                 print(f"  - 首个文本片段: '{params['input'][0][:50]}...'")

            # Call the Ark SDK client's embedding creation method
            response = self.ark_client.embeddings.create(**params)
            print("Embeddings API 调用成功!")
            # print(response) # Optional: log raw response for debugging

            # Extract embeddings and usage info
            embeddings = [item.embedding for item in response.data]
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0,
                "total_tokens": response.usage.total_tokens if hasattr(response.usage, 'total_tokens') else 0
            }

            result = {
                "embeddings": embeddings,
                "model": used_model,
                "usage": usage
            }
            return result

        # Execute the operation with retry logic
        try:
            return self._execute_with_retry(operation_func, "文本向量生成")
        except ArkAPIError as e:
            # Catch ArkAPIError specifically if it wasn't handled by retry (e.g., non-network errors)
            # _execute_with_retry already calls _handle_api_error for non-retryable errors
            # This catch block might be redundant if _execute_with_retry handles it, but ensures clarity.
            self._handle_api_error("文本向量生成 (Ark specific)", e)
        except Exception as e:
            # Catch any other unexpected errors during the process
             self._handle_api_error("文本向量生成 (Unexpected)", e)


    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 1.0,
        stop_sequences: Optional[List[str]] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成对话完成

        Args:
            messages: 消息历史列表
            max_tokens: 最大生成 token 数量
            temperature: 温度
            top_p: Top-P 采样
            stop_sequences: 停止序列
            model: 使用的模型，默认使用初始化时设置的聊天模型
            **kwargs: 其他传递给 OpenAI 兼容 API 的参数

        Returns:
            包含生成回复及元数据的字典
        """
        if not self.openai_client:
            raise APIException("火山引擎 OpenAI 兼容客户端未初始化", EXTERNAL_API_ERROR)

        # Define the actual API call logic within a function for the retry wrapper
        def operation_func():
            used_model = model or self.default_chat_model

            params = {
                "model": used_model,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens
            }

            if stop_sequences:
                params["stop"] = stop_sequences

            # 添加其他来自 kwargs 的参数
            for key, value in kwargs.items():
                if key not in params:
                    params[key] = value
                    logger.debug(f"Adding extra kwarg to chat completion: {key}={value}")

            print(f"发送到火山引擎 Chat API ({used_model}) 的请求...")
            # print(f"  - 消息数量: {len(params['messages'])}")
            # print(f"  - 温度: {params['temperature']}")
            # print(f"  - 最大tokens: {params['max_tokens']}")
            # print(f"  - Params: {params}") # Be careful logging full messages

            # 发送请求 (使用 OpenAI client)
            response = self.openai_client.chat.completions.create(**params)
            # print(response) # Optional: log raw response
            print("Chat API 调用成功!")

            # 构造统一格式的返回结果
            # Ensure we handle cases where choices might be empty (though unlikely on success)
            if not response.choices:
                 raise APIException("API 调用成功但未返回有效的 choices。", EXTERNAL_API_ERROR)

            first_choice = response.choices[0]
            message_content = first_choice.message.content if first_choice.message else None

            # Handle potential None content
            if message_content is None:
                logger.warning("API 返回的 message content 为 None.")
                message_content = "" # Default to empty string

            result = {
                "message": {
                    "role": "assistant",
                    "content": message_content
                },
                "model": used_model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                },
                "finish_reason": first_choice.finish_reason
            }

            # 火山引擎特定字段 (如果存在，基于之前的代码)
            if hasattr(first_choice.message, 'reasoning_content') and first_choice.message.reasoning_content:
                result["reasoning_content"] = first_choice.message.reasoning_content
                logger.debug("包含 reasoning_content")

            return result

        # Execute the operation with retry logic
        return self._execute_with_retry(operation_func, "对话生成")

    def count_tokens(self, text: str) -> int:
        """计算文本包含的token数量 (估算)

        Args:
            text: 需要计算token的文本

        Returns:
            估算的 token 数量
        """
        # 火山引擎没有官方的 client-side token 计数方法，继续使用之前的估算
        # 更好的方法是依赖 API 返回的 usage 数据
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        # 简单英文单词计数 (按空格分割，并检查是否为 ASCII)
        english_words = len([word for word in text.split() if word and all(c.isascii() and c.isalnum() for c in word)])
        # 其他字符（包括标点、特殊符号等）也可能计入 token，这里简化处理
        other_chars = len(text) - chinese_chars - sum(len(word) for word in text.split() if word and all(c.isascii() and c.isalnum() for c in word))

        # 估算: 1 中文字符 ~= 1 token, 1 英文单词 ~= 1.5 tokens (粗略)
        # 其他字符的 token 计数比较难估算，暂时忽略或按比例计入
        estimated_tokens = chinese_chars + int(english_words * 1.5) + int(other_chars * 0.5) # 粗略估计其他字符
        # logger.debug(f"Token estimation for '{text[:50]}...': Chinese={chinese_chars}, EnglishWords={english_words}, Other={other_chars} -> Estimated={estimated_tokens}")
        return estimated_tokens


    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表 (硬编码/待实现)

        Returns:
            可用模型信息列表
        """
        # TODO: 火山引擎似乎没有标准的 "list models" API 端点像 OpenAI 那样。
        # 需要查阅文档或平台看是否有获取方式，否则只能硬编码已知模型。
        # 基于当前代码和文档，返回已知模型：
        return [
            {
                "id": "deepseek-r1-250120", # 来自原代码 default
                "type": "chat",
                "provider": "Volcano"
            },
            {
                "id": "deepseek-coder", # 来自原代码 get_available_models
                "type": "chat",
                "provider": "Volcano"
            },
            {
                "id": "doubao-embedding-large-text-240915", # 来自 embedding 文档
                "type": "embedding",
                "provider": "Volcano"
            }
            # 添加其他你知道的可用火山引擎模型
        ]

    def health_check(self) -> bool:
        """检查API连接状态

        Returns:
            连接是否基本正常
        """
        # 检查两个客户端是否已初始化
        if not self.openai_client and not self.ark_client:
            logger.warning("健康检查失败: 两个火山引擎客户端均未初始化。")
            return False

        results = {}

        # 1. 检查 Chat (OpenAI compatible client)
        if self.openai_client:
            try:
                logger.debug("执行健康检查 (Chat)...")
                # 尝试发送一个非常短的消息
                self.generate_chat_completion(
                    messages=[{"role": "user", "content": "Health check"}],
                    max_tokens=5,
                    temperature=0.1 # Low temp for predictable (short) response
                )
                logger.info("健康检查 (Chat): 成功")
                results['chat'] = True
            except APIException as e:
                logger.warning(f"健康检查 (Chat): 失败 - {e}")
                results['chat'] = False
            except Exception as e:
                 logger.error(f"健康检查 (Chat): 意外错误 - {e}", exc_info=True)
                 results['chat'] = False
        else:
             results['chat'] = None # Not initialized

        # 2. 检查 Embeddings (Ark client)
        if self.ark_client:
            try:
                logger.debug("执行健康检查 (Embeddings)...")
                 # 尝试获取一个短文本的向量
                self.generate_embeddings(texts=["Health check"])
                logger.info("健康检查 (Embeddings): 成功")
                results['embeddings'] = True
            except APIException as e:
                logger.warning(f"健康检查 (Embeddings): 失败 - {e}")
                results['embeddings'] = False
            except Exception as e:
                 logger.error(f"健康检查 (Embeddings): 意外错误 - {e}", exc_info=True)
                 results['embeddings'] = False
        else:
             results['embeddings'] = None # Not initialized

        # 认为服务健康的标准是至少有一个客户端成功初始化并能成功执行检查
        # 或者可以更严格：要求所有初始化的客户端都健康
        is_healthy = (results.get('chat') is True) or (results.get('embeddings') is True)
        logger.info(f"整体健康检查结果: {is_healthy} (Chat: {results['chat']}, Embeddings: {results['embeddings']})")
        return is_healthy


    def get_provider_name(self) -> str:
        """获取提供商名称"""
        return "Volcano"

# --- Helper function from doubao-embedding docs (optional, if needed outside) ---
# You might place this in a separate utility module if used elsewhere
def sliced_norm_l2(vec: List[float], dim=2048) -> List[float]:
    """
    Performs slicing and L2 normalization, typically for doubao-embedding.
    Args:
        vec: The embedding vector (list of floats).
        dim: The target dimension to slice to (e.g., 512, 1024, 2048).
    Returns:
        The sliced and L2-normalized vector.
    Raises:
        ValueError if dim is invalid or vector is too short.
        ZeroDivisionError if the norm of the sliced vector is zero.
    """
    if not isinstance(vec, list) or not vec:
        raise ValueError("Input vector must be a non-empty list.")
    if dim <= 0 or dim > len(vec):
        raise ValueError(f"Target dimension {dim} is invalid for vector of length {len(vec)}.")

    sliced_vec = vec[:dim]
    norm = np.linalg.norm(sliced_vec)

    if norm == 0:
        # Handle zero vector case - cannot normalize. Return zeros or raise error.
        logger.warning(f"Norm of sliced vector (dim={dim}) is zero. Returning zero vector.")
        return [0.0] * dim
        # Alternatively: raise ZeroDivisionError("Cannot normalize a zero vector")

    normalized_vec = [v / norm for v in sliced_vec]
    return normalized_vec