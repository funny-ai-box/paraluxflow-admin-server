# app/infrastructure/vector_stores/milvus.py
"""Milvus向量存储实现"""
import logging
import os
from typing import Dict, List, Any, Optional, Union, Tuple
import json
import time

# 导入Milvus客户端
from pymilvus import (
    connections,
    utility,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
)

from app.infrastructure.vector_stores.base import VectorStoreInterface
from app.core.exceptions import APIException
from app.core.status_codes import VECTOR_DB_ERROR

logger = logging.getLogger(__name__)

class MilvusVectorStore(VectorStoreInterface):
    """Milvus向量存储实现"""
    
    def __init__(self):
        """初始化Milvus向量存储"""
        self.initialized = False
        self.host = "localhost"
        self.port = "19530"
        self.collections = {}  # 缓存已加载的集合
        self.alias = "default"
        self.timeout = 60  # 连接超时时间（秒）
    
    def initialize(self, **kwargs) -> None:
        """初始化向量存储
        
        Args:
            **kwargs: 初始化参数，支持：
                    - host: Milvus服务器地址
                    - port: Milvus服务器端口
                    - user: 用户名（可选）
                    - password: 密码（可选）
                    - timeout: 连接超时时间（可选）
                    - alias: 连接别名（可选）
        """
        try:
            # 获取配置参数
            self.host = kwargs.get("host", os.environ.get("MILVUS_HOST", "localhost"))
            self.port = kwargs.get("port", os.environ.get("MILVUS_PORT", "19530"))
            self.alias = kwargs.get("alias", "default")
            self.timeout = kwargs.get("timeout", 60)
            
            # 可选参数
            user = kwargs.get("user")
            password = kwargs.get("password")
            secure = kwargs.get("secure", False)
            
            # 连接参数
            conn_params = {
                "host": self.host,
                "port": self.port
            }
            
            # 如果提供了认证信息
            if user and password:
                conn_params["user"] = user
                conn_params["password"] = password
                
            if secure:
                conn_params["secure"] = True
            
            # 连接Milvus服务器
            connections.connect(alias=self.alias, **conn_params)
            logger.info(f"成功连接到Milvus服务器 {self.host}:{self.port}")
            
            self.initialized = True
        except Exception as e:
            logger.error(f"连接Milvus服务器失败: {str(e)}")
            raise APIException(f"Milvus初始化失败: {str(e)}", VECTOR_DB_ERROR)
    
    def _ensure_initialized(self):
        """确保已初始化"""
        if not self.initialized:
            raise APIException("Milvus存储未初始化", VECTOR_DB_ERROR)
    
    def _get_collection(self, index_name: str, auto_load: bool = True) -> Collection:
        """获取集合对象
        
        Args:
            index_name: 索引/集合名称
            auto_load: 是否自动加载集合
            
        Returns:
            Collection对象
            
        Raises:
            APIException: 集合不存在时抛出异常
        """
        self._ensure_initialized()
        
        # 检查是否已缓存
        if index_name in self.collections:
            return self.collections[index_name]
        
        # 检查集合是否存在
        if not utility.has_collection(index_name, using=self.alias):
            raise APIException(f"集合 {index_name} 不存在", VECTOR_DB_ERROR)
        
        # 获取集合
        collection = Collection(name=index_name, using=self.alias)
        
        # 自动加载
        if auto_load and not utility.has_collection_loaded(index_name, using=self.alias):
            collection.load()
        
        # 缓存集合
        self.collections[index_name] = collection
        
        return collection
    
    def create_index(self, index_name: str, dimension: int, **kwargs) -> None:
        """创建索引
        
        Args:
            index_name: 索引名称
            dimension: 向量维度
            **kwargs: 其他创建索引的参数，支持：
                    - description: 集合描述
                    - metric_type: 相似度度量类型，默认为COSINE
                    - index_type: 索引类型，默认为HNSW
                    - index_params: 索引参数，默认为{"M": 8, "efConstruction": 64}
                    - fields: 额外字段定义列表，每个字段为字典，包含name、type和params
        """
        self._ensure_initialized()
        
        # 检查集合是否已存在
        if utility.has_collection(index_name, using=self.alias):
            logger.info(f"集合 {index_name} 已存在，跳过创建")
            return
        
        try:
            # 获取参数
            description = kwargs.get("description", f"向量集合 {index_name}")
            metric_type = kwargs.get("metric_type", "COSINE")
            index_type = kwargs.get("index_type", "HNSW")
            index_params = kwargs.get("index_params", {"M": 8, "efConstruction": 64})
            
            # 默认字段
            field_list = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
                FieldSchema(name="metadata", dtype=DataType.JSON)
            ]
            
            # 添加自定义字段
            custom_fields = kwargs.get("fields", [])
            if custom_fields:
                for field in custom_fields:
                    if not isinstance(field, FieldSchema):
                        # 从字典转换为FieldSchema对象
                        field_name = field.get("name")
                        field_type = field.get("type", "VARCHAR")
                        
                        # 确定数据类型
                        data_type = None
                        if field_type == "INT64" or field_type == "INTEGER":
                            data_type = DataType.INT64
                        elif field_type == "FLOAT":
                            data_type = DataType.FLOAT
                        elif field_type == "DOUBLE":
                            data_type = DataType.DOUBLE
                        elif field_type == "BOOLEAN":
                            data_type = DataType.BOOL
                        elif field_type == "VARCHAR" or field_type == "STRING":
                            data_type = DataType.VARCHAR
                            
                        # 创建字段模式
                        if data_type is not None:
                            field_params = field.get("params", {})
                            if data_type == DataType.VARCHAR and "max_length" in field_params:
                                field_obj = FieldSchema(
                                    name=field_name, 
                                    dtype=data_type,
                                    max_length=field_params.get("max_length", 100)
                                )
                            else:
                                field_obj = FieldSchema(name=field_name, dtype=data_type)
                            
                            field_list.append(field_obj)
            
            # 创建集合模式
            schema = CollectionSchema(fields=field_list, description=description)
            
            # 创建集合
            collection = Collection(name=index_name, schema=schema, using=self.alias)
            
            # 创建索引
            index_params = {
                "metric_type": metric_type,
                "index_type": index_type,
                "params": index_params
            }
            collection.create_index(field_name="vector", index_params=index_params)
            
            # 加载集合
            collection.load()
            
            # 缓存集合
            self.collections[index_name] = collection
            
            logger.info(f"集合 {index_name} 创建并加载成功")
        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")
            raise APIException(f"创建Milvus索引失败: {str(e)}", VECTOR_DB_ERROR)
    
    def delete_index(self, index_name: str) -> None:
        """删除索引
        
        Args:
            index_name: 索引名称
        """
        self._ensure_initialized()
        
        try:
            # 检查集合是否存在
            if utility.has_collection(index_name, using=self.alias):
                # 删除集合
                utility.drop_collection(index_name, using=self.alias)
                
                # 从缓存中移除
                if index_name in self.collections:
                    del self.collections[index_name]
                
                logger.info(f"集合 {index_name} 已删除")
            else:
                logger.warning(f"尝试删除不存在的集合 {index_name}")
        except Exception as e:
            logger.error(f"删除索引失败: {str(e)}")
            raise APIException(f"删除Milvus索引失败: {str(e)}", VECTOR_DB_ERROR)
    
    def list_indexes(self) -> List[str]:
        """列出所有索引
        
        Returns:
            索引名称列表
        """
        self._ensure_initialized()
        
        try:
            # 获取所有集合
            collections = utility.list_collections(using=self.alias)
            return collections
        except Exception as e:
            logger.error(f"列出索引失败: {str(e)}")
            raise APIException(f"列出Milvus索引失败: {str(e)}", VECTOR_DB_ERROR)
    
    def index_exists(self, index_name: str) -> bool:
        """检查索引是否存在
        
        Args:
            index_name: 索引名称
            
        Returns:
            索引是否存在
        """
        self._ensure_initialized()
        
        try:
            return utility.has_collection(index_name, using=self.alias)
        except Exception as e:
            logger.error(f"检查索引存在失败: {str(e)}")
            return False
    
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
        self._ensure_initialized()
        
        try:
            # 获取集合
            collection = self._get_collection(index_name)
            
            # 准备插入数据
            if len(vectors) != len(ids):
                raise APIException("向量数量和ID数量不匹配", VECTOR_DB_ERROR)
            
            # 准备元数据
            if metadata is None:
                metadata = [{} for _ in range(len(ids))]
            elif len(metadata) != len(ids):
                raise APIException("元数据数量和ID数量不匹配", VECTOR_DB_ERROR)
            
            # 转换元数据为JSON字符串
            metadata_json = [json.dumps(m) if m else "{}" for m in metadata]
            
            # 插入数据
            entities = [ids, vectors, metadata_json]
            collection.insert(entities)
            
            logger.info(f"成功向集合 {index_name} 插入 {len(ids)} 条向量")
        except Exception as e:
            logger.error(f"插入向量失败: {str(e)}")
            raise APIException(f"插入Milvus向量失败: {str(e)}", VECTOR_DB_ERROR)
    
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
        self._ensure_initialized()
        
        try:
            # 获取集合
            collection = self._get_collection(index_name)
            
            # Milvus不直接支持upsert，需要先删除再插入
            # 先查询ID是否存在
            existing_ids = []
            for id_batch in [ids[i:i+100] for i in range(0, len(ids), 100)]:
                expr = f"id in {id_batch}"
                results = collection.query(expr=expr, output_fields=["id"])
                existing_ids.extend([r["id"] for r in results])
            
            # 删除存在的ID
            if existing_ids:
                self.delete(index_name, existing_ids)
            
            # 插入新数据
            self.insert(index_name, vectors, ids, metadata)
            
            logger.info(f"成功更新集合 {index_name} 中的 {len(ids)} 条向量")
        except Exception as e:
            logger.error(f"更新向量失败: {str(e)}")
            raise APIException(f"更新Milvus向量失败: {str(e)}", VECTOR_DB_ERROR)
    
    def delete(self, index_name: str, ids: List[str]) -> None:
        """删除向量
        
        Args:
            index_name: 索引名称
            ids: 要删除的向量ID列表
        """
        self._ensure_initialized()
        
        try:
            # 获取集合
            collection = self._get_collection(index_name)
            
            # 删除数据
            expr = f'id in {ids}'
            collection.delete(expr=expr)
            
            logger.info(f"成功从集合 {index_name} 删除 {len(ids)} 条向量")
        except Exception as e:
            logger.error(f"删除向量失败: {str(e)}")
            raise APIException(f"删除Milvus向量失败: {str(e)}", VECTOR_DB_ERROR)
    
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
        self._ensure_initialized()
        
        try:
            # 获取集合
            collection = self._get_collection(index_name)
            
            # 搜索参数
            search_params = {
                "metric_type": "COSINE",  # 可扩展为参数
                "params": {"ef": 64}
            }
            
            # 构建过滤表达式
            expr = None
            if filter:
                # 简单过滤条件支持
                expr_parts = []
                for key, value in filter.items():
                    # 处理JSON字段中的属性查询
                    expr_parts.append(f'metadata["{key}"] == "{value}"')
                
                if expr_parts:
                    expr = " && ".join(expr_parts)
            
            # 执行搜索
            results = collection.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["metadata"]
            )
            
            # 处理结果
            search_results = []
            for hits in results:
                for hit in hits:
                    # 解析元数据
                    try:
                        metadata = json.loads(hit.entity.get('metadata', '{}'))
                    except:
                        metadata = {}
                    
                    search_results.append({
                        "id": hit.id,
                        "score": hit.distance,
                        "metadata": metadata
                    })
            
            return search_results
        except Exception as e:
            logger.error(f"搜索向量失败: {str(e)}")
            raise APIException(f"搜索Milvus向量失败: {str(e)}", VECTOR_DB_ERROR)
    
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
        self._ensure_initialized()
        
        try:
            # 获取集合
            collection = self._get_collection(index_name)
            
            # 搜索参数
            search_params = {
                "metric_type": "COSINE",  # 可扩展为参数
                "params": {"ef": 64}
            }
            
            # 构建过滤表达式
            expr = None
            if filter:
                # 简单过滤条件支持
                expr_parts = []
                for key, value in filter.items():
                    # 处理JSON字段中的属性查询
                    expr_parts.append(f'metadata["{key}"] == "{value}"')
                
                if expr_parts:
                    expr = " && ".join(expr_parts)
            
            # 执行搜索
            results = collection.search(
                data=query_vectors,
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["metadata"]
            )
            
            # 处理结果
            batch_results = []
            for hits in results:
                search_results = []
                for hit in hits:
                    # 解析元数据
                    try:
                        metadata = json.loads(hit.entity.get('metadata', '{}'))
                    except:
                        metadata = {}
                    
                    search_results.append({
                        "id": hit.id,
                        "score": hit.distance,
                        "metadata": metadata
                    })
                batch_results.append(search_results)
            
            return batch_results
        except Exception as e:
            logger.error(f"批量搜索向量失败: {str(e)}")
            raise APIException(f"批量搜索Milvus向量失败: {str(e)}", VECTOR_DB_ERROR)
    
    def get(self, index_name: str, ids: List[str]) -> List[Dict[str, Any]]:
        """获取指定ID的向量
        
        Args:
            index_name: 索引名称
            ids: 向量ID列表
            
        Returns:
            向量数据列表
        """
        self._ensure_initialized()
        
        try:
            # 获取集合
            collection = self._get_collection(index_name)
            
            # 构建查询表达式
            expr = f'id in {ids}'
            
            # 执行查询
            results = collection.query(
                expr=expr,
                output_fields=["id", "vector", "metadata"]
            )
            
            # 处理结果
            vector_data = []
            for item in results:
                # 解析元数据
                try:
                    metadata = json.loads(item.get('metadata', '{}'))
                except:
                    metadata = {}
                
                vector_data.append({
                    "id": item["id"],
                    "vector": item["vector"],
                    "metadata": metadata
                })
            
            return vector_data
        except Exception as e:
            logger.error(f"获取向量失败: {str(e)}")
            raise APIException(f"获取Milvus向量失败: {str(e)}", VECTOR_DB_ERROR)
    
    def count(self, index_name: str, filter: Optional[Dict[str, Any]] = None) -> int:
        """计算索引中的向量数量
        
        Args:
            index_name: 索引名称
            filter: 元数据过滤条件，可选
            
        Returns:
            向量数量
        """
        self._ensure_initialized()
        
        try:
            # 获取集合
            collection = self._get_collection(index_name)
            
            # 构建过滤表达式
            expr = None
            if filter:
                # 简单过滤条件支持
                expr_parts = []
                for key, value in filter.items():
                    # 处理JSON字段中的属性查询
                    expr_parts.append(f'metadata["{key}"] == "{value}"')
                
                if expr_parts:
                    expr = " && ".join(expr_parts)
            
            # 获取数量
            if expr:
                count = collection.query(expr=expr, output_fields=["count(*)"])[0]["count(*)"]
                return count
            else:
                return collection.num_entities
        except Exception as e:
            logger.error(f"获取向量数量失败: {str(e)}")
            raise APIException(f"获取Milvus向量数量失败: {str(e)}", VECTOR_DB_ERROR)
    
    def health_check(self) -> bool:
        """检查向量存储是否正常工作
        
        Returns:
            是否正常工作
        """
        if not self.initialized:
            return False
        
        try:
            # 测试连接
            collections = utility.list_collections(using=self.alias)
            return True
        except:
            return False
    
    def get_provider_name(self) -> str:
        """获取提供商名称
        
        Returns:
            提供商名称
        """
        return "Milvus"