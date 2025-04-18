# app/infrastructure/vector_stores/factory.py
"""向量存储工厂模块，负责创建和管理向量存储实例"""
import logging
from typing import Dict, Any, Optional

from app.infrastructure.vector_stores.base import VectorStoreInterface

from app.infrastructure.vector_stores.milvus import MilvusVectorStore

from app.core.exceptions import APIException
from app.core.status_codes import VECTOR_DB_ERROR

logger = logging.getLogger(__name__)

class VectorStoreFactory:
    """向量存储工厂类，负责创建和管理向量存储实例"""
    
    # 支持的存储提供商映射
    STORES = {

        "milvus": MilvusVectorStore,

    }
    
    @classmethod
    def create_store(cls, store_name: str, **config) -> VectorStoreInterface:
        """创建向量存储实例
        
        Args:
            store_name: 存储名称，如"pinecone"、"milvus"
            **config: 配置参数，不同的存储可能需要不同的配置
            
        Returns:
            初始化好的向量存储实例
            
        Raises:
            APIException: 如果存储不支持或初始化失败
        """
        store_name = store_name.lower()
        
        if store_name not in cls.STORES:
            logger.error(f"Unsupported vector store: {store_name}")
            raise APIException(
                f"不支持的向量存储: {store_name}，支持的存储: {', '.join(cls.STORES.keys())}", 
                VECTOR_DB_ERROR
            )
        
        try:
            # 创建存储实例
            store = cls.STORES[store_name]()
            
            # 初始化存储
            store.initialize(**config)
            
            logger.info(f"Successfully created and initialized {store_name} vector store")
            return store
        except Exception as e:
            logger.error(f"Failed to create {store_name} vector store: {str(e)}")
            if isinstance(e, APIException):
                raise
            raise APIException(f"创建向量存储失败: {str(e)}", VECTOR_DB_ERROR)
    
    @classmethod
    def get_available_stores(cls) -> Dict[str, Dict[str, Any]]:
        """获取所有可用的向量存储信息
        
        Returns:
            存储信息字典，键为存储名称，值为存储描述
        """
        return {
  
            "milvus": {
                "name": "Milvus",
                "description": "Milvus是一个开源向量数据库，专为多样化向量相似度搜索设计",
                "features": ["插入向量", "查询向量", "过滤搜索", "元数据存储", "集合管理"],
                "configuration": {
                    "host": "Milvus服务器地址",
                    "port": "Milvus服务器端口",
                    "user": "用户名（可选）",
                    "password": "密码（可选）"
                }
            }

        }