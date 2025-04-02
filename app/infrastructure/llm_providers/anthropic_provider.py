"""Anthropic API提供商实现"""
import time
from typing import Dict, Any, List, Optional, Union
import logging

import anthropic
from anthropic import Anthropic, APIError, RateLimitError

from app.infrastructure.llm_providers.base import LLMProviderInterface
from app.core.exceptions import APIException
from app.core.status_codes import ANTHROPIC_API_ERROR, TIMEOUT, RATE_LIMITED

logger = logging.getLogger(__name__)

class AnthropicProvider(LLMProviderInterface):
    """Anthropic API服务提供商"""
    
    def __init__(self):
        """初始化Anthropic提供商"""
        self.client = None
        self.default_model = "claude-3-opus-20240229"
        self.max_retries = 3
        self.retry_delay = 2  # 初始重试延迟（秒）
    
    def initialize(self, api_key: str, **kwargs) -> None:
        """初始化Anthropic客户端
        
        Args:
            api_key: Anthropic API密钥
            **kwargs: 其他初始化参数，可包含:
                      - default_model: 默认模型名称
                      - max_retries: 最大重试次数
                      - timeout: 请求超时时间
        """
        try:
            self.client = Anthropic(api_key=api_key)
            
            # 更新可选配置
            self.default_model = kwargs.get("default_model", self.default_model)
            self.max_retries = kwargs.get("max_retries", self.max_retries)
            
            # 设置超时时间
            timeout = kwargs.get("timeout")
            if timeout:
                self.client.timeout = timeout
                
            logger.info(f"Anthropic Provider initialized with model: {self.default_model}")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {str(e)}")
            raise APIException(f"Anthropic初始化失败: {str(e)}", ANTHROPIC_API_ERROR)
    
    def _handle_api_error(self, operation: str, error: Exception) -> None:
        """处理API错误
        
        Args:
            operation: 操作名称
            error: 捕获的异常
            
        Raises:
            APIException: 转换后的API异常
        """
        error_msg = f"Anthropic {operation}失败: {str(error)}"
        logger.error(error_msg)
        
        if isinstance(error, RateLimitError):
            raise APIException(error_msg, RATE_LIMITED, 429)
        elif isinstance(error, anthropic.APIConnectionError):
            raise APIException(error_msg, TIMEOUT, 503)
        else:
            raise APIException(error_msg, ANTHROPIC_API_ERROR)
    
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
            except (RateLimitError, anthropic.APIConnectionError) as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    self._handle_api_error(operation_name, e)
                
                # 计算指数退避延迟
                wait_time = delay * (2 ** (retry_count - 1))
                logger.warning(f"Anthropic {operation_name} 失败，正在重试 ({retry_count}/{self.max_retries})，等待 {wait_time}秒")
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
            raise APIException("Anthropic客户端未初始化", ANTHROPIC_API_ERROR)
        
        try:
            # Anthropic只支持通过消息API，转换为单消息格式
            return self.generate_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop_sequences=stop_sequences,
                model=model,
                **kwargs
            )
        except Exception as e:
            self._handle_api_error("文本生成", e)
    
    def generate_embeddings(self, texts: List[str], **kwargs) -> Dict[str, Any]:
        """生成文本嵌入向量
        
        Args:
            texts: 需要生成嵌入的文本列表
            **kwargs: 其他参数
            
        Returns:
            包含嵌入向量及元数据的字典
        """
        # Anthropic目前不提供官方的嵌入API
        raise APIException("Anthropic不支持嵌入向量生成", ANTHROPIC_API_ERROR)
    
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
            raise APIException("Anthropic客户端未初始化", ANTHROPIC_API_ERROR)
        
        try:
            def operation_func():
                system_message = None
                conversation_messages = []
                
                # 处理系统消息
                for msg in messages:
                    if msg["role"] == "system":
                        system_message = msg["content"]
                    else:
                        conversation_messages.append(msg)
                
                response = self.client.messages.create(
                    model=model or self.default_model,
                    messages=conversation_messages,
                    system=system_message,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stop_sequences=stop_sequences,
                    **kwargs
                )
                
                result = {
                    "message": {
                        "role": response.content[0].type,
                        "content": response.content[0].text
                    },
                    "model": response.model,
                    "stop_reason": response.stop_reason,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    }
                }
                
                # 添加总tokens数
                result["usage"]["total_tokens"] = result["usage"]["input_tokens"] + result["usage"]["output_tokens"]
                
                return result
            
            return self._execute_with_retry(operation_func, "对话生成")
        except Exception as e:
            self._handle_api_error("对话生成", e)
    
    def count_tokens(self, text: str) -> int:
        """计算文本包含的token数量
        
        Args:
            text: 需要计算token的文本
            
        Returns:
            token数量
        """
        if not self.client:
            raise APIException("Anthropic客户端未初始化", ANTHROPIC_API_ERROR)
        
        try:
            # 使用Anthropic的token计数API
            return self.client.count_tokens(text)
        except Exception as e:
            logger.warning(f"Token计数失败，使用估算值: {str(e)}")
            # 简单估算: 英文约4个字符/token
            return int(len(text) / 4)
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表
        
        Returns:
            可用模型信息列表
        """
        # Anthropic目前不提供获取模型列表的API，返回固定列表
        return [
            {
                "id": "claude-3-opus-20240229",
                "type": "chat"
            },
            {
                "id": "claude-3-sonnet-20240229",
                "type": "chat"
            },
            {
                "id": "claude-3-haiku-20240307",
                "type": "chat"
            }
        ]
    
    def health_check(self) -> bool:
        """检查API连接状态
        
        Returns:
            连接是否正常
        """
        if not self.client:
            return False
            
        try:
            # 尝试发送一个简单消息作为健康检查
            self.client.messages.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            return True
        except:
            return False
    
    def get_provider_name(self) -> str:
        """获取提供商名称
        
        Returns:
            提供商名称
        """
        return "Anthropic"