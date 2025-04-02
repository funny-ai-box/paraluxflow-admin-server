"""缓存接口基类"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Tuple, Set
import time

class CacheInterface(ABC):
    """缓存接口基类"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项
        
        Args:
            key: 缓存键名
            
        Returns:
            缓存的值，如果不存在则返回None
        """
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存项
        
        Args:
            key: 缓存键名
            value: 要缓存的值
            ttl: 过期时间（秒），None表示永不过期
            
        Returns:
            操作是否成功
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存项
        
        Args:
            key: 要删除的缓存键名
            
        Returns:
            操作是否成功
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查缓存键是否存在
        
        Args:
            key: 缓存键名
            
        Returns:
            键是否存在
        """
        pass
    
    @abstractmethod
    def ttl(self, key: str) -> Optional[int]:
        """获取缓存项剩余生存时间
        
        Args:
            key: 缓存键名
            
        Returns:
            剩余生存时间（秒），None表示永不过期，-1表示键不存在
        """
        pass
    
    @abstractmethod
    def expire(self, key: str, ttl: int) -> bool:
        """设置缓存项的过期时间
        
        Args:
            key: 缓存键名
            ttl: 过期时间（秒）
            
        Returns:
            操作是否成功
        """
        pass
    
    @abstractmethod
    def mget(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存项
        
        Args:
            keys: 缓存键名列表
            
        Returns:
            键值对字典，不存在的键不会出现在结果中
        """
        pass
    
    @abstractmethod
    def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """批量设置缓存项
        
        Args:
            mapping: 键值对字典
            ttl: 过期时间（秒），None表示永不过期
            
        Returns:
            操作是否成功
        """
        pass
    
    @abstractmethod
    def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的所有键
        
        Args:
            pattern: 匹配模式，支持通配符
            
        Returns:
            匹配的键列表
        """
        pass
    
    @abstractmethod
    def flush(self) -> bool:
        """清空所有缓存
        
        Returns:
            操作是否成功
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    # 高级缓存方法
    
    def get_or_set(self, key: str, default_func, ttl: Optional[int] = None) -> Any:
        """获取缓存项，如果不存在则设置并返回默认值
        
        Args:
            key: 缓存键名
            default_func: 生成默认值的函数
            ttl: 过期时间（秒），None表示永不过期
            
        Returns:
            缓存的值或默认值
        """
        value = self.get(key)
        if value is None:
            value = default_func()
            self.set(key, value, ttl)
        return value
    
    def get_with_metadata(self, key: str) -> Tuple[Optional[Any], Dict[str, Any]]:
        """获取缓存项及其元数据
        
        Args:
            key: 缓存键名
            
        Returns:
            (值, 元数据字典)元组，如果键不存在则值为None
        """
        value = self.get(key)
        
        metadata = {}
        if value is not None:
            ttl_value = self.ttl(key)
            metadata = {
                "exists": True,
                "ttl": ttl_value
            }
        else:
            metadata = {
                "exists": False
            }
            
        return value, metadata
    
    def cache_decorator(self, prefix: str, ttl: Optional[int] = None):
        """创建一个缓存装饰器，用于缓存函数结果
        
        Args:
            prefix: 缓存键前缀
            ttl: 过期时间（秒），None表示永不过期
            
        Returns:
            装饰器函数
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # 构造缓存键
                key_parts = [prefix, func.__name__]
                for arg in args:
                    key_parts.append(str(arg))
                
                for k, v in sorted(kwargs.items()):
                    key_parts.append(f"{k}={v}")
                
                cache_key = ":".join(key_parts)
                
                # 尝试从缓存获取
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # 执行函数并缓存结果
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                return result
            
            return wrapper
        
        return decorator