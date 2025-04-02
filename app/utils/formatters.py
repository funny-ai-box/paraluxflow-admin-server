"""数据格式化工具"""
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
import json

def format_datetime(dt: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[str]:
    """格式化日期时间
    
    Args:
        dt: 日期时间对象
        format_str: 格式字符串
        
    Returns:
        格式化后的日期时间字符串
    """
    if dt is None:
        return None
    return dt.strftime(format_str)

def format_date(dt: Optional[datetime], format_str: str = "%Y-%m-%d") -> Optional[str]:
    """格式化日期
    
    Args:
        dt: 日期时间对象
        format_str: 格式字符串
        
    Returns:
        格式化后的日期字符串
    """
    return format_datetime(dt, format_str)

def format_time(dt: Optional[datetime], format_str: str = "%H:%M:%S") -> Optional[str]:
    """格式化时间
    
    Args:
        dt: 日期时间对象
        format_str: 格式字符串
        
    Returns:
        格式化后的时间字符串
    """
    return format_datetime(dt, format_str)

def format_currency(amount: Union[int, float], currency: str = "¥", decimal_places: int = 2) -> str:
    """格式化货币
    
    Args:
        amount: 金额
        currency: 货币符号
        decimal_places: 小数位数
        
    Returns:
        格式化后的货币字符串
    """
    return f"{currency}{amount:.{decimal_places}f}"

def format_file_size(size_bytes: int) -> str:
    """格式化文件大小
    
    Args:
        size_bytes: 字节数
        
    Returns:
        格式化后的文件大小字符串
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def format_json(data: Any, indent: int = 2) -> str:
    """格式化JSON
    
    Args:
        data: 要格式化的数据
        indent: 缩进值
        
    Returns:
        格式化后的JSON字符串
    """
    return json.dumps(data, ensure_ascii=False, indent=indent)

def format_percentage(value: float, decimal_places: int = 2) -> str:
    """格式化百分比
    
    Args:
        value: 小数值
        decimal_places: 小数位数
        
    Returns:
        格式化后的百分比字符串
    """
    return f"{value * 100:.{decimal_places}f}%"

def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """截断字符串
    
    Args:
        text: 原始字符串
        max_length: 最大长度
        suffix: 截断后的后缀
        
    Returns:
        截断后的字符串
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def format_list(items: List[Any], separator: str = ", ") -> str:
    """格式化列表为字符串
    
    Args:
        items: 列表项
        separator: 分隔符
        
    Returns:
        格式化后的字符串
    """
    return separator.join(str(item) for item in items)