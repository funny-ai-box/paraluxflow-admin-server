"""Pinecone向量存储实现"""
import time
import logging
from typing import Dict, Any, List, Optional, Union

import pinecone
from pinecone import Pinecone, PodSpec
from pinecone.core.client.exceptions import ApiException, ServiceException

from app.infrastructure.vector_stores.base import VectorStoreInterface
from app.core.exceptions import APIException
from app.core.status_codes import VECTOR_DB_ERROR, TIMEOUT, RATE_LIMITED

logger = logging.getLogger(__name__)

class PineconeVectorStore(VectorStoreInterface):
    """Pinecone向量存储实现"""
    
    def __init__(self):
        """初始化Pinecone客户端"""
        self.client = None
        self.api_key = None
        self.environment = None
        self.max_retries = 3
        self.retry_delay = 2  # 初始重试延迟（秒）
    
    def initialize(self, api_key: str, environment: str, **kwargs) -> None:
        """初始化Pinecone客户端
        
        Args:
            api_key: Pinecone API密钥
            environment: Pinecone环境
            **kwargs: 其他初始化参数
        """
        try:
            self.api_key = api_key
            self.environment = environment
            
            # 更新可选配置
            self.max_retries = kwargs.get("max_retries", self.max_retries)
            
            # 初始化Pinecone客户端
            self.client = Pinecone(api_key=api_key, environment=environment)
            
            logger.info(f"Pinecone initialized with environment: {environment}")
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {str(e)}")
            raise APIException(f"Pinecone初始化失败: {str(e)}", VECTOR_DB_ERROR)
    
    def _handle_api_error(self, operation: str, error: Exception) -> None:
        """处理API错误
        
        Args:
            operation: 操作名称
            error: 捕获的异常
            
        Raises:
            APIException: 转换后的API异常
        """
        error_msg = f"Pinecone {operation}失败: {str(error)}"
        logger.error(error_msg)
        
        if "rate limit" in str(error).lower():
            raise APIException(error_msg, RATE_LIMITED, 429)
        elif "timeout" in str(error).lower() or "connection" in str(error).lower():
            raise APIException(error_msg, TIMEOUT, 503)
        else:
            raise APIException(error_msg, VECTOR_DB_ERROR)
    
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
        if not self.client:
            raise APIException("Pinecone客户端未初始化", VECTOR_DB_ERROR)
            
        retry_count = 0
        delay = self.retry_delay
        
        while retry_count <= self.max_retries:
            try:
                return operation_func(*args, **kwargs)
            except (ApiException, ServiceException) as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    self._handle_api_error(operation_name, e)
                
                # 计算指数退避延迟
                wait_time = delay * (2 ** (retry_count - 1))
                logger.warning(f"Pinecone {operation_name} 失败，正在重试 ({retry_count}/{self.max_retries})，等待 {wait_time}秒")
                time.sleep(wait_time)
            except Exception as e:
                # 其他错误直接失败，不重试
                self._handle_api_error(operation_name, e)
    
    def create_index(self, index_name: str, dimension: int, **kwargs) -> None:
        """创建索引
        
        Args:
            index_name: 索引名称
            dimension: 向量维度
            **kwargs: 其他创建索引的参数，可包含:
                      - metric: 相似度度量方式，默认"cosine"
                      - pods: Pod数量，默认1
                      - replicas: 副本数量，默认1
                      - pod_type: Pod类型
                      - metadata_config: 元数据配置
        """
        try:
            def operation_func():
                # 检查索引是否已存在
                if index_name in [idx.name for idx in self.client.list_indexes()]:
                    logger.info(f"索引 {index_name} 已存在，跳过创建")
                    return
                
                # 设置索引规范
                metric = kwargs.get("metric", "cosine")
                pods = kwargs.get("pods", 1)
                replicas = kwargs.get("replicas", 1)
                pod_type = kwargs.get("pod_type", "p1.x1")  # 默认最小规格
                
                # 元数据配置
                metadata_config = kwargs.get("metadata_config", None)
                
                # 创建索引
                self.client.create_index(
                    name=index_name,
                    dimension=dimension,
                    metric=metric,
                    spec=PodSpec(
                        environment=self.environment,
                        pod_type=pod_type,
                        pods=pods,
                        replicas=replicas
                    ),
                    metadata_config=metadata_config
                )
                
                # 等待索引就绪
                while not self.client.describe_index(index_name).status.ready:
                    logger.info(f"等待索引 {index_name} 就绪...")
                    time.sleep(5)
                
                logger.info(f"索引 {index_name} 创建成功")
            
            self._execute_with_retry(operation_func, "创建索引")
        except Exception as e:
            self._handle_api_error("创建索引", e)
    
    def delete_index(self, index_name: str) -> None:
        """删除索引
        
        Args:
            index_name: 索引名称
        """
        try:
            def operation_func():
                # 检查索引是否存在
                if index_name not in [idx.name for idx in self.client.list_indexes()]:
                    logger.info(f"索引 {index_name} 不存在，跳过删除")
                    return
                
                # 删除索引
                self.client.delete_index(index_name)
                logger.info(f"索引 {index_name} 已删除")
            
            self._execute_with_retry(operation_func, "删除索引")
        except Exception as e:
            self._handle_api_error("删除索引", e)
    
    def list_indexes(self) -> List[str]:
        """列出所有索引
        
        Returns:
            索引名称列表
        """
        try:
            def operation_func():
                indexes = self.client.list_indexes()
                return [idx.name for idx in indexes]
            
            return self._execute_with_retry(operation_func, "列出索引")
        except Exception as e:
            self._handle_api_error("列出索引", e)
    
    def index_exists(self, index_name: str) -> bool:
        """检查索引是否存在
        
        Args:
            index_name: 索引名称
            
        Returns:
            索引是否存在
        """
        try:
            def operation_func():
                index_list = [idx.name for idx in self.client.list_indexes()]
                return index_name in index_list
            
            return self._execute_with_retry(operation_func, "检查索引")
        except Exception as e:
            self._handle_api_error("检查索引", e)
    
    def _get_index(self, index_name: str):
        """获取索引对象
        
        Args:
            index_name: 索引名称
            
        Returns:
            索引对象
        """
        try:
            # 确保索引存在
            if not self.index_exists(index_name):
                raise APIException(f"索引 {index_name} 不存在", VECTOR_DB_ERROR)
            
            # 获取索引
            return self.client.Index(index_name)
        except Exception as e:
            if isinstance(e, APIException):
                raise
            self._handle_api_error("获取索引", e)
    
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
        try:
            def operation_func():
                index = self._get_index(index_name)
                
                # 准备数据
                items = []
                for i, (vec_id, vector) in enumerate(zip(ids, vectors)):
                    item = {
                        "id": vec_id,
                        "values": vector
                    }
                    
                    # 添加元数据（如果有）
                    if metadata and i < len(metadata):
                        item["metadata"] = metadata[i]
                    
                    items.append(item)
                
                # 批量插入
                batch_size = 100  # 批处理大小
                for i in range(0, len(items), batch_size):
                    batch = items[i:i+batch_size]
                    index.upsert(vectors=batch)
                
                logger.info(f"成功插入 {len(ids)} 条向量到索引 {index_name}")
            
            self._execute_with_retry(operation_func, "插入向量")
        except Exception as e:
            self._handle_api_error("插入向量", e)
    
    def upsert(
        self, 
        index_name: str, 
        vectors: List[List[float]], 
        ids: List[str], 
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """更新或插入向量（与insert相同，因为Pinecone的upsert会自动处理重复ID）
        
        Args:
            index_name: 索引名称
            vectors: 向量列表
            ids: 向量ID列表
            metadata: 元数据列表，可选
        """
        # Pinecone的upsert已经具备更新或插入功能
        self.insert(index_name, vectors, ids, metadata)
    
    def delete(self, index_name: str, ids: List[str]) -> None:
        """删除向量
        
        Args:
            index_name: 索引名称
            ids: 要删除的向量ID列表
        """
        try:
            def operation_func():
                index = self._get_index(index_name)
                
                # 批量删除
                batch_size = 1000  # 批处理大小
                for i in range(0, len(ids), batch_size):
                    batch = ids[i:i+batch_size]
                    index.delete(ids=batch)
                
                logger.info(f"成功从索引 {index_name} 删除 {len(ids)} 条向量")
            
            self._execute_with_retry(operation_func, "删除向量")
        except Exception as e:
            self._handle_api_error("删除向量", e)
    
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
        try:
            def operation_func():
                index = self._get_index(index_name)
                
                # 执行查询
                response = index.query(
                    vector=query_vector,
                    top_k=top_k,
                    include_metadata=True,
                    filter=filter
                )
                
                # 格式化结果
                results = []
                for match in response.matches:
                    result = {
                        "id": match.id,
                        "score": match.score
                    }
                    
                    # 添加元数据（如果有）
                    if hasattr(match, 'metadata') and match.metadata:
                        result["metadata"] = match.metadata
                    
                    results.append(result)
                
                return results
            
            return self._execute_with_retry(operation_func, "搜索向量")
        except Exception as e:
            self._handle_api_error("搜索向量", e)
    
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
        try:
            # 对每个查询向量执行单独的搜索
            results = []
            for query_vector in query_vectors:
                query_result = self.search(
                    index_name=index_name,
                    query_vector=query_vector,
                    top_k=top_k,
                    filter=filter
                )
                results.append(query_result)
            
            return results
        except Exception as e:
            if isinstance(e, APIException):
                raise
            self._handle_api_error("批量搜索向量", e)
    
    def get(self, index_name: str, ids: List[str]) -> List[Dict[str, Any]]:
        """获取指定ID的向量
        
        Args:
            index_name: 索引名称
            ids: 向量ID列表
            
        Returns:
            向量数据列表
        """
        try:
            def operation_func():
                index = self._get_index(index_name)
                
                # 获取向量
                response = index.fetch(ids=ids)
                
                # 格式化结果
                results = []
                for vec_id, vector_data in response.vectors.items():
                    result = {
                        "id": vec_id,
                        "values": vector_data.values
                    }
                    
                    # 添加元数据（如果有）
                    if hasattr(vector_data, 'metadata') and vector_data.metadata:
                        result["metadata"] = vector_data.metadata
                    
                    results.append(result)
                
                return results
            
            return self._execute_with_retry(operation_func, "获取向量")
        except Exception as e:
            self._handle_api_error("获取向量", e)
    
    def count(self, index_name: str, filter: Optional[Dict[str, Any]] = None) -> int:
        """计算索引中的向量数量
        
        Args:
            index_name: 索引名称
            filter: 元数据过滤条件，可选
            
        Returns:
            向量数量
        """
        try:
            def operation_func():
                index = self._get_index(index_name)
                
                # 获取统计信息
                stats = index.describe_index_stats(filter=filter)
                
                # 返回总向量数
                return stats.total_vector_count
            
            return self._execute_with_retry(operation_func, "计数向量")
        except Exception as e:
            self._handle_api_error("计数向量", e)
    
    def health_check(self) -> bool:
        """检查向量存储是否正常工作
        
        Returns:
            是否正常工作
        """
        try:
            # 尝试列出索引作为健康检查
            self.list_indexes()
            return True
        except:
            return False
    
    def get_provider_name(self) -> str:
        """获取提供商名称
        
        Returns:
            提供商名称
        """
        return "Pinecone"