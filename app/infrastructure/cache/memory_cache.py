"""内存缓存实现，用于开发和测试环境"""
import fnmatch
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Set

from app.infrastructure.cache.base import CacheInterface

logger = logging.getLogger(__name__)

class MemoryCache(CacheInterface):
    """内存缓存实现，适用于开发和测试环境"""
    
    def __init__(self):
        """初始化内存缓存"""
        # 存储结构：{key: (value, expiry_time)}
        # expiry_time为None表示永不过期，否则为Unix时间戳
        self.cache = {}
        self.lock = threading.RLock()  # 可重入锁，用于线程安全操作
        self.prefix = ""
    
    def initialize(self, prefix: str = "", **kwargs) -> None:
        """初始化内存缓存
        
        Args:
            prefix: 键前缀
            **kwargs: 其他配置参数（被忽略）
        """
        self.prefix = prefix
        logger.info("Memory cache initialized")
    
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
    
    def _cleanup_expired(self) -> None:
        """清理已过期的缓存项"""
        now = time.time()
        expired_keys = []
        
        # 找出所有过期的键
        for key, (_, expiry_time) in self.cache.items():
            if expiry_time is not None and expiry_time <= now:
                expired_keys.append(key)
        
        # 删除过期的键
        for key in expired_keys:
            del self.cache[key]
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项
        
        Args:
            key: 缓存键名
            
        Returns:
            缓存的值，如果不存在或已过期则返回None
        """
        with self.lock:
            self._cleanup_expired()
            
            prefixed_key = self._prefixed_key(key)
            if prefixed_key in self.cache:
                value, expiry_time = self.cache[prefixed_key]
                return value
            
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存项
        
        Args:
            key: 缓存键名
            value: 要缓存的值
            ttl: 过期时间（秒），None表示永不过期
            
        Returns:
            操作是否成功
        """
        with self.lock:
            prefixed_key = self._prefixed_key(key)
            
            # 计算过期时间
            expiry_time = None
            if ttl is not None:
                expiry_time = time.time() + ttl
            
            # 存储值和过期时间
            self.cache[prefixed_key] = (value, expiry_time)
            return True
    
    def delete(self, key: str) -> bool:
        """删除缓存项
        
        Args:
            key: 要删除的缓存键名
            
        Returns:
            操作是否成功（如果键不存在也返回True）
        """
        with self.lock:
            prefixed_key = self._prefixed_key(key)
            if prefixed_key in self.cache:
                del self.cache[prefixed_key]
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """检查缓存键是否存在
        
        Args:
            key: 缓存键名
            
        Returns:
            键是否存在且未过期
        """
        with self.lock:
            self._cleanup_expired()
            
            prefixed_key = self._prefixed_key(key)
            return prefixed_key in self.cache
    
    def ttl(self, key: str) -> Optional[int]:
        """获取缓存项剩余生存时间
        
        Args:
            key: 缓存键名
            
        Returns:
            剩余生存时间（秒），None表示永不过期，-1表示键不存在
        """
        with self.lock:
            self._cleanup_expired()
            
            prefixed_key = self._prefixed_key(key)
            if prefixed_key not in self.cache:
                return -1
            
            _, expiry_time = self.cache[prefixed_key]
            if expiry_time is None:
                return None
            
            # 计算剩余时间
            remaining = expiry_time - time.time()
            return int(max(0, remaining))  # 不返回负数
    
    def expire(self, key: str, ttl: int) -> bool:
        """设置缓存项的过期时间
        
        Args:
            key: 缓存键名
            ttl: 过期时间（秒）
            
        Returns:
            操作是否成功
        """
        with self.lock:
            prefixed_key = self._prefixed_key(key)
            if prefixed_key not in self.cache:
                return False
            
            # 更新过期时间
            value, _ = self.cache[prefixed_key]
            expiry_time = time.time() + ttl
            self.cache[prefixed_key] = (value, expiry_time)
            return True
    
    def mget(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存项
        
        Args:
            keys: 缓存键名列表
            
        Returns:
            键值对字典，不存在的键不会出现在结果中
        """
        with self.lock:
            self._cleanup_expired()
            
            result = {}
            for key in keys:
                prefixed_key = self._prefixed_key(key)
                if prefixed_key in self.cache:
                    value, _ = self.cache[prefixed_key]
                    result[key] = value
            
            return result
    
    def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """批量设置缓存项
        
        Args:
            mapping: 键值对字典
            ttl: 过期时间（秒），None表示永不过期
            
        Returns:
            操作是否成功
        """
        with self.lock:
            # 计算过期时间
            expiry_time = None
            if ttl is not None:
                expiry_time = time.time() + ttl
            
            # 批量设置
            for key, value in mapping.items():
                prefixed_key = self._prefixed_key(key)
                self.cache[prefixed_key] = (value, expiry_time)
            
            return True
    
    def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的所有键
        
        Args:
            pattern: 匹配模式，支持通配符
            
        Returns:
            匹配的键列表（已移除前缀）
        """
        with self.lock:
            self._cleanup_expired()
            
            # 构造带前缀的模式
            prefixed_pattern = self._prefixed_key(pattern)
            
            # 查找匹配的键
            matched_keys = []
            for key in self.cache.keys():
                if fnmatch.fnmatch(key, prefixed_pattern):
                    # 移除前缀
                    if not self.prefix:
                        matched_keys.append(key)
                    else:
                        matched_keys.append(key[len(self.prefix) + 1:])  # +1 是为了冒号
            
            return matched_keys
    
    def flush(self) -> bool:
        """清空所有缓存（只清除当前前缀下的键）
        
        Returns:
            操作是否成功
        """
        with self.lock:
            if not self.prefix:
                # 如果没有前缀，清空所有键
                self.cache.clear()
            else:
                # 如果有前缀，只清除前缀下的键
                prefix_with_colon = f"{self.prefix}:"
                keys_to_delete = [key for key in self.cache.keys() if key.startswith(prefix_with_colon)]
                for key in keys_to_delete:
                    del self.cache[key]
            
            return True
    
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
        with self.lock:
            prefixed_key = self._prefixed_key(key)
            
            # 获取当前值
            if prefixed_key in self.cache:
                value, expiry_time = self.cache[prefixed_key]
                
                # 检查值类型
                if not isinstance(value, int):
                    raise ValueError("缓存项的值不是整数类型")
                
                # 递增值
                new_value = value + amount
                self.cache[prefixed_key] = (new_value, expiry_time)
                return new_value
            else:
                # 键不存在，创建新键
                self.cache[prefixed_key] = (amount, None)
                return amount
    
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
        # 递减就是递增负数
        return self.incr(key, -amount)