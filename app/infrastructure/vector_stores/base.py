"""向量存储基础抽象类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Tuple

class VectorStoreInterface(ABC):
    """向量存储接口"""
    
    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """初始化向量存储
        
        Args:
            **kwargs: 初始化参数，如API密钥、环境等
        """
        pass
    
    @abstractmethod
    def create_index(self, index_name: str, dimension: int, **kwargs) -> None:
        """创建索引
        
        Args:
            index_name: 索引名称
            dimension: 向量维度
            **kwargs: 其他创建索引的参数
        """
        pass
    
    @abstractmethod
    def delete_index(self, index_name: str) -> None:
        """删除索引
        
        Args:
            index_name: 索引名称
        """
        pass
    
    @abstractmethod
    def list_indexes(self) -> List[str]:
        """列出所有索引
        
        Returns:
            索引名称列表
        """
        pass
    
    @abstractmethod
    def index_exists(self, index_name: str) -> bool:
        """检查索引是否存在
        
        Args:
            index_name: 索引名称
            
        Returns:
            索引是否存在
        """
        pass
    
    @abstractmethod
    def insert(
        self, 
        index_name: str, 
        vectors: List[List[float]], 
        ids: List[str], 
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """插入向量
        
        Args:
            index_name: 索引名称
            vectors: 向量列表
            ids: 向量ID列表
            metadata: 元数据列表，可选
        """
        pass
    
    @abstractmethod
    def upsert(
        self, 
        index_name: str, 
        vectors: List[List[float]], 
        ids: List[str], 
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """更新或插入向量
        
        Args:
            index_name: 索引名称
            vectors: 向量列表
            ids: 向量ID列表
            metadata: 元数据列表，可选
        """
        pass
    
    @abstractmethod
    def delete(self, index_name: str, ids: List[str]) -> None:
        """删除向量
        
        Args:
            index_name: 索引名称
            ids: 要删除的向量ID列表
        """
        pass
    
    @abstractmethod
    def search(
        self, 
        index_name: str, 
        query_vector: List[float], 
        top_k: int = 10, 
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """搜索向量
        
        Args:
            index_name: 索引名称
            query_vector: 查询向量
            top_k: 返回结果数量
            filter: 元数据过滤条件，可选
            
        Returns:
            搜索结果列表，包含ID、分数和元数据
        """
        pass
    
    @abstractmethod
    def batch_search(
        self, 
        index_name: str, 
        query_vectors: List[List[float]], 
        top_k: int = 10, 
        filter: Optional[Dict[str, Any]] = None
    ) -> List[List[Dict[str, Any]]]:
        """批量搜索向量
        
        Args:
            index_name: 索引名称
            query_vectors: 查询向量列表
            top_k: 每个查询返回结果数量
            filter: 元数据过滤条件，可选
            
        Returns:
            搜索结果列表的列表
        """
        pass
    
    @abstractmethod
    def get(self, index_name: str, ids: List[str]) -> List[Dict[str, Any]]:
        """获取指定ID的向量
        
        Args:
            index_name: 索引名称
            ids: 向量ID列表
            
        Returns:
            向量数据列表
        """
        pass
    
    @abstractmethod
    def count(self, index_name: str, filter: Optional[Dict[str, Any]] = None) -> int:
        """计算索引中的向量数量
        
        Args:
            index_name: 索引名称
            filter: 元数据过滤条件，可选
            
        Returns:
            向量数量
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """检查向量存储是否正常工作
        
        Returns:
            是否正常工作
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """获取提供商名称
        
        Returns:
            提供商名称
        """
        pass