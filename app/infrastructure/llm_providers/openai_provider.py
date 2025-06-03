# app/infrastructure/llm_providers/openai_provider.py
import time
from typing import Dict, Any, Generator, List, Optional, Union
import logging

from openai import OpenAI, APIError, RateLimitError, APIConnectionError
from tiktoken import encoding_for_model

from app.infrastructure.llm_providers.base import LLMProviderInterface
from app.core.exceptions import APIException
from app.core.status_codes import OPENAI_API_ERROR, TIMEOUT, RATE_LIMITED

import random
logger = logging.getLogger(__name__)

class OpenLLMProvider(LLMProviderInterface):
    """OpenAI API服务提供商"""

    def __init__(self):
        """初始化OpenAI提供商"""
        self.client: Optional[OpenAI] = None
        self.default_model: str = "gpt-4o-mini"
        self.embeddings_model: str = "text-embedding-3-large"
        self.max_retries: int = 3  # Max retries for the provider's wrapper logic
        self.retry_delay: int = 2  # Initial retry delay (seconds) for the wrapper logic

    def initialize(self, api_key: str, **kwargs) -> None:
        """初始化OpenAI客户端

        Args:
            api_key: OpenAI API密钥
            **kwargs: 其他初始化参数，可包含:
                      - api_base_url (str): 自定义API端点
                      - default_model (str): 默认文本生成模型名称
                      - embeddings_model (str): 嵌入模型名称
                      - max_retries (int): 提供商包装器的最大重试次数
                      - client_max_retries (int): OpenAI客户端内部的最大重试次数
                      - timeout (float): 请求超时时间 (秒)
                      - organization (str): OpenAI组织ID
                      # 其他可以传递给 OpenAI() 构造函数的参数
        """
        try:
            logger.info("Initializing OpenAI client...")

            # 1. 准备传递给 OpenAI() 构造函数的参数
            client_init_params = {
                "api_key": api_key,
            }

            print("kwargs:", kwargs)
            param_mapping = {
                "api_base_url": "base_url",
                "timeout": "timeout",
                "client_max_retries": "max_retries", #区分提供商包装器的重试和客户端内部重试
                "organization": "organization",
                # Add other relevant OpenAI client constructor params here if needed
            }
            

            used_client_args = {} # Track args passed to OpenAI() for logging
            for kwarg_key, client_param_key in param_mapping.items():
                if kwarg_key in kwargs and kwargs[kwarg_key] is not None:
                    value = kwargs[kwarg_key]
                    client_init_params[client_param_key] = value
                    used_client_args[client_param_key] = value

            # 3. 初始化 OpenAI 客户端
            print(f"OpenAI client init params: {client_init_params}")
            self.client = OpenAI(**client_init_params)
            logger.info("OpenAI client object created.")

            # 4. 更新提供商自身的配置 (来自kwargs或使用默认值)
            self.default_model = kwargs.get("default_model", self.default_model)
            self.embeddings_model = kwargs.get("embeddings_model", self.embeddings_model)
            # 使用 'max_retries' 控制 *我们自己* 的重试逻辑 (_execute_with_retry)
            self.max_retries = kwargs.get("max_retries", self.max_retries)
            # 可以选择性地从 kwargs 更新 retry_delay
            self.retry_delay = kwargs.get("retry_delay", self.retry_delay)

            # 5. 记录最终配置
            log_details = [
                f"API Key: {'*' * (len(api_key) - 4)}{api_key[-4:] if api_key and len(api_key) > 4 else 'Provided'}",
                f"Default Text Model: {self.default_model}",
                f"Embeddings Model: {self.embeddings_model}",
                f"Provider Wrapper Max Retries: {self.max_retries}",
                f"Provider Wrapper Initial Retry Delay: {self.retry_delay}s"
            ]
            for key, val in used_client_args.items():
                # Format key for readability in logs (e.g., base_url -> Base URL)
                formatted_key = key.replace('_', ' ').title()
                log_details.append(f"Client {formatted_key}: {val}")

            logger.info("OpenAI Provider initialized successfully with settings:\n  " + "\n  ".join(log_details))

        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}", exc_info=True)
            raise APIException(f"OpenAI initialization failed: {str(e)}", OPENAI_API_ERROR)

    def _handle_api_error(self, operation: str, error: Exception) -> None:
        """处理API错误

        Args:
            operation: 操作名称
            error: 捕获的异常

        Raises:
            APIException: 转换后的API异常
        """
        error_msg = f"OpenAI {operation} failed: {str(error)}"
        logger.error(error_msg, exc_info=True) # Add exc_info for context

        if isinstance(error, RateLimitError):
            raise APIException(error_msg, RATE_LIMITED, 429) from error
        elif isinstance(error, APIConnectionError): # Includes timeouts potentially
             # Check if it's specifically a timeout based on message or type if possible
            if "timed out" in str(error).lower():
                 raise APIException(error_msg, TIMEOUT, 504) from error # Use 504 Gateway Timeout
            else:
                 raise APIException(error_msg, TIMEOUT, 503) from error # Service Unavailable for connection issues
        elif isinstance(error, APIError): # Catch broader OpenAI API errors
            # You might want to inspect error.status_code if available
            status_code = getattr(error, 'status_code', 500)
            raise APIException(error_msg, OPENAI_API_ERROR, status_code) from error
        else: # Other unexpected errors
            raise APIException(error_msg, OPENAI_API_ERROR) from error

    def _execute_with_retry(self, operation_func, operation_name, *args, **kwargs):
        """使用重试机制执行API操作 (Provider-level wrapper retry)

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
            except (RateLimitError, APIConnectionError) as e: # Retry only on these specific, potentially transient errors
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"OpenAI {operation_name} failed after {self.max_retries} retries.")
                    self._handle_api_error(operation_name, e) # Raise the final error

                # Exponential backoff
                wait_time = current_delay * (2 ** (retry_count - 1))
                # Add some jitter (e.g., +/- 10%)
                jitter = wait_time * 0.1
                wait_time += random.uniform(-jitter, jitter)
                wait_time = max(0.5, wait_time) # Ensure minimum wait time

                logger.warning(
                    f"OpenAI {operation_name} encountered error: {type(e).__name__}. "
                    f"Retrying ({retry_count}/{self.max_retries}) after {wait_time:.2f} seconds..."
                )
                time.sleep(wait_time)

            except APIException: # If operation_func itself raises an APIException handled internally
                raise # Re-raise immediately
            except Exception as e:
                # Handle other unexpected errors immediately without retry by this wrapper
                logger.error(f"OpenAI {operation_name} encountered unexpected error during execution.")
                self._handle_api_error(operation_name, e) # Will wrap and raise APIException

    # --- generate_text, generate_embeddings, generate_chat_completion methods remain largely the same ---
    # They will now use self.client which was initialized potentially with base_url etc.
    # The self._execute_with_retry wrapper handles retries based on self.max_retries.

    def generate_text(
        self,
        prompt: str,

        temperature: float = 0.7,
        top_p: float = 1.0,
        stop_sequences: Optional[List[str]] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成文本"""
        if not self.client:
            raise APIException("OpenAI client not initialized", OPENAI_API_ERROR)

        resolved_model = model or self.default_model
        logger.debug(f"Generating text with model: {resolved_model}")

        def operation_func():
            response = self.client.completions.create(
                model=resolved_model,
                prompt=prompt,
     
                temperature=temperature,
                top_p=top_p,
                stop=stop_sequences,
                **kwargs
            )
            # Check if response or choices are valid
            if not response or not response.choices:
                raise APIException("OpenAI API returned an empty or invalid response.", OPENAI_API_ERROR)

            return {
                "text": response.choices[0].text,
                "finish_reason": response.choices[0].finish_reason,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
            }

        try:
            # Pass model explicitly for clarity in retry logs if needed, though already in operation_func
            return self._execute_with_retry(operation_func, f"Text Generation ({resolved_model})")
        except Exception as e:
            # Catch potential exceptions from _execute_with_retry (which should be APIExceptions)
            # or if client wasn't initialized correctly before call.
            if not isinstance(e, APIException):
                 self._handle_api_error(f"Text Generation ({resolved_model})", e)
            else:
                 raise e # Re-raise APIException


    def generate_embeddings(self, texts: List[str], model: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """生成文本嵌入向量"""
        if not self.client:
            raise APIException("OpenAI client not initialized", OPENAI_API_ERROR)

        resolved_model = model or self.embeddings_model
        logger.debug(f"Generating embeddings with model: {resolved_model}")

        def operation_func():
            response = self.client.embeddings.create(
                model=resolved_model,
                input=texts,
                **kwargs
            )
            if not response or not response.data:
                 raise APIException("OpenAI API returned an empty or invalid response for embeddings.", OPENAI_API_ERROR)

            return {
                "embeddings": [item.embedding for item in response.data],
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
            }

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

        stop_sequences: Optional[List[str]] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成对话完成"""
        if not self.client:
            raise APIException("OpenAI client not initialized", OPENAI_API_ERROR)

        resolved_model = model or self.default_model
        logger.debug(f"Generating chat completion with model: {resolved_model}")

        def operation_func():
            response = self.client.chat.completions.create(
                model=resolved_model,
                messages=messages,
      
                stop=stop_sequences,
                **kwargs
            )
            if not response or not response.choices or not response.choices[0].message:
                raise APIException("OpenAI API returned an empty or invalid chat completion response.", OPENAI_API_ERROR)


            message_content = response.choices[0].message.content
            # Handle potential None content if finish_reason indicates an issue (e.g., 'content_filter')
            if message_content is None:
                 logger.warning(f"Chat completion finished with reason '{response.choices[0].finish_reason}', content is None.")
                 message_content = "" # Return empty string or handle as needed


            return {
                "message": {
                    "role": response.choices[0].message.role or "assistant", # Default role if missing
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


    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """计算文本包含的token数量"""
        model_to_use = model or self.default_model
        try:
            # Ensure tiktoken is installed: pip install tiktoken
            encoding = encoding_for_model(model_to_use)
            return len(encoding.encode(text))
        except ModuleNotFoundError:
            logger.warning("tiktoken library not found. Falling back to rough estimation for token count.")
            # Rough estimation (words * factor)
            return int(len(text.split()) * 1.5) # Adjusted factor slightly
        except KeyError:
            logger.warning(f"No tiktoken encoding found for model '{model_to_use}'. Falling back to rough estimation.")
            # Fallback for models not recognized by tiktoken
            return int(len(text.split()) * 1.5)
        except Exception as e:
            logger.warning(f"Token counting failed due to an unexpected error: {str(e)}. Falling back to rough estimation.")
            return int(len(text.split()) * 1.5)

    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        if not self.client:
            raise APIException("OpenAI client not initialized", OPENAI_API_ERROR)

        logger.debug("Fetching available models from OpenAI API...")

        def operation_func():
            response = self.client.models.list()
            return [
                {
                    "id": model.id,
                    "created": model.created,
                    "owned_by": model.owned_by,
                    # Add other relevant fields if needed, e.g., 'object', 'parent'
                }
                for model in response.data
            ] if response and response.data else []

        try:
            # Retries might be less critical here, but applying for consistency
            models = self._execute_with_retry(operation_func, "Model Listing")
            logger.info(f"Successfully retrieved {len(models)} models.")
            return models
        except Exception as e:
             # Error handled by _execute_with_retry or _handle_api_error if it fails
             if not isinstance(e, APIException):
                 self._handle_api_error("Model Listing", e) # Ensure it's wrapped
             else:
                  raise e # Re-raise APIException

    def health_check(self) -> bool:
        """检查API连接状态"""
        logger.debug("Performing OpenAI health check...")
        try:
            # Use a lightweight operation like listing models as a health check
            self.get_available_models()
            logger.info("OpenAI health check successful.")
            return True
        except APIException as e:
            # Log the specific API exception during health check failure
            logger.error(f"OpenAI health check failed: {str(e)} (Code: {e.status_code})")
            return False
        except Exception as e:
             # Catch any other unexpected exceptions during health check
             logger.error(f"OpenAI health check failed with unexpected error: {str(e)}", exc_info=True)
             return False
        
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
            raise APIException("OpenAI client not initialized", OPENAI_API_ERROR)

        resolved_model = model or self.default_model
        logger.debug(f"Generating streaming chat completion with model: {resolved_model}")

        def operation_func():
            try:
                stream = self.client.chat.completions.create(
                    model=resolved_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stop=stop_sequences,
                    stream=True,  # 启用流式输出
                    **kwargs
                )
                
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
                logger.error(f"OpenAI streaming error: {str(e)}")
                yield {
                    "type": "error",
                    "error": str(e)
                }
        
        try:
            # 使用现有的重试机制包装流式操作
            for chunk in operation_func():
                yield chunk
        except Exception as e:
            if not isinstance(e, APIException):
                self._handle_api_error(f"Streaming Chat Completion ({resolved_model})", e)
            else:
                raise e

    def supports_streaming(self) -> bool:
        """检查是否支持流式输出"""
        return True

    def get_provider_name(self) -> str:
        """获取提供商名称"""
        return "OpenAI"

