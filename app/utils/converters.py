"""数据转换工具"""
import json
import datetime
from typing import Dict, Any, List, Union, Optional, TypeVar, Type, Generic

T = TypeVar('T')

def to_dict(obj: Any) -> Dict[str, Any]:
    """将对象转换为字典
    
    Args:
        obj: 要转换的对象
        
    Returns:
        转换后的字典
    """
    if hasattr(obj, "__dict__"):
        # 处理常规对象
        result = {}
        for key, value in obj.__dict__.items():
            # 跳过私有属性
            if key.startswith("_"):
                continue
            # 递归转换值
            result[key] = to_dict(value) if hasattr(value, "__dict__") else value
        return result
    elif hasattr(obj, "keys"):
        # 处理类字典对象
        return {key: to_dict(obj[key]) if hasattr(obj[key], "__dict__") else obj[key] for key in obj.keys()}
    elif isinstance(obj, list):
        # 处理列表
        return [to_dict(item) if hasattr(item, "__dict__") else item for item in obj]
    else:
        # 其他类型直接返回
        return obj

def to_json(obj: Any, indent: Optional[int] = None) -> str:
    """将对象转换为JSON字符串
    
    Args:
        obj: 要转换的对象
        indent: 缩进值
        
    Returns:
        JSON字符串
    """
    def json_serial(obj):
        """JSON序列化处理器"""
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if hasattr(obj, "__dict__"):
            return to_dict(obj)
        return str(obj)
    
    return json.dumps(obj, default=json_serial, ensure_ascii=False, indent=indent)

def from_dict(data: Dict[str, Any], cls: Type[T]) -> T:
    """从字典创建对象
    
    Args:
        data: 字典数据
        cls: 目标类
        
    Returns:
        创建的对象实例
    """
    if hasattr(cls, "from_dict"):
        # 如果类有自己的from_dict方法，使用它
        return cls.from_dict(data)
    else:
        # 否则尝试创建实例并设置属性
        instance = cls()
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance

def to_camel_case(snake_str: str) -> str:
    """将下划线命名转为驼峰命名
    
    Args:
        snake_str: 下划线命名的字符串
        
    Returns:
        驼峰命名的字符串
    """
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

def to_snake_case(camel_str: str) -> str:
    """将驼峰命名转为下划线命名
    
    Args:
        camel_str: 驼峰命名的字符串
        
    Returns:
        下划线命名的字符串
    """
    import re
    pattern = re.compile(r'(?<!^)(?=[A-Z])')
    return pattern.sub('_', camel_str).lower()

def dict_keys_to_camel_case(d: Dict[str, Any]) -> Dict[str, Any]:
    """将字典的键转为驼峰命名
    
    Args:
        d: 要转换的字典
        
    Returns:
        转换后的字典
    """
    result = {}
    for key, value in d.items():
        camel_key = to_camel_case(key)
        # 递归处理嵌套字典
        if isinstance(value, dict):
            result[camel_key] = dict_keys_to_camel_case(value)
        # 处理字典列表
        elif isinstance(value, list) and all(isinstance(item, dict) for item in value):
            result[camel_key] = [dict_keys_to_camel_case(item) for item in value]
        else:
            result[camel_key] = value
    return result

def dict_keys_to_snake_case(d: Dict[str, Any]) -> Dict[str, Any]:
    """将字典的键转为下划线命名
    
    Args:
        d: 要转换的字典
        
    Returns:
        转换后的字典
    """
    result = {}
    for key, value in d.items():
        snake_key = to_snake_case(key)
        # 递归处理嵌套字典
        if isinstance(value, dict):
            result[snake_key] = dict_keys_to_snake_case(value)
        # 处理字典列表
        elif isinstance(value, list) and all(isinstance(item, dict) for item in value):
            result[snake_key] = [dict_keys_to_snake_case(item) for item in value]
        else:
            result[snake_key] = value
    return result