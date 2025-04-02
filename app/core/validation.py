"""数据验证工具"""
import re
from typing import Dict, Any, List, Optional, Callable, TypeVar, Union
from app.core.exceptions import ValidationException
from app.core.status_codes import PARAMETER_ERROR

T = TypeVar('T')

def validate_required_fields(data: Dict[str, Any], required_fields: List[str], error_code: int = PARAMETER_ERROR) -> None:
    """验证必填字段
    
    Args:
        data: 要验证的数据字典
        required_fields: 必填字段列表
        error_code: 错误状态码
        
    Raises:
        ValidationException: 如果缺少必填字段
    """
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    
    if missing_fields:
        raise ValidationException(
            f"缺少必填字段: {', '.join(missing_fields)}", 
            error_code
        )

def validate_field_value(
    data: Dict[str, Any], 
    field: str, 
    validator: Callable[[Any], bool], 
    error_message: str,
    error_code: int = PARAMETER_ERROR
) -> None:
    """验证字段值
    
    Args:
        data: 要验证的数据字典
        field: 字段名
        validator: 验证函数
        error_message: 错误消息
        error_code: 错误状态码
        
    Raises:
        ValidationException: 如果字段值不符合要求
    """
    if field in data and data[field] is not None:
        if not validator(data[field]):
            raise ValidationException(error_message, error_code)

def validate_email(email: str) -> bool:
    """验证邮箱格式
    
    Args:
        email: 要验证的邮箱
        
    Returns:
        是否为有效邮箱
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_url(url: str) -> bool:
    """验证URL格式
    
    Args:
        url: 要验证的URL
        
    Returns:
        是否为有效URL
    """
    pattern = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
    return bool(re.match(pattern, url))

def validate_numeric_range(
    value: Union[int, float], 
    min_value: Optional[Union[int, float]] = None, 
    max_value: Optional[Union[int, float]] = None
) -> bool:
    """验证数值范围
    
    Args:
        value: 要验证的数值
        min_value: 最小值（包含）
        max_value: 最大值（包含）
        
    Returns:
        值是否在范围内
    """
    if min_value is not None and value < min_value:
        return False
    if max_value is not None and value > max_value:
        return False
    return True

def validate_string_length(value: str, min_length: Optional[int] = None, max_length: Optional[int] = None) -> bool:
    """验证字符串长度
    
    Args:
        value: 要验证的字符串
        min_length: 最小长度（包含）
        max_length: 最大长度（包含）
        
    Returns:
        长度是否在范围内
    """
    if min_length is not None and len(value) < min_length:
        return False
    if max_length is not None and len(value) > max_length:
        return False
    return True

def validate_list_length(value: List[Any], min_length: Optional[int] = None, max_length: Optional[int] = None) -> bool:
    """验证列表长度
    
    Args:
        value: 要验证的列表
        min_length: 最小长度（包含）
        max_length: 最大长度（包含）
        
    Returns:
        长度是否在范围内
    """
    if min_length is not None and len(value) < min_length:
        return False
    if max_length is not None and len(value) > max_length:
        return False
    return True