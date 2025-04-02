"""数据验证工具"""
import re
from typing import Any, Union, List, Dict, Optional
import ipaddress
import uuid

def is_email(value: str) -> bool:
    """验证是否为有效的邮箱格式
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否为有效的邮箱
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, value))

def is_url(value: str) -> bool:
    """验证是否为有效的URL格式
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否为有效的URL
    """
    pattern = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
    return bool(re.match(pattern, value))

def is_phone_number(value: str, country: str = 'CN') -> bool:
    """验证是否为有效的电话号码
    
    Args:
        value: 要验证的字符串
        country: 国家代码，默认为中国
        
    Returns:
        是否为有效的电话号码
    """
    if country == 'CN':
        # 中国大陆手机号
        pattern = r'^1[3-9]\d{9}$'
        return bool(re.match(pattern, value))
    elif country == 'US':
        # 美国电话号码
        pattern = r'^\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})$'
        return bool(re.match(pattern, value))
    else:
        # 通用格式，宽松验证
        pattern = r'^\+?[0-9]{7,15}$'
        return bool(re.match(pattern, value))

def is_ip_address(value: str) -> bool:
    """验证是否为有效的IP地址
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否为有效的IP地址
    """
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False

def is_uuid(value: str) -> bool:
    """验证是否为有效的UUID
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否为有效的UUID
    """
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False

def is_empty(value: Any) -> bool:
    """检查值是否为空
    
    Args:
        value: 要检查的值
        
    Returns:
        值是否为空
    """
    if value is None:
        return True
    elif isinstance(value, str):
        return value.strip() == ''
    elif isinstance(value, (list, dict, set, tuple)):
        return len(value) == 0
    return False

def is_numeric(value: str) -> bool:
    """验证字符串是否为数字
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否为数字
    """
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

def is_integer(value: str) -> bool:
    """验证字符串是否为整数
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否为整数
    """
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        return False

def is_alphanumeric(value: str) -> bool:
    """验证字符串是否只包含字母和数字
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否只包含字母和数字
    """
    return value.isalnum()

def is_chinese(value: str) -> bool:
    """验证字符串是否为中文
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否为中文
    """
    pattern = r'^[\u4e00-\u9fa5]+$'
    return bool(re.match(pattern, value))

def is_length_between(value: str, min_length: int, max_length: int) -> bool:
    """验证字符串长度是否在指定范围内
    
    Args:
        value: 要验证的字符串
        min_length: 最小长度
        max_length: 最大长度
        
    Returns:
        是否在长度范围内
    """
    return min_length <= len(value) <= max_length

def contains_uppercase(value: str) -> bool:
    """验证字符串是否包含大写字母
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否包含大写字母
    """
    return any(char.isupper() for char in value)

def contains_lowercase(value: str) -> bool:
    """验证字符串是否包含小写字母
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否包含小写字母
    """
    return any(char.islower() for char in value)

def contains_digit(value: str) -> bool:
    """验证字符串是否包含数字
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否包含数字
    """
    return any(char.isdigit() for char in value)

def contains_special_char(value: str) -> bool:
    """验证字符串是否包含特殊字符
    
    Args:
        value: 要验证的字符串
        
    Returns:
        是否包含特殊字符
    """
    pattern = r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]'
    return bool(re.search(pattern, value))

def is_strong_password(value: str, min_length: int = 8) -> bool:
    """验证是否为强密码
    
    密码必须满足:
    1. 最小长度为min_length
    2. 包含大写字母
    3. 包含小写字母
    4. 包含数字
    5. 包含特殊字符
    
    Args:
        value: 要验证的密码
        min_length: 最小长度
        
    Returns:
        是否为强密码
    """
    return (len(value) >= min_length and 
            contains_uppercase(value) and 
            contains_lowercase(value) and 
            contains_digit(value) and 
            contains_special_char(value))