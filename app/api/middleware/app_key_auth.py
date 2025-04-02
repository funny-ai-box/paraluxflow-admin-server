# app/api/middleware/app_key_auth.py
from functools import wraps
import time
import logging
import traceback
from flask import request, g, current_app
from app.infrastructure.database.repositories.user_app_repository import UserAppRepository
from app.core.exceptions import AuthenticationException, ValidationException, NotFoundException
from app.core.status_codes import APPLICATION_NOT_FOUND, PARAMETER_ERROR, RATE_LIMITED
from app.infrastructure.database.session import get_db_session

logger = logging.getLogger(__name__)

# 简单的内存限流器
class RateLimiter:
    """简单的基于内存的限流器"""
    _requests = {}  # {app_key: [(timestamp, ip), ...]}
    _block_list = {}  # {app_key: unblock_time}
    
    @classmethod
    def check(cls, app_key, ip_address, limit=60, window=60):
        """检查是否超出限制
        
        Args:
            app_key: 应用密钥
            ip_address: 请求IP
            limit: 窗口期内允许的最大请求数
            window: 窗口期（秒）
            
        Returns:
            是否允许请求
        """
        now = time.time()
        
        # 检查是否被临时封禁
        if app_key in cls._block_list and cls._block_list[app_key] > now:
            return False
        
        # 初始化请求记录
        if app_key not in cls._requests:
            cls._requests[app_key] = []
        
        # 清理过期记录
        window_start = now - window
        cls._requests[app_key] = [r for r in cls._requests[app_key] if r[0] > window_start]
        
        # 检查请求数量
        if len(cls._requests[app_key]) >= limit:
            # 如果超过限制，临时封禁
            cls._block_list[app_key] = now + 60  # 封禁1分钟
            return False
        
        # 记录新请求
        cls._requests[app_key].append((now, ip_address))
        return True
    
    @classmethod
    def clean(cls):
        """清理过期数据"""
        now = time.time()
        # 清理过期的封禁记录
        cls._block_list = {k: v for k, v in cls._block_list.items() if v > now}
        
        # 清理过期的请求记录（超过1小时）
        for key in list(cls._requests.keys()):
            cls._requests[key] = [r for r in cls._requests[key] if r[0] > now - 3600]
            if not cls._requests[key]:
                del cls._requests[key]

def app_key_required(f):
    """应用密钥验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # 从请求头中获取应用密钥
            app_key = request.headers.get("X-App-Key")
            print("===== 开始应用密钥认证 =====")
            print(f"Headers获取是: {request.headers}")
            print(f"提取的应用密钥头: {app_key}")
            print(f"提取的应用密钥: {app_key[:15]}...{app_key[-15:]} (仅显示首尾)")
            if not app_key:
                raise AuthenticationException("缺少应用密钥")
            
            # 获取客户端IP
            ip_address = request.remote_addr
            
            # 限流检查
            if not RateLimiter.check(app_key, ip_address):
                logger.warning(f"Rate limit exceeded for app_key: {app_key}, IP: {ip_address}")
                raise ValidationException("请求频率超过限制，请稍后再试", RATE_LIMITED)
            
            # 初始化存储库
            db_session = get_db_session()
            user_app_repo = UserAppRepository(db_session)
            
            # 验证应用密钥
            app = user_app_repo.get_by_app_key(app_key)
            if not app:
                logger.warning(f"Invalid app key: {app_key}")
                raise NotFoundException("无效的应用密钥")
            
            # 验证应用是否已发布
            if not app.published:
                logger.warning(f"App not published: {app_key}")
                raise AuthenticationException("该应用未发布，无法使用")
            
            # 将应用信息和用户ID存储在请求上下文中
            g.app_key = app_key
            g.app = app
            g.user_id = app.user_id
            g.db_session = db_session
            
            # 记录API调用
            logger.info(f"API call from app: {app.name} (ID: {app.id}), User ID: {app.user_id}")
            
            # 执行被装饰的函数
            return f(*args, **kwargs)
            
        except (AuthenticationException, ValidationException, NotFoundException) as e:
            # 直接重新抛出已知异常
            raise
        except Exception as e:
            # 记录未知异常
            logger.error(f"Unexpected error in app_key_auth: {str(e)}\n{traceback.format_exc()}")
            raise AuthenticationException(f"应用验证失败: {str(e)}")
    
    return decorated_function

# 定期清理过期数据的函数，应当在应用启动时通过后台线程调用
def cleanup_rate_limiter():
    """清理限流器中的过期数据"""
    RateLimiter.clean()