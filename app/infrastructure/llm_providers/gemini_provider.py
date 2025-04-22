# app/infrastructure/llm_providers/gemini_provider.py
import logging
import time
import random
from typing import Dict, Any, List, Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from app.infrastructure.llm_providers.base import LLMProviderInterface
from app.core.exceptions import APIException
from app.core.status_codes import CONTENT_FILTER_BLOCKED, EXTERNAL_API_ERROR, PARAMETER_ERROR, TIMEOUT, RATE_LIMITED, AUTH_FAILED, MODEL_NOT_FOUND

logger = logging.getLogger(__name__)

class GeminiProvider(LLMProviderInterface):
    """Google Gemini API 服务提供商"""

    def __init__(self):
        """初始化 Gemini 提供商"""
        self.client_configured: bool = False
        self.default_chat_model: str = "gemini-1.5-flash-latest" # Example default
        self.default_embedding_model: str = "text-embedding-004" # Example default
        self.max_retries: int = 3
        self.retry_delay: int = 2

    def initialize(self, api_key: str, **kwargs) -> None:
        """初始化 Gemini 客户端

        Args:
            api_key: Google AI API 密钥
            **kwargs: 其他初始化参数，可包含:
                      - default_model / default_chat_model: 默认聊天模型名称
                      - default_embedding_model: 默认向量模型名称
                      - max_retries: 最大重试次数
                      - timeout: 请求超时时间 (注意: SDK 可能有自己的超时处理)
        """
        try:
            print("Initializing Gemini client...")
            print("Initializing Google Gemini client...")
            if not api_key:
                raise APIException("Missing Google AI API Key for Gemini provider", AUTH_FAILED)

            genai.configure(api_key=api_key)
            self.client_configured = True

            # 更新可选配置
            self.default_chat_model = kwargs.get("default_model",
                                                kwargs.get("default_chat_model", self.default_chat_model))
            self.default_embedding_model = kwargs.get("default_embedding_model", self.default_embedding_model)
            self.max_retries = kwargs.get("max_retries", self.max_retries)
            self.retry_delay = kwargs.get("retry_delay", self.retry_delay)
            # Note: google-generativeai SDK handles timeouts internally to some extent

            log_details = [
                f"API Key: {'*' * (len(api_key) - 4)}{api_key[-4:] if api_key and len(api_key) > 4 else 'Provided'}",
                f"Default Chat Model: {self.default_chat_model}",
                f"Default Embedding Model: {self.default_embedding_model}",
                f"Max Retries: {self.max_retries}",
                f"Initial Retry Delay: {self.retry_delay}s"
            ]
            print("Gemini Provider initialized successfully with settings:\n  " + "\n  ".join(log_details))

        except Exception as e:
            print(f"Failed to initialize Gemini client: {str(e)}", exc_info=True)
            self.client_configured = False
            raise APIException(f"Gemini initialization failed: {str(e)}", AUTH_FAILED)

    def _ensure_initialized(self):
        """确保客户端已配置"""
        if not self.client_configured:
            raise APIException("Gemini client not configured. Call initialize first.", AUTH_FAILED)

    def _handle_api_error(self, operation: str, error: Exception) -> None:
        """处理 Google AI API 错误"""
        error_msg = f"Gemini {operation} failed: {type(error).__name__} - {str(error)}"
        print(error_msg, exc_info=True)

        status_code = EXTERNAL_API_ERROR
        http_status = 500

        if isinstance(error, google_exceptions.PermissionDenied):
            status_code = AUTH_FAILED
            http_status = 403
        elif isinstance(error, google_exceptions.ResourceExhausted):
            status_code = RATE_LIMITED
            http_status = 429
        elif isinstance(error, (google_exceptions.RetryError, google_exceptions.DeadlineExceeded)):
            status_code = TIMEOUT
            http_status = 504 # Gateway Timeout
        elif isinstance(error, google_exceptions.NotFound):
            status_code = MODEL_NOT_FOUND # Or a more specific resource not found
            http_status = 404
        elif isinstance(error, google_exceptions.InvalidArgument):
             status_code = PARAMETER_ERROR
             http_status = 400
        elif isinstance(error, google_exceptions.InternalServerError):
             status_code = EXTERNAL_API_ERROR
             http_status = 500
        # Add more specific Google API error mappings if needed

        raise APIException(error_msg, status_code, http_status) from error

    def _execute_with_retry(self, operation_func, operation_name, *args, **kwargs):
        """使用重试机制执行API操作"""
        self._ensure_initialized()
        retry_count = 0
        current_delay = self.retry_delay

        while retry_count <= self.max_retries:
            try:
                return operation_func(*args, **kwargs)
            except (google_exceptions.ResourceExhausted,
                    google_exceptions.RetryError,
                    google_exceptions.DeadlineExceeded,
                    google_exceptions.ServiceUnavailable, # Explicitly retry on 503
                    google_exceptions.InternalServerError) as e: # Retry on 500 as well
                retry_count += 1
                if retry_count > self.max_retries:
                    print(f"Gemini {operation_name} failed after {self.max_retries} retries.")
                    self._handle_api_error(operation_name, e) # Raise final error

                # Exponential backoff with jitter
                wait_time = current_delay * (2 ** (retry_count - 1))
                jitter = wait_time * 0.2 # Add more jitter
                wait_time += random.uniform(-jitter, jitter)
                wait_time = max(1.0, min(wait_time, 60.0)) # Clamp wait time

                logger.warning(
                    f"Gemini {operation_name} encountered error: {type(e).__name__}. "
                    f"Retrying ({retry_count}/{self.max_retries}) after {wait_time:.2f} seconds..."
                )
                time.sleep(wait_time)
            except APIException: # If operation_func itself raises an APIException handled internally
                raise # Re-raise immediately
            except Exception as e:
                # Handle other unexpected errors immediately without retry by this wrapper
                print(f"Gemini {operation_name} encountered unexpected error during execution.")
                self._handle_api_error(operation_name, e) # Will wrap and raise APIException

    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 1000, # Note: Gemini uses max_output_tokens
        temperature: float = 0.7,
        top_p: float = 1.0,
        stop_sequences: Optional[List[str]] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成文本 (使用 generate_content)"""
        # Gemini primarily uses generate_content for both text and chat.
        # We'll map this to the chat completion structure for consistency.
        print(f"Calling generate_text (mapped to generate_chat_completion) for Gemini.")
        return self.generate_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_sequences=stop_sequences,
            model=model,
            **kwargs
        )

    def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成文本嵌入向量"""
        self._ensure_initialized()
        resolved_model = model or self.default_embedding_model
        # Gemini embedding models might need prefix like "models/"
        if not resolved_model.startswith("models/"):
             resolved_model_for_api = f"models/{resolved_model}"
        else:
             resolved_model_for_api = resolved_model
        logger.debug(f"Generating embeddings with Gemini model: {resolved_model_for_api}")

        # Task type might be needed depending on the model and use case
        task_type = kwargs.get("task_type", "RETRIEVAL_DOCUMENT") # Common default

        def operation_func():
            response = genai.embed_content(
                model=resolved_model_for_api,
                content=texts,
                task_type=task_type
            )
            if not response or "embedding" not in response:
                raise APIException("Gemini API returned invalid response for embeddings.", EXTERNAL_API_ERROR)

            # Note: Gemini embedding API doesn't seem to return token counts directly
            return {
                "embeddings": response["embedding"] if isinstance(response["embedding"], list) else [response["embedding"]], # Ensure list
                "model": resolved_model, # Return the user-facing model name
                "usage": { # Placeholder usage
                    "prompt_tokens": 0,
                    "total_tokens": 0
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
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 1.0,
        stop_sequences: Optional[List[str]] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成对话完成"""
        self._ensure_initialized()
        resolved_model_name = model or self.default_chat_model
        logger.debug(f"Generating chat completion with Gemini model: {resolved_model_name}")

        # Generation Config
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_sequences=stop_sequences or []
        )

        # Prepare messages for Gemini API (needs specific format)
        gemini_messages = []
        system_instruction = None
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if not content: continue # Skip empty messages

            if role == "system":
                # Gemini uses system_instruction parameter
                system_instruction = content
            elif role == "user":
                gemini_messages.append({'role': 'user', 'parts': [content]})
            elif role == "assistant":
                gemini_messages.append({'role': 'model', 'parts': [content]})
            else:
                logger.warning(f"Unsupported role '{role}' in message, treating as user.")
                gemini_messages.append({'role': 'user', 'parts': [content]})

        # Ensure history alternates user/model roles if needed by the model
        # (Basic check, more robust validation might be needed)
        if len(gemini_messages) > 1:
             last_role = gemini_messages[-1]['role']
             if all(m['role'] == last_role for m in gemini_messages):
                  logger.warning("All messages have the same role, which might cause issues.")
             # Add logic here if strict alternation is required (e.g., insert dummy messages)


        def operation_func():
            try:
                # Instantiate the model
                generative_model = genai.GenerativeModel(
                    model_name=resolved_model_name,
                    system_instruction=system_instruction # Add system instruction here
                )

                # Start chat if history exists, otherwise generate directly
                if len(gemini_messages) > 1:
                     # Send history, last message is the new prompt
                     chat = generative_model.start_chat(history=gemini_messages[:-1])
                     response = chat.send_message(
                          gemini_messages[-1]['parts'], # Send the last message's content
                          generation_config=generation_config,
                          stream=False # Assuming non-streaming for this interface
                     )
                elif len(gemini_messages) == 1:
                      # Single message, generate directly
                      response = generative_model.generate_content(
                          gemini_messages[0]['parts'], # Send the single message content
                          generation_config=generation_config,
                          stream=False
                      )
                else:
                     raise APIException("No valid messages provided for chat completion.", PARAMETER_ERROR)

            except google_exceptions.NotFound:
                 raise APIException(f"Gemini model '{resolved_model_name}' not found.", MODEL_NOT_FOUND)
            except Exception as e: # Catch other potential model init/generation errors
                 raise e # Let retry handler catch it

            # Process response
            if not response:
                raise APIException("Gemini API returned an empty response.", EXTERNAL_API_ERROR)

            # Handle potential blocked prompts or safety issues
            if not response.candidates:
                  finish_reason = "UNKNOWN"
                  if response.prompt_feedback and response.prompt_feedback.block_reason:
                       finish_reason = f"BLOCKED:{response.prompt_feedback.block_reason.name}"
                       logger.warning(f"Gemini prompt blocked due to: {finish_reason}")
                       raise APIException(f"Prompt blocked by Gemini safety filters: {finish_reason}", CONTENT_FILTER_BLOCKED)
                  else:
                       print(f"Gemini response has no candidates and no block reason. Raw response: {response}")
                       raise APIException("Gemini response missing candidates.", EXTERNAL_API_ERROR)


            # Extract content and finish reason
            candidate = response.candidates[0]
            message_content = ""
            if candidate.content and candidate.content.parts:
                 message_content = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))

            finish_reason = candidate.finish_reason.name if candidate.finish_reason else "UNKNOWN"
            # Map Gemini finish reasons if needed (e.g., MAX_TOKENS, STOP, SAFETY)
            mapped_finish_reason = finish_reason

            # Extract usage metadata if available (may require specific API versions or be approximate)
            prompt_token_count = 0
            completion_token_count = 0
            total_token_count = 0
            if hasattr(response, 'usage_metadata'):
                 prompt_token_count = response.usage_metadata.prompt_token_count
                 # Gemini API often gives total tokens for candidates
                 completion_token_count = response.usage_metadata.candidates_token_count
                 total_token_count = response.usage_metadata.total_token_count


            return {
                "message": {
                    "role": "assistant", # Gemini responses are from the 'model'
                    "content": message_content
                },
                "finish_reason": mapped_finish_reason,
                "model": resolved_model_name, # Return the model used
                "usage": {
                    "prompt_tokens": prompt_token_count,
                    "completion_tokens": completion_token_count,
                    "total_tokens": total_token_count
                }
            }

        try:
            return self._execute_with_retry(operation_func, f"Chat Completion ({resolved_model_name})")
        except Exception as e:
            if not isinstance(e, APIException):
                self._handle_api_error(f"Chat Completion ({resolved_model_name})", e)
            else:
                raise e

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """计算文本包含的token数量"""
        self._ensure_initialized()
        resolved_model_name = model or self.default_chat_model

        try:
            def operation_func():
                 generative_model = genai.GenerativeModel(model_name=resolved_model_name)
                 # count_tokens can take string or list of strings/parts
                 response = generative_model.count_tokens(text)
                 return response.total_tokens

            # Retries might be less critical here, but applying for consistency
            return self._execute_with_retry(operation_func, f"Token Count ({resolved_model_name})")

        except Exception as e:
            logger.warning(f"Gemini token counting failed for model '{resolved_model_name}': {str(e)}. Falling back to estimation.")
            # Fallback estimation
            return int(len(text) / 3.5) # Rough estimate

    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表"""
        self._ensure_initialized()
        logger.debug("Fetching available models from Google AI API...")

        def operation_func():
            models_list = []
            # Add known default models first for convenience
            known_models = [self.default_chat_model, self.default_embedding_model]
            for model_name in known_models:
                if model_name not in [m['id'] for m in models_list]: # Avoid duplicates if API lists them too
                    try:
                        model_info = genai.get_model(f"models/{model_name}") # Needs 'models/' prefix
                        models_list.append({
                            "id": model_info.name.replace("models/", ""), # Use clean name
                            "name": model_info.display_name,
                            "description": model_info.description,
                            "context_window": model_info.input_token_limit,
                            "max_tokens": model_info.output_token_limit,
                            "supported_generation_methods": model_info.supported_generation_methods,
                            # Add other relevant fields
                        })
                    except Exception as e:
                         logger.warning(f"Could not get info for known model {model_name}: {e}")


            # Fetch from API
            for model_info in genai.list_models():
                # Filter for models supporting generateContent (chat/text) or embedContent (embeddings)
                 is_chat_model = 'generateContent' in model_info.supported_generation_methods
                 is_embedding_model = 'embedContent' in model_info.supported_generation_methods

                 if not is_chat_model and not is_embedding_model:
                      continue # Skip models not usable for generation or embedding

                 model_id_clean = model_info.name.replace("models/", "")
                 if model_id_clean not in [m['id'] for m in models_list]: # Avoid duplicates
                    models_list.append({
                        "id": model_id_clean,
                        "name": model_info.display_name,
                        "description": model_info.description,
                        "context_window": model_info.input_token_limit,
                        "max_tokens": model_info.output_token_limit,
                        "supported_generation_methods": model_info.supported_generation_methods,
                         # Determine type based on supported methods
                        "model_type": "embedding" if is_embedding_model else "chat" if is_chat_model else "other",
                    })

            return models_list

        try:
            models = self._execute_with_retry(operation_func, "Model Listing")
            print(f"Successfully retrieved {len(models)} usable models from Google AI.")
            return models
        except Exception as e:
            if not isinstance(e, APIException):
                self._handle_api_error("Model Listing", e)
            else:
                raise e

    def health_check(self) -> bool:
        """检查API连接状态"""
        logger.debug("Performing Gemini health check...")
        try:
            # Use list_models as a lightweight health check
            self._ensure_initialized()
            genai.list_models()
            print("Gemini health check successful.")
            return True
        except APIException as e:
            # Log the specific API exception during health check failure
            print(f"Gemini health check failed (APIException): {str(e)} (Code: {e.code})")
            return False
        except Exception as e:
            # Catch any other unexpected exceptions during health check
            print(f"Gemini health check failed with unexpected error: {str(e)}", exc_info=True)
            return False

    def get_provider_name(self) -> str:
        """获取提供商名称"""
        return "Gemini"