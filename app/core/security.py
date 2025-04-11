"""安全相关工具"""
import hashlib
import hmac
import secrets
import uuid
import pytz
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import jwt
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash

def create_password_hash(password: str) -> str:
    """创建密码哈希
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码
    """
    return generate_password_hash(password, method='pbkdf2:sha256')

def verify_password(password_hash: str, password: str) -> bool:
    """验证密码
    
    Args:
        password_hash: 哈希后的密码
        password: 要验证的明文密码
        
    Returns:
        密码是否正确
    """
    return check_password_hash(password_hash, password)

def generate_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """生成JWT令牌
    
    Args:
        data: 令牌数据
        expires_delta: 过期时间间隔，默认为24小时
        
    Returns:
        JWT令牌
    """
    payload = data.copy()
    
    # 使用UTC时间确保服务器时区一致性
    if expires_delta:
        expire = datetime.now(tz=pytz.UTC) + expires_delta
    else:
        expire = datetime.now(tz=pytz.UTC) + timedelta(hours=24)
    
    # 添加标准声明
    payload.update({
        "exp": expire,
        "iat": datetime.now(tz=pytz.UTC)  # 添加签发时间
    })
    
    secret_key = current_app.config.get('JWT_SECRET_KEY')
    return jwt.encode(payload, secret_key, algorithm="HS256")

def decode_token(token: str) -> Dict[str, Any]:
    """解码JWT令牌
    
    Args:
        token: JWT令牌
        
    Returns:
        解码后的令牌数据
        
    Raises:
        jwt.PyJWTError: 如果令牌无效或已过期
    """
    secret_key = current_app.config.get('JWT_SECRET_KEY')
    return jwt.decode(token, secret_key, algorithms=["HS256"])

def generate_random_token(length: int = 32) -> str:
    """生成随机令牌
    
    Args:
        length: 令牌长度，默认为32
        
    Returns:
        随机令牌
    """
    return secrets.token_hex(length // 2)

def generate_uuid() -> str:
    """生成UUID
    
    Returns:
        UUID字符串
    """
    return str(uuid.uuid4()).replace('-', '')

def create_signature(data: str, secret: str) -> str:
    """创建数据签名
    
    Args:
        data: 要签名的数据
        secret: 密钥
        
    Returns:
        签名结果
    """
    return hmac.new(
        secret.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def verify_signature(data: str, signature: str, secret: str) -> bool:
    """验证数据签名
    
    Args:
        data: 签名的数据
        signature: 要验证的签名
        secret: 密钥
        
    Returns:
        签名是否有效
    """
    expected_signature = create_signature(data, secret)
    return hmac.compare_digest(expected_signature, signature)