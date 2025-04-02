# app/utils/security.py
from typing import Optional, Dict, Any
import uuid
import secrets
import logging
import re

logger = logging.getLogger(__name__)

def generate_app_key() -> str:
    """生成应用密钥
    
    Returns:
        生成的应用密钥
    """
    return str(uuid.uuid4()).replace("-", "")

def generate_secure_token(length: int = 32) -> str:
    """生成安全令牌
    
    Args:
        length: 令牌长度（字节）
        
    Returns:
        十六进制令牌字符串
    """
    return secrets.token_hex(length)

def mask_sensitive_info(value: Optional[str], visible_chars: int = 4) -> Optional[str]:
    """屏蔽敏感信息
    
    Args:
        value: 要屏蔽的值
        visible_chars: 末尾可见字符数
        
    Returns:
        屏蔽后的值
    """
    if not value or len(value) <= visible_chars:
        return None
    
    masked_length = len(value) - visible_chars
    return f"{'*' * masked_length}{value[-visible_chars:]}"

def mask_dict_values(data: Dict[str, Any], sensitive_keys: list) -> Dict[str, Any]:
    """屏蔽字典中的敏感字段
    
    Args:
        data: 数据字典
        sensitive_keys: 敏感键列表（支持正则表达式）
        
    Returns:
        屏蔽后的字典
    """
    result = {}
    
    for key, value in data.items():
        # 检查是否是敏感键
        is_sensitive = False
        for pattern in sensitive_keys:
            if re.match(pattern, key, re.IGNORECASE):
                is_sensitive = True
                break
        
        # 递归处理嵌套字典
        if isinstance(value, dict):
            result[key] = mask_dict_values(value, sensitive_keys)
        # 屏蔽敏感值
        elif is_sensitive and isinstance(value, str):
            result[key] = mask_sensitive_info(value)
        # 保持其他值不变
        else:
            result[key] = value
    
    return result