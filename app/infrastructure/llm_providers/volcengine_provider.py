# app/infrastructure/llm_providers/volcengine_provider.py
"""火山引擎大模型服务提供商实现"""
import time
import random
from typing import Dict, Any, Generator, List, Optional, Union
import logging

from app.infrastructure.llm_providers.base import LLMProviderInterface
from app.core.exceptions import APIException
from app.core.status_codes import EXTERNAL_API_ERROR, TIMEOUT, RATE_LIMITED, AUTH_FAILED, MODEL_NOT_FOUND, PARAMETER_ERROR

logger = logging.getLogger(__name__)

class VolcengineProvider(LLMProviderInterface):
    """火山引擎方舟大模型服务提供商"""

    def __init__(self):
        """初始化火山引擎提供商"""
        self.client = None
        self.default_model: str = "deepseek-r1-250528"
        self.embeddings_model: str = "text-embedding-3-large"  # 根据实际支持的嵌入模型调整
        self.max_retries: int = 3
        self.retry_delay: int = 2
        self.api_key: str = ""
        self.base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    def initialize(self, api_key: str, **kwargs) -> None:
        """初始化火山引擎客户端

        Args:
            api_key: 火山引擎 ARK API Key
            **kwargs: 其他初始化参数，可包含:
                      - api_base_url (str): 自定义API端点，默认为火山引擎端点
                      - default_model (str): 默认文本生成模型名称
                      - embeddings_model (str): 嵌入模型名称（如果支持）
                      - max_retries (int): 提供商包装器的最大重试次数
                      - client_max_retries (int): 客户端内部的最大重试次数
                      - timeout (float): 请求超时时间 (秒)
                      - region (str): 区域设置
        """
        try:
            logger.info("Initializing Volcengine ARK client...")
            print("===================")

            # 检查 api_key
            if not api_key:
                raise APIException("Missing Volcengine ARK API Key", AUTH_FAILED)

            # 尝试导入火山引擎 SDK
            try:
                from volcenginesdkarkruntime import Ark
                from volcenginesdkarkruntime._exceptions import ArkAPIError
                self.ArkAPIError = ArkAPIError
            except ImportError:
                raise APIException(
                    "volcengine-python-sdk not installed. Please install it using: pip install 'volcengine-python-sdk[ark]'",
                    AUTH_FAILED
                )

            # 1. 准备传递给 Ark() 构造函数的参数
            client_init_params = {
                "api_key": api_key,
            }

            # 设置基础 URL，默认使用火山引擎的端点
            base_url = kwargs.get("api_base_url", self.base_url)
            if base_url:
                client_init_params["base_url"] = base_url

            # 其他客户端参数
            param_mapping = {
                "timeout": "timeout",
                "client_max_retries": "max_retries",
                "region": "region",
            }

            used_client_args = {}
            for kwarg_key, client_param_key in param_mapping.items():
                if kwarg_key in kwargs and kwargs[kwarg_key] is not None:
                    value = kwargs[kwarg_key]
                    client_init_params[client_param_key] = value
                    used_client_args[client_param_key] = value

            # 3. 初始化火山引擎客户端
            logger.debug(f"Volcengine client init params: {client_init_params}")
            self.client = Ark(**client_init_params)
            self.api_key = api_key
            logger.info("Volcengine ARK client object created.")

            # 4. 更新提供商自身的配置
            self.default_model = kwargs.get("default_model", self.default_model)
            self.embeddings_model = kwargs.get("embeddings_model", self.embeddings_model)
            self.max_retries = kwargs.get("max_retries", self.max_retries)
            self.retry_delay = kwargs.get("retry_delay", self.retry_delay)

            # 5. 记录最终配置
            log_details = [
                f"API Key: {'*' * (len(api_key) - 4)}{api_key[-4:] if api_key and len(api_key) > 4 else 'Provided'}",
                f"Base URL: {client_init_params.get('base_url', self.base_url)}",
                f"Default Text Model: {self.default_model}",
                f"Embeddings Model: {self.embeddings_model}",
                f"Provider Wrapper Max Retries: {self.max_retries}",
                f"Provider Wrapper Initial Retry Delay: {self.retry_delay}s"
            ]
            for key, val in used_client_args.items():
                formatted_key = key.replace('_', ' ').title()
                log_details.append(f"Client {formatted_key}: {val}")

            logger.info("Volcengine Provider initialized successfully with settings:\n  " + "\n  ".join(log_details))

        except Exception as e:
            logger.error(f"Failed to initialize Volcengine client: {str(e)}", exc_info=True)
            raise APIException(f"Volcengine initialization failed: {str(e)}", AUTH_FAILED)

    def _handle_api_error(self, operation: str, error: Exception) -> None:
        """处理API错误

        Args:
            operation: 操作名称
            error: 捕获的异常

        Raises:
            APIException: 转换后的API异常
        """
        error_msg = f"Volcengine {operation} failed: {str(error)}"
        logger.error(error_msg, exc_info=True)

        # 检查是否是火山引擎特定的错误
        if hasattr(self, 'ArkAPIError') and isinstance(error, self.ArkAPIError):
            # 根据火山引擎的错误码进行分类
            status_code = getattr(error, 'status_code', 500)
            if status_code == 429:
                raise APIException(error_msg, RATE_LIMITED, 429) from error
            elif status_code == 401 or status_code == 403:
                raise APIException(error_msg, AUTH_FAILED, status_code) from error
            elif status_code == 404:
                raise APIException(error_msg, MODEL_NOT_FOUND, 404) from error
            elif status_code == 400:
                raise APIException(error_msg, PARAMETER_ERROR, 400) from error
            else:
                raise APIException(error_msg, EXTERNAL_API_ERROR, status_code) from error
        else:
            # 通用错误处理
            if "timeout" in str(error).lower() or "timed out" in str(error).lower():
                raise APIException(error_msg, TIMEOUT, 504) from error
            elif "rate limit" in str(error).lower():
                raise APIException(error_msg, RATE_LIMITED, 429) from error
            else:
                raise APIException(error_msg, EXTERNAL_API_ERROR) from error

    def _execute_with_retry(self, operation_func, operation_name, *args, **kwargs):
        """使用重试机制执行API操作

        Args:
            operation_func: 要执行的操作函数
            operation_name: 操作名称（用于日志）
            *args, **kwargs: 传递给操作函数的参数

        Returns:
            操作结果

        Raises:
            APIException: 当所有重试都失败时
        """
        retry_count = 0
        current_delay = self.retry_delay

        while retry_count <= self.max_retries:
            try:
                return operation_func(*args, **kwargs)
            except Exception as e:
                # 检查是否应该重试
                should_retry = False
                if hasattr(self, 'ArkAPIError') and isinstance(e, self.ArkAPIError):
                    status_code = getattr(e, 'status_code', 500)
                    # 重试特定的错误码
                    should_retry = status_code in [429, 500, 502, 503, 504]
                elif "timeout" in str(e).lower() or "connection" in str(e).lower():
                    should_retry = True

                if not should_retry:
                    # 不应该重试的错误直接抛出
                    self._handle_api_error(operation_name, e)

                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"Volcengine {operation_name} failed after {self.max_retries} retries.")
                    self._handle_api_error(operation_name, e)

                # 指数退避
                wait_time = current_delay * (2 ** (retry_count - 1))
                jitter = wait_time * 0.1
                wait_time += random.uniform(-jitter, jitter)
                wait_time = max(0.5, wait_time)

                logger.warning(
                    f"Volcengine {operation_name} encountered error: {type(e).__name__}. "
                    f"Retrying ({retry_count}/{self.max_retries}) after {wait_time:.2f} seconds..."
                )
                time.sleep(wait_time)

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
        """生成文本"""
        # 火山引擎主要使用 chat completions，将文本生成映射到聊天完成
        return self.generate_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_sequences=stop_sequences,
            model=model,
            **kwargs
        )

    def generate_embeddings(self, texts: List[str], model: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """生成文本嵌入向量
        
        注意：火山引擎的嵌入模型可能有所不同，需要根据实际支持情况调整
        """
        if not self.client:
            raise APIException("Volcengine client not initialized", AUTH_FAILED)

        resolved_model = model or self.embeddings_model
        logger.debug(f"Generating embeddings with Volcengine model: {resolved_model}")

        def operation_func():
            # 火山引擎可能有专门的嵌入接口，这里需要根据实际API调整
            # 目前先返回不支持的提示
            raise APIException(
                "Volcengine embeddings API not implemented yet. Please check Volcengine documentation for embeddings support.",
                EXTERNAL_API_ERROR
            )

        try:
            return self._execute_with_retry(operation_func, f"Embeddings Generation ({resolved_model})")
        except Exception as e:
            if not isinstance(e, APIException):
                self._handle_api_error(f"Embeddings Generation ({resolved_model})", e)
            else:
                raise e

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
        """生成对话完成"""
        if not self.client:
            raise APIException("Volcengine client not initialized", AUTH_FAILED)

        resolved_model = model or self.default_model
        logger.debug(f"Generating chat completion with Volcengine model: {resolved_model}")

        def operation_func():
            # 准备请求参数
            request_params = {
                "model": resolved_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
            }
            print(request_params)
            
            # 添加停止序列
            if stop_sequences:
                request_params["stop"] = stop_sequences
            
            # 添加其他参数
            request_params.update(kwargs)

            # 调用火山引擎API
            response = self.client.chat.completions.create(**request_params)
            print(response)

            if not response or not response.choices or not response.choices[0].message:
                raise APIException("Volcengine API returned an empty or invalid chat completion response.", EXTERNAL_API_ERROR)

            message_content = response.choices[0].message.content
            if message_content is None:
                logger.warning(f"Chat completion finished with reason '{response.choices[0].finish_reason}', content is None.")
                message_content = ""

            return {
                "message": {
                    "role": response.choices[0].message.role or "assistant",
                    "content": message_content
                },
                "finish_reason": response.choices[0].finish_reason,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
            }

        try:
            return self._execute_with_retry(operation_func, f"Chat Completion ({resolved_model})")
        except Exception as e:
            if not isinstance(e, APIException):
                self._handle_api_error(f"Chat Completion ({resolved_model})", e)
            else:
                raise e

    def generate_chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 1.0,
        stop_sequences: Optional[List[str]] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Generator[Dict[str, Any], None, None]:
        """生成流式对话完成"""
        if not self.client:
            raise APIException("Volcengine client not initialized", AUTH_FAILED)

        resolved_model = model or self.default_model
        logger.debug(f"Generating streaming chat completion with Volcengine model: {resolved_model}")

        def operation_func():
            try:
                # 准备请求参数
                request_params = {
                    "model": resolved_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                    "stream": True,  # 启用流式输出
                }
                
                if stop_sequences:
                    request_params["stop"] = stop_sequences
                
                request_params.update(kwargs)

                stream = self.client.chat.completions.create(**request_params)
                
                accumulated_content = ""
                
                for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        choice = chunk.choices[0]
                        
                        # 处理内容增量
                        if choice.delta and choice.delta.content:
                            content_delta = choice.delta.content
                            accumulated_content += content_delta
                            
                            yield {
                                "type": "content",
                                "content": content_delta,
                                "accumulated": accumulated_content
                            }
                        
                        # 处理完成原因
                        if choice.finish_reason:
                            yield {
                                "type": "finish",
                                "finish_reason": choice.finish_reason,
                                "accumulated": accumulated_content
                            }
                            break
                
                # 发送使用统计（如果可用）
                if hasattr(chunk, 'usage') and chunk.usage:
                    yield {
                        "type": "usage",
                        "usage": {
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                            "total_tokens": chunk.usage.total_tokens
                        }
                    }
            
            except Exception as e:
                logger.error(f"Volcengine streaming error: {str(e)}")
                yield {
                    "type": "error",
                    "error": str(e)
                }
        
        try:
            for chunk in operation_func():
                yield chunk
        except Exception as e:
            if not isinstance(e, APIException):
                self._handle_api_error(f"Streaming Chat Completion ({resolved_model})", e)
            else:
                raise e

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """计算文本包含的token数量
        
        火山引擎提供了分词API，可以使用其计算token数量
        """
        model_to_use = model or self.default_model
        
        if not self.client:
            # 客户端未初始化，使用估算
            logger.warning("Volcengine client not initialized for token counting, using estimation.")
            return int(len(text) / 3.5)  # 中文估算
        
        try:
            # 火山引擎可能有专门的token计数API
            # 这里需要根据实际API文档调整
            # 目前使用简单估算
            logger.debug(f"Using token estimation for Volcengine model: {model_to_use}")
            # 中文和英文混合的估算
            return int(len(text) / 3.0)
        except Exception as e:
            logger.warning(f"Volcengine token counting failed: {str(e)}. Falling back to estimation.")
            return int(len(text) / 3.0)

    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        if not self.client:
            raise APIException("Volcengine client not initialized", AUTH_FAILED)

        logger.debug("Fetching available models from Volcengine API...")

        def operation_func():
            try:
                # 火山引擎可能有获取模型列表的API
                # 根据文档，这里列出一些已知的模型
                known_models = [
                    {
                        "id": "doubao-1.5-pro",
                        "name": "豆包-1.5-pro",
                        "description": "最新一代专业版大模型，在知识、代码、推理、中文等多项测评中获得高分",
                        "context_window": 32768,
                        "model_type": "chat"
                    },
                    {
                        "id": "doubao-1.5-lite",
                        "name": "豆包-1.5-lite",
                        "description": "最新一代轻量版大模型，性价比极高",
                        "context_window": 32768,
                        "model_type": "chat"
                    },
                    {
                        "id": "deepseek-r1-250528",
                        "name": "豆包-pro-32k",
                        "description": "专业版大模型，高质量低成本",
                        "context_window": 32768,
                        "model_type": "chat"
                    },
                    {
                        "id": "doubao-pro-128k",
                        "name": "豆包-pro-128k",
                        "description": "长文本专业版模型，支持约20万字上下文",
                        "context_window": 131072,
                        "model_type": "chat"
                    },
                    {
                        "id": "doubao-pro-256k",
                        "name": "豆包-pro-256k",
                        "description": "超长文本专业版模型，支持约40万字上下文",
                        "context_window": 262144,
                        "model_type": "chat"
                    },
                    {
                        "id": "doubao-lite",
                        "name": "豆包-lite",
                        "description": "轻量级大模型，极致响应速度",
                        "context_window": 32768,
                        "model_type": "chat"
                    },
                    {
                        "id": "deepseek-v3-250324",
                        "name": "DeepSeek V3",
                        "description": "DeepSeek V3最新版本",
                        "context_window": 65536,
                        "model_type": "chat"
                    },
                    {
                        "id": "deepseek-r1-250120",
                        "name": "DeepSeek R1",
                        "description": "DeepSeek R1深度思考模型",
                        "context_window": 65536,
                        "model_type": "reasoning"
                    }
                ]
                return known_models
            except Exception as e:
                logger.warning(f"Failed to fetch Volcengine models, returning known models: {str(e)}")
                # 返回基本的已知模型列表
                return [
                    {
                        "id": "deepseek-r1-250528",
                        "name": "豆包-pro-32k",
                        "description": "专业版大模型",
                        "context_window": 32768,
                        "model_type": "chat"
                    }
                ]

        try:
            models = self._execute_with_retry(operation_func, "Model Listing")
            logger.info(f"Successfully retrieved {len(models)} models from Volcengine.")
            return models
        except Exception as e:
            if not isinstance(e, APIException):
                self._handle_api_error("Model Listing", e)
            else:
                raise e

    def health_check(self) -> bool:
        """检查API连接状态"""
        logger.debug("Performing Volcengine health check...")
        try:
            if not self.client:
                return False
            
            # 使用一个简单的请求作为健康检查
            test_response = self.client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            logger.info("Volcengine health check successful.")
            return True
        except Exception as e:
            logger.error(f"Volcengine health check failed: {str(e)}")
            return False

    def supports_streaming(self) -> bool:
        """检查是否支持流式输出"""
        return True

    def get_provider_name(self) -> str:
        """获取提供商名称"""
        return "Volcengine"