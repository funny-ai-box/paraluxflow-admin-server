"""Redis缓存实现"""
import json
import logging
import pickle
from typing import Any, Dict, List, Optional, Union, Tuple, Set

import redis
from redis.exceptions import ConnectionError, RedisError

from app.infrastructure.cache.base import CacheInterface
from app.core.exceptions import APIException
from app.core.status_codes import EXTERNAL_API_ERROR

logger = logging.getLogger(__name__)

class RedisCache(CacheInterface):
    """Redis缓存实现"""
    
    SERIALIZATION_METHODS = ["json", "pickle"]
    
    def __init__(self):
        """初始化Redis缓存"""
        self.client = None
        self.serialization = "json"  # 默认序列化方式
        self.prefix = ""  # 键前缀
    
    def initialize(
        self, 
        redis_url: str, 
        serialization: str = "json", 
        prefix: str = "", 
        **kwargs
    ) -> None:
        """初始化Redis客户端
        
        Args:
            redis_url: Redis连接URL，格式为redis://[[username]:[password]]@host:port/db
            serialization: 序列化方式，支持"json"和"pickle"
            prefix: 键前缀
            **kwargs: 其他Redis连接选项
        """
        try:
            # 验证序列化方式
            if serialization not in self.SERIALIZATION_METHODS:
                raise ValueError(
                    f"不支持的序列化方式: {serialization}，支持的方式: {', '.join(self.SERIALIZATION_METHODS)}"
                )
            
            # 设置序列化方式和前缀
            self.serialization = serialization
            self.prefix = prefix
            
            # 创建Redis客户端
            self.client = redis.from_url(redis_url, **kwargs)
            
            # 测试连接
            self.client.ping()
            
            logger.info(f"Redis cache initialized with URL: {redis_url}")
        except (ConnectionError, RedisError) as e:
            logger.error(f"Failed to initialize Redis client: {str(e)}")
            raise APIException(f"Redis初始化失败: {str(e)}", EXTERNAL_API_ERROR)
    
    def _prefixed_key(self, key: str) -> str:
        """为键添加前缀
        
        Args:
            key: 原始键名
            
        Returns:
            添加了前缀的键名
        """
        if not self.prefix:
            return key
        return f"{self.prefix}:{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """序列化值
        
        Args:
            value: 要序列化的值
            
        Returns:
            序列化后的字节串
            
        Raises:
            TypeError: 如果无法序列化
        """
        try:
            if self.serialization == "json":
                return json.dumps(value).encode("utf-8")
            elif self.serialization == "pickle":
                return pickle.dumps(value)
            else:
                raise ValueError(f"未知的序列化方式: {self.serialization}")
        except (TypeError, ValueError) as e:
            logger.error(f"Serialization error: {str(e)}")
            raise
    
    def _deserialize(self, data: bytes) -> Any:
        """反序列化数据
        
        Args:
            data: 要反序列化的字节串
            
        Returns:
            反序列化后的值
            
        Raises:
            ValueError: 如果无法反序列化
        """
        if data is None:
            return None
            
        try:
            if self.serialization == "json":
                return json.loads(data.decode("utf-8"))
            elif self.serialization == "pickle":
                return pickle.loads(data)
            else:
                raise ValueError(f"未知的序列化方式: {self.serialization}")
        except (json.JSONDecodeError, pickle.UnpicklingError, ValueError) as e:
            logger.error(f"Deserialization error: {str(e)}")
            return None
    
    def _handle_redis_error(self, operation: str, error: Exception) -> None:
        """处理Redis错误
        
        Args:
            operation: 操作名称
            error: 捕获的异常
            
        Raises:
            APIException: 转换后的API异常
        """
        error_msg = f"Redis {operation}失败: {str(error)}"
        logger.error(error_msg)
        raise APIException(error_msg, EXTERNAL_API_ERROR)
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项
        
        Args:
            key: 缓存键名
            
        Returns:
            缓存的值，如果不存在则返回None
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            prefixed_key = self._prefixed_key(key)
            data = self.client.get(prefixed_key)
            return self._deserialize(data)
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("get", e)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存项
        
        Args:
            key: 缓存键名
            value: 要缓存的值
            ttl: 过期时间（秒），None表示永不过期
            
        Returns:
            操作是否成功
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            prefixed_key = self._prefixed_key(key)
            serialized_value = self._serialize(value)
            
            if ttl is not None:
                return bool(self.client.setex(prefixed_key, ttl, serialized_value))
            else:
                return bool(self.client.set(prefixed_key, serialized_value))
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("set", e)
    
    def delete(self, key: str) -> bool:
        """删除缓存项
        
        Args:
            key: 要删除的缓存键名
            
        Returns:
            操作是否成功
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            prefixed_key = self._prefixed_key(key)
            return bool(self.client.delete(prefixed_key))
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("delete", e)
    
    def exists(self, key: str) -> bool:
        """检查缓存键是否存在
        
        Args:
            key: 缓存键名
            
        Returns:
            键是否存在
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            prefixed_key = self._prefixed_key(key)
            return bool(self.client.exists(prefixed_key))
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("exists", e)
    
    def ttl(self, key: str) -> Optional[int]:
        """获取缓存项剩余生存时间
        
        Args:
            key: 缓存键名
            
        Returns:
            剩余生存时间（秒），None表示永不过期，-1表示键不存在
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            prefixed_key = self._prefixed_key(key)
            ttl_value = self.client.ttl(prefixed_key)
            
            # Redis返回-2表示键不存在，-1表示没有设置过期时间
            if ttl_value == -2:
                return -1
            elif ttl_value == -1:
                return None
            else:
                return ttl_value
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("ttl", e)
    
    def expire(self, key: str, ttl: int) -> bool:
        """设置缓存项的过期时间
        
        Args:
            key: 缓存键名
            ttl: 过期时间（秒）
            
        Returns:
            操作是否成功
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            prefixed_key = self._prefixed_key(key)
            return bool(self.client.expire(prefixed_key, ttl))
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("expire", e)
    
    def mget(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存项
        
        Args:
            keys: 缓存键名列表
            
        Returns:
            键值对字典，不存在的键不会出现在结果中
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            # 为所有键添加前缀
            prefixed_keys = [self._prefixed_key(key) for key in keys]
            
            # 获取所有值
            values = self.client.mget(prefixed_keys)
            
            # 构造结果字典
            result = {}
            for i, key in enumerate(keys):
                if values[i] is not None:
                    result[key] = self._deserialize(values[i])
            
            return result
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("mget", e)
    
    def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """批量设置缓存项
        
        Args:
            mapping: 键值对字典
            ttl: 过期时间（秒），None表示永不过期
            
        Returns:
            操作是否成功
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            # 准备带前缀的映射
            prefixed_mapping = {}
            for key, value in mapping.items():
                prefixed_key = self._prefixed_key(key)
                prefixed_mapping[prefixed_key] = self._serialize(value)
            
            # 设置所有值
            with self.client.pipeline() as pipe:
                pipe.mset(prefixed_mapping)
                
                # 如果设置了TTL，为每个键设置过期时间
                if ttl is not None:
                    for prefixed_key in prefixed_mapping.keys():
                        pipe.expire(prefixed_key, ttl)
                
                pipe.execute()
            
            return True
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("mset", e)
    
    def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的所有键
        
        Args:
            pattern: 匹配模式，支持通配符
            
        Returns:
            匹配的键列表（已移除前缀）
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            # 添加前缀到模式
            prefixed_pattern = self._prefixed_key(pattern)
            
            # 获取所有匹配的键
            prefixed_keys = self.client.keys(prefixed_pattern)
            
            # 移除前缀
            if not self.prefix:
                return [key.decode("utf-8") for key in prefixed_keys]
            else:
                prefix_length = len(self.prefix) + 1  # +1 是为了冒号
                return [key.decode("utf-8")[prefix_length:] for key in prefixed_keys]
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("keys", e)
    
    def flush(self) -> bool:
        """清空所有缓存（只清除当前前缀下的键）
        
        Returns:
            操作是否成功
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            # 如果有前缀，只删除前缀下的键
            if self.prefix:
                keys = self.client.keys(f"{self.prefix}:*")
                if keys:
                    self.client.delete(*keys)
            else:
                # 如果没有前缀，清空整个数据库
                self.client.flushdb()
            
            return True
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("flush", e)
    
    def incr(self, key: str, amount: int = 1) -> int:
        """递增缓存项的值
        
        Args:
            key: 缓存键名
            amount: 递增量，默认为1
            
        Returns:
            递增后的值
            
        Raises:
            ValueError: 如果值不是整数类型
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            prefixed_key = self._prefixed_key(key)
            return self.client.incrby(prefixed_key, amount)
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("incr", e)
    
    def decr(self, key: str, amount: int = 1) -> int:
        """递减缓存项的值
        
        Args:
            key: 缓存键名
            amount: 递减量，默认为1
            
        Returns:
            递减后的值
            
        Raises:
            ValueError: 如果值不是整数类型
        """
        if not self.client:
            raise APIException("Redis客户端未初始化", EXTERNAL_API_ERROR)
            
        try:
            prefixed_key = self._prefixed_key(key)
            return self.client.decrby(prefixed_key, amount)
        except (ConnectionError, RedisError) as e:
            self._handle_redis_error("decr", e)