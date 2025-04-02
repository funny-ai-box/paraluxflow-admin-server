"""火山引擎API提供商实现"""
# 需要安装: pip install --upgrade "volcengine-python-sdk[ark]"
import time
import json
import logging
from typing import Dict, Any, List, Optional

from volcenginesdkarkruntime import Ark
import httpx
from openai import OpenAI
from app.infrastructure.llm_providers.base import LLMProviderInterface
from app.core.exceptions import APIException
from app.core.status_codes import EXTERNAL_API_ERROR, TIMEOUT, RATE_LIMITED

logger = logging.getLogger(__name__)

class VolcanoProvider(LLMProviderInterface):
    """火山引擎API服务提供商"""
    
    def __init__(self):
        """初始化火山引擎提供商"""
        self.client = None
        self.default_model = "deepseek-r1-250120"
        self.max_retries = 3
        self.retry_delay = 2  # 初始重试延迟（秒）
    
    def initialize(self, api_key: str, **kwargs) -> None:
        """初始化火山引擎客户端
        
        Args:
            api_key: 火山引擎API密钥
            **kwargs: 其他初始化参数，可包含:
                      - app_id: 应用ID
                      - app_secret: 应用密钥
                      - default_model: 默认模型名称
                      - max_retries: 最大重试次数
                      - timeout: 请求超时时间
        """
        try:
            # 更新可选配置
            self.default_model = kwargs.get("default_model", self.default_model)
            self.max_retries = kwargs.get("max_retries", self.max_retries)
            
            # 设置超时时间
            timeout_seconds = kwargs.get("timeout", 300)
            print(f"设置超时时间为 {timeout_seconds} 秒")
            print(f"默认模型为 {self.default_model}")
            print(f"api_key为 {api_key}")
            # 初始化客户端
            # 如果提供了app_id和app_secret，则使用IAM认证
            self.client = OpenAI(
                    api_key=api_key,
                    base_url = "https://ark.cn-beijing.volces.com/api/v3",
                )
            print(f"火山引擎客户端初始化成功")
            logger.info(f"火山引擎初始化成功: {self.default_model}")
        except Exception as e:
            logger.error(f"失败初始化火山引擎: {str(e)}")
            raise APIException(f"火山引擎初始化失败: {str(e)}", EXTERNAL_API_ERROR)
    
    def _handle_api_error(self, operation: str, error: Exception) -> None:
        """处理API错误
        
        Args:
            operation: 操作名称
            error: 捕获的异常
            
        Raises:
            APIException: 转换后的API异常
        """
        error_msg = f"火山引擎 {operation}失败: {str(error)}"
        logger.error(error_msg)
        
        if "rate limit" in str(error).lower():
            raise APIException(error_msg, RATE_LIMITED, 429)
        elif "timeout" in str(error).lower() or "connection" in str(error).lower():
            raise APIException(error_msg, TIMEOUT, 503)
        else:
            raise APIException(error_msg, EXTERNAL_API_ERROR)
    
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
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    self._handle_api_error(operation_name, e)
                
                # 计算指数退避延迟
                wait_time = delay * (2 ** (retry_count - 1))
                logger.warning(f"火山引擎 {operation_name} 失败，正在重试 ({retry_count}/{self.max_retries})，等待 {wait_time}秒")
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
        # 火山引擎只支持通过消息API，转换为单消息格式
        return self.generate_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_sequences=stop_sequences,
            model=model,
            **kwargs
        )
    
    def generate_embeddings(self, texts: List[str], **kwargs) -> Dict[str, Any]:
        """生成文本嵌入向量
        
        Args:
            texts: 需要生成嵌入的文本列表
            **kwargs: 其他参数
            
        Returns:
            包含嵌入向量及元数据的字典
        """
        # 目前不支持，未来可以实现
        raise APIException("火山引擎尚不支持嵌入向量生成", EXTERNAL_API_ERROR)
    
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
            raise APIException("火山引擎客户端未初始化", EXTERNAL_API_ERROR)
        
        try:
            def operation_func():
                used_model = model or self.default_model
                
                # 构建请求参数
                params = {
                    "model": used_model,
                    "messages": messages,
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens
                }
                
                if stop_sequences:
                    params["stop"] = stop_sequences
                
                # 添加其他参数
                for key, value in kwargs.items():
                    if key not in params:
                        params[key] = value
                
                print(f"发送到火山引擎的请求参数:")
                print(f"- 模型: {params['model']}")
                print(f"- 消息数量: {len(params['messages'])}")
                print(f"- 温度: {params['temperature']}")
                print(f"- 最大tokens: {params['max_tokens']}")
                
                # 发送请求
                print("开始调用火山引擎API...")
                response = self.client.chat.completions.create(**params)
                print(response)
                print("API调用成功!")
                
                # 构造统一格式的返回结果
                result = {
                    "message": {
                        "role": "assistant", 
                        "content": response.choices[0].message.content
                    },
                    "model": used_model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0,
                        "completion_tokens": response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0,
                        "total_tokens": response.usage.total_tokens if hasattr(response.usage, 'total_tokens') else 0
                    }
                }
                
                # 添加reasoning_content（如果有）
                if hasattr(response.choices[0].message, 'reasoning_content') and response.choices[0].message.reasoning_content:
                    result["reasoning_content"] = response.choices[0].message.reasoning_content
                
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
        # 火山引擎没有官方的计数方法，使用估算
        # 简单估算: 汉字约1个token/字，英文约1.5个token/单词
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        english_words = len([word for word in text.split() if all(c.isascii() for c in word)])
        
        return chinese_chars + int(english_words * 1.5)
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表
        
        Returns:
            可用模型信息列表
        """
        # 返回硬编码的模型列表
        return [
            {
                "id": "deepseek-r1-250120",
                "type": "chat"
            },
            {
                "id": "deepseek-coder",
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
            self.generate_chat_completion(
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
        return "Volcano"