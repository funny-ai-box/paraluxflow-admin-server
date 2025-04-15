# app/api/middleware/client_auth.py
"""客户端JWT认证中间件"""
from functools import wraps
import logging
import time
import jwt
from flask import request, g, current_app

from app.core.exceptions import AuthenticationException
from app.core.status_codes import UNAUTHORIZED, TOKEN_EXPIRED, INVALID_TOKEN

logger = logging.getLogger(__name__)

def client_auth_required(f):
    """客户端JWT认证装饰器
    
    验证客户端请求中的JWT令牌，获取用户ID并存储在g对象中
    
    Args:
        f: 被装饰的函数
        
    Returns:
        装饰后的函数
        
    Raises:
        AuthenticationException: 认证失败时抛出异常
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        logger.debug("===== 开始客户端JWT认证 =====")
        # 从请求头中获取JWT令牌
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning("缺少Authorization请求头")
            raise AuthenticationException("缺少认证令牌")
        
        # 提取令牌
        token_parts = auth_header.split()
        logger.debug(f"Authorization头拆分结果: {token_parts}")
        
        if len(token_parts) != 2 or token_parts[0].lower() != "bearer":
            logger.warning(f"无效的认证格式 - 长度: {len(token_parts)}, 前缀: {token_parts[0] if token_parts else None}")
            raise AuthenticationException("无效的认证格式")
        
        token = token_parts[1]
        
        try:
            # 获取密钥
            secret_key = current_app.config.get("JWT_SECRET_KEY")
            
            # 解码令牌
            payload = jwt.decode(token, secret_key, algorithms=["HS256"], leeway=120)
            logger.debug(f"令牌解码成功")
            
            # 获取用户ID
            user_id = payload.get("sub")
            if not user_id:
                logger.warning("payload中缺少'sub'字段")
                raise AuthenticationException("无效的令牌")
            
            logger.debug(f"从令牌获取的用户ID: {user_id}")
            
            # 检查令牌过期时间
            exp_time = payload.get("exp", 0)
            current_time = int(time.time())
            time_diff = exp_time - current_time
            logger.debug(f"令牌过期时间: {exp_time} (Unix时间戳)")
            logger.debug(f"当前时间: {current_time} (Unix时间戳)")
            logger.debug(f"距离过期还有: {time_diff} 秒")
            
            # 将用户信息存储在请求上下文中
            g.user_id = user_id
            g.user_email = payload.get("email")
            g.user_google_id = payload.get("google_id")
            g.firebase_uid = payload.get("firebase_uid")  # 添加Firebase UID
            
            logger.debug("===== JWT认证成功 =====")
            # 调用被装饰的函数
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError as e:
            logger.warning(f"令牌已过期 - {str(e)}")
            raise AuthenticationException("令牌已过期")
        except jwt.InvalidTokenError as e:
            logger.warning(f"无效的令牌 - {str(e)}")
            raise AuthenticationException("无效的令牌")
        except Exception as e:
            # 记录未知异常
            logger.error(f"认证过程中发生非认证异常 - 类型: {type(e).__name__}, 信息: {str(e)}")
            raise
    
    return decorated_function