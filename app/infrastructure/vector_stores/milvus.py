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
        if auto_load:
            try:
                # 尝试获取集合加载状态
                loaded = collection.is_loaded
                if not loaded:
                    collection.load()
                    logger.info(f"集合 {index_name} 已加载")
            except Exception as e:
                # 如果无法检查加载状态，直接尝试加载
                logger.warning(f"无法检查集合加载状态，尝试直接加载: {str(e)}")
                try:
                    collection.load()
                except Exception as load_err:
                    logger.warning(f"加载集合异常，可能已经加载: {str(load_err)}")
        
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
                    - fields: 额外字段定义
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
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
                FieldSchema(name="metadata", dtype=DataType.JSON)
            ]
            
            # 添加自定义字段
            custom_fields = kwargs.get("fields", [])
            added_fields = set([f.name for f in fields])
            
            if custom_fields:
                # 处理额外字段
                for field_def in custom_fields:
                    field_name = field_def.get("name")
                    if not field_name or field_name in added_fields:
                        continue  # 跳过没有名称或已存在的字段
                    
                    field_type = field_def.get("type", "VARCHAR")
                    params = field_def.get("params", {})
                    
                    logger.info(f"添加字段: {field_name}, 类型: {field_type}, 参数: {params}")
                    
                    if field_type == "INT64":
                        fields.append(FieldSchema(name=field_name, dtype=DataType.INT64))
                        added_fields.add(field_name)
                        
                    elif field_type == "VARCHAR":
                        max_length = params.get("max_length", 500)
                        fields.append(FieldSchema(name=field_name, dtype=DataType.VARCHAR, max_length=max_length))
                        added_fields.add(field_name)
                        
                    elif field_type == "JSON":
                        fields.append(FieldSchema(name=field_name, dtype=DataType.JSON))
                        added_fields.add(field_name)
                        
                    elif field_type == "FLOAT":
                        fields.append(FieldSchema(name=field_name, dtype=DataType.FLOAT))
                        added_fields.add(field_name)
                        
                    elif field_type == "BOOL":
                        fields.append(FieldSchema(name=field_name, dtype=DataType.BOOL))
                        added_fields.add(field_name)
                    else:
                        logger.warning(f"不支持的字段类型: {field_type}, 字段: {field_name}")
            
            logger.info(f"正在创建集合 {index_name} 包含 {len(fields)} 个字段")
            
            # 创建集合模式
            schema = CollectionSchema(fields=fields, description=description)
            
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
            # 记录更详细的错误信息
            logger.exception("索引创建详细错误")
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
            
            # 转换元数据为JSON字符串 (根据版本可能不需要)
            metadata_json = []
            for m in metadata:
                if m is None:
                    metadata_json.append(None)
                else:
                    metadata_json.append(m)
            
            # 插入数据
            data = [ids, vectors, metadata_json]
            collection.insert(data)
            
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
                try:
                    results = collection.query(expr=expr, output_fields=["id"])
                    existing_ids.extend([r["id"] for r in results])
                except Exception as query_err:
                    logger.warning(f"查询ID存在性失败，将尝试直接插入: {str(query_err)}")
            
            # 删除存在的ID
            if existing_ids:
                try:
                    self.delete(index_name, existing_ids)
                except Exception as del_err:
                    logger.warning(f"删除现有向量失败，将尝试直接插入: {str(del_err)}")
            
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
                    # 处理不同类型的值
                    if isinstance(value, str):
                        expr_parts.append(f'{key} == "{value}"')
                    elif isinstance(value, (int, float, bool)):
                        expr_parts.append(f'{key} == {value}')
                    else:
                        logger.warning(f"不支持的过滤值类型: {type(value)}")
                
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
                    metadata = {}
                    try:
                        # 尝试获取元数据
                        raw_metadata = hit.entity.get('metadata')
                        if isinstance(raw_metadata, dict):
                            metadata = raw_metadata
                        elif isinstance(raw_metadata, str) and raw_metadata:
                            metadata = json.loads(raw_metadata)
                    except Exception as metadata_err:
                        logger.warning(f"解析元数据失败: {str(metadata_err)}")
                    
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
                    # 处理不同类型的值
                    if isinstance(value, str):
                        expr_parts.append(f'{key} == "{value}"')
                    elif isinstance(value, (int, float, bool)):
                        expr_parts.append(f'{key} == {value}')
                    else:
                        logger.warning(f"不支持的过滤值类型: {type(value)}")
                
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
                    metadata = {}
                    try:
                        # 尝试获取元数据
                        raw_metadata = hit.entity.get('metadata')
                        if isinstance(raw_metadata, dict):
                            metadata = raw_metadata
                        elif isinstance(raw_metadata, str) and raw_metadata:
                            metadata = json.loads(raw_metadata)
                    except Exception as metadata_err:
                        logger.warning(f"解析元数据失败: {str(metadata_err)}")
                    
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
                metadata = {}
                try:
                    # 尝试获取元数据
                    raw_metadata = item.get('metadata')
                    if isinstance(raw_metadata, dict):
                        metadata = raw_metadata
                    elif isinstance(raw_metadata, str) and raw_metadata:
                        metadata = json.loads(raw_metadata)
                except Exception as metadata_err:
                    logger.warning(f"解析元数据失败: {str(metadata_err)}")
                
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
                    # 处理不同类型的值
                    if isinstance(value, str):
                        expr_parts.append(f'{key} == "{value}"')
                    elif isinstance(value, (int, float, bool)):
                        expr_parts.append(f'{key} == {value}')
                    else:
                        logger.warning(f"不支持的过滤值类型: {type(value)}")
                
                if expr_parts:
                    expr = " && ".join(expr_parts)
            
            # 获取数量
            if expr:
                try:
                    # 尝试使用count(*)函数
                    count_result = collection.query(expr=expr, output_fields=["count(*)"])
                    if count_result and "count(*)" in count_result[0]:
                        return count_result[0]["count(*)"]
                    else:
                        # 回退方法：获取所有ID然后计数
                        id_results = collection.query(expr=expr, output_fields=["id"])
                        return len(id_results)
                except Exception as count_err:
                    logger.warning(f"查询计数失败，使用实体数量: {str(count_err)}")
                    return collection.num_entities
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