"""OpenAI API提供商实现"""
import time
from typing import Dict, Any, List, Optional, Union
import logging

from openai import OpenAI, APIError, RateLimitError, APIConnectionError
from tiktoken import encoding_for_model

from app.infrastructure.llm_providers.base import LLMProviderInterface
from app.core.exceptions import APIException
from app.core.status_codes import OPENAI_API_ERROR, TIMEOUT, RATE_LIMITED

logger = logging.getLogger(__name__)

class OpenLLMProvider(LLMProviderInterface):
    """OpenAI API服务提供商"""
    
    def __init__(self):
        """初始化OpenAI提供商"""
        self.client = None
        self.default_model = "gpt-4o"
        self.embeddings_model = "text-embedding-3-large"
        self.max_retries = 3
        self.retry_delay = 2  # 初始重试延迟（秒）
    
    def initialize(self, api_key: str, **kwargs) -> None:
        """初始化OpenAI客户端
        
        Args:
            api_key: OpenAI API密钥
            **kwargs: 其他初始化参数，可包含:
                      - default_model: 默认模型名称
                      - embeddings_model: 嵌入模型名称
                      - max_retries: 最大重试次数
                      - timeout: 请求超时时间
        """
        try:
            self.client = OpenAI(api_key=api_key)
            
            # 更新可选配置
            self.default_model = kwargs.get("default_model", self.default_model)
            self.embeddings_model = kwargs.get("embeddings_model", self.embeddings_model)
            self.max_retries = kwargs.get("max_retries", self.max_retries)
            
            # 设置超时时间
            timeout = kwargs.get("timeout")
            if timeout:
                self.client.timeout = timeout
                
            logger.info(f"OpenAI Provider initialized with models: {self.default_model} (text), {self.embeddings_model} (embeddings)")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            raise APIException(f"OpenAI初始化失败: {str(e)}", OPENAI_API_ERROR)
    
    def _handle_api_error(self, operation: str, error: Exception) -> None:
        """处理API错误
        
        Args:
            operation: 操作名称
            error: 捕获的异常
            
        Raises:
            APIException: 转换后的API异常
        """
        error_msg = f"OpenAI {operation}失败: {str(error)}"
        logger.error(error_msg)
        
        if isinstance(error, RateLimitError):
            raise APIException(error_msg, RATE_LIMITED, 429)
        elif isinstance(error, APIConnectionError):
            raise APIException(error_msg, TIMEOUT, 503)
        else:
            raise APIException(error_msg, OPENAI_API_ERROR)
    
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
        delay = self.retry_delay
        
        while retry_count <= self.max_retries:
            try:
                return operation_func(*args, **kwargs)
            except (RateLimitError, APIConnectionError) as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    self._handle_api_error(operation_name, e)
                
                # 计算指数退避延迟
                wait_time = delay * (2 ** (retry_count - 1))
                logger.warning(f"OpenAI {operation_name} 失败，正在重试 ({retry_count}/{self.max_retries})，等待 {wait_time}秒")
                time.sleep(wait_time)
            except Exception as e:
                # 其他错误直接失败，不重试
                self._handle_api_error(operation_name, e)
    
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
        """生成文本
        
        Args:
            prompt: 提示词
            max_tokens: 最大生成的token数量
            temperature: 温度参数，控制随机性
            top_p: 核采样参数
            stop_sequences: 停止生成的序列
            model: 使用的模型，默认使用初始化时设置的模型
            **kwargs: 其他参数
            
        Returns:
            包含生成文本及元数据的字典
        """
        if not self.client:
            raise APIException("OpenAI客户端未初始化", OPENAI_API_ERROR)
        
        try:
            def operation_func():
                response = self.client.completions.create(
                    model=model or self.default_model,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stop=stop_sequences,
                    **kwargs
                )
                return {
                    "text": response.choices[0].text,
                    "finish_reason": response.choices[0].finish_reason,
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            
            return self._execute_with_retry(operation_func, "文本生成")
        except Exception as e:
            self._handle_api_error("文本生成", e)
    
    def generate_embeddings(self, texts: List[str], model: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """生成文本嵌入向量
        
        Args:
            texts: 需要生成嵌入的文本列表
            model: 使用的嵌入模型，默认使用初始化时设置的嵌入模型
            **kwargs: 其他参数
            
        Returns:
            包含嵌入向量及元数据的字典
        """
        if not self.client:
            raise APIException("OpenAI客户端未初始化", OPENAI_API_ERROR)
        
        try:
            def operation_func():
                response = self.client.embeddings.create(
                    model=model or self.embeddings_model,
                    input=texts,
                    **kwargs
                )
                
                return {
                    "embeddings": [item.embedding for item in response.data],
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            
            return self._execute_with_retry(operation_func, "嵌入生成")
        except Exception as e:
            self._handle_api_error("嵌入生成", e)
    
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
            messages: 消息历史列表，格式为[{"role": "user/assistant/system", "content": "消息内容"}]
            max_tokens: 最大生成的token数量
            temperature: 温度参数，控制随机性
            top_p: 核采样参数
            stop_sequences: 停止生成的序列
            model: 使用的模型，默认使用初始化时设置的模型
            **kwargs: 其他参数
            
        Returns:
            包含生成回复及元数据的字典
        """
        if not self.client:
            raise APIException("OpenAI客户端未初始化", OPENAI_API_ERROR)
        
        try:
            def operation_func():
                response = self.client.chat.completions.create(
                    model=model or self.default_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stop=stop_sequences,
                    **kwargs
                )
                
                return {
                    "message": {
                        "role": response.choices[0].message.role,
                        "content": response.choices[0].message.content
                    },
                    "finish_reason": response.choices[0].finish_reason,
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            
            return self._execute_with_retry(operation_func, "对话生成")
        except Exception as e:
            self._handle_api_error("对话生成", e)
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """计算文本包含的token数量
        
        Args:
            text: 需要计算token的文本
            model: 使用的模型的编码器，默认使用初始化时设置的模型
            
        Returns:
            token数量
        """
        try:
            encoding = encoding_for_model(model or self.default_model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Token计数失败，使用估算值: {str(e)}")
            # 简单估算: 英文约1.3个token/单词
            return int(len(text.split()) * 1.3)
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表
        
        Returns:
            可用模型信息列表
        """
        if not self.client:
            raise APIException("OpenAI客户端未初始化", OPENAI_API_ERROR)
        
        try:
            def operation_func():
                response = self.client.models.list()
                return [
                    {
                        "id": model.id,
                        "created": model.created,
                        "owned_by": model.owned_by
                    }
                    for model in response.data
                ]
            
            return self._execute_with_retry(operation_func, "获取模型列表")
        except Exception as e:
            self._handle_api_error("获取模型列表", e)
    
    def health_check(self) -> bool:
        """检查API连接状态
        
        Returns:
            连接是否正常
        """
        try:
            # 尝试获取模型列表作为健康检查
            self.get_available_models()
            return True
        except:
            return False
    
    def get_provider_name(self) -> str:
        """获取提供商名称
        
        Returns:
            提供商名称
        """
        return "OpenAI"