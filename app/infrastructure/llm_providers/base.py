"""AI供应商基础抽象类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union

class LLMProviderInterface(ABC):
    """AI模型提供商接口"""
    
    @abstractmethod
    def initialize(self, api_key: str, **kwargs) -> None:
        """初始化AI提供商客户端
        
        Args:
            api_key: API密钥
            **kwargs: 其他初始化参数
        """
        pass
    
    @abstractmethod
    def generate_text(
        self, 
        prompt: str, 
        max_tokens: int = 1000,
        temperature: float = 0.7, 
        top_p: float = 1.0,
        stop_sequences: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成文本
        
        Args:
            prompt: 提示词
            max_tokens: 最大生成的token数量
            temperature: 温度参数，控制随机性
            top_p: 核采样参数
            stop_sequences: 停止生成的序列
            **kwargs: 其他参数
            
        Returns:
            包含生成文本及元数据的字典
        """
        pass
    
    @abstractmethod
    def generate_embeddings(self, texts: List[str], **kwargs) -> Dict[str, Any]:
        """生成文本嵌入向量
        
        Args:
            texts: 需要生成嵌入的文本列表
            **kwargs: 其他参数
            
        Returns:
            包含嵌入向量及元数据的字典
        """
        pass
    
    @abstractmethod
    def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 1.0,
        stop_sequences: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """生成对话完成
        
        Args:
            messages: 消息历史列表，格式为[{"role": "user/assistant/system", "content": "消息内容"}]
            max_tokens: 最大生成的token数量
            temperature: 温度参数，控制随机性
            top_p: 核采样参数
            stop_sequences: 停止生成的序列
            **kwargs: 其他参数
            
        Returns:
            包含生成回复及元数据的字典
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """计算文本包含的token数量
        
        Args:
            text: 需要计算token的文本
            
        Returns:
            token数量
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取可用模型列表
        
        Returns:
            可用模型信息列表
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """检查API连接状态
        
        Returns:
            连接是否正常
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """获取提供商名称
        
        Returns:
            提供商名称
        """
        pass