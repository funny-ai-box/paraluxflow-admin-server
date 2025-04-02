"""认证中间件"""
from functools import wraps
from flask import request, g, current_app
import jwt
import time
from app.core.exceptions import AuthenticationException
from app.core.status_codes import UNAUTHORIZED, TOKEN_EXPIRED, INVALID_TOKEN
from app.infrastructure.database.repositories.user_repository import UserRepository
from app.infrastructure.database.session import get_db_session

def auth_required(f):
    """JWT认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print("===== 开始JWT认证 =====")
        # 从请求头中获取JWT令牌
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            print("错误: 缺少Authorization请求头")
            raise AuthenticationException("缺少认证令牌")
        
        # 提取令牌
        token_parts = auth_header.split()
        print(f"Authorization头拆分结果: {token_parts}")
        
        if len(token_parts) != 2 or token_parts[0].lower() != "bearer":
            print(f"错误: 无效的认证格式 - 长度: {len(token_parts)}, 前缀: {token_parts[0] if token_parts else None}")
            raise AuthenticationException("无效的认证格式")
        
        token = token_parts[1]
        print(f"提取的令牌: {token[:15]}...{token[-15:]} (仅显示首尾)")
        
        try:
            # 获取密钥
            secret_key = current_app.config.get("JWT_SECRET_KEY")
            print(f"使用的密钥: {secret_key[:3]}...{secret_key[-3:] if secret_key else None} (仅显示首尾)")
            
            # 解码令牌前检查
            print("尝试解码令牌...")
            
            # 解码令牌
            payload = jwt.decode(token, secret_key, algorithms=["HS256"],leeway=120)
            print(f"令牌解码成功，payload: {payload}")
            
            # 获取用户ID
            user_id = payload.get("sub")
            if not user_id:
                print("错误: payload中缺少'sub'字段")
                raise AuthenticationException("无效的2令牌")
            
            print(f"从令牌获取的用户ID: {user_id}")
            
            # 检查令牌过期时间
            exp_time = payload.get("exp", 0)
            current_time = int(time.time())
            time_diff = exp_time - current_time
            print(f"令牌过期时间: {exp_time} (Unix时间戳)")
            print(f"当前时间: {current_time} (Unix时间戳)")
            print(f"距离过期还有: {time_diff} 秒")
            
            # 初始化存储库
            print("初始化用户存储库...")
            db_session = get_db_session()
            user_repo = UserRepository(db_session)
            
            # 验证用户是否存在
            print(f"查询用户ID: {user_id}...")
            user = user_repo.find_by_id(user_id)
            if not user:
                print(f"错误: 用户ID {user_id} 不存在")
                raise AuthenticationException("用户不存在")
            
            print(f"用户信息: ID={user.id}, 用户名={user.username}, 状态={user.is_active}")
            
            # 验证用户状态
            if not user.is_active:
                print("错误: 用户账户已禁用")
                raise AuthenticationException("账户已禁用")
            
            # 将用户ID和会话存储在请求上下文中
            g.user_id = user_id
            g.db_session = db_session
            
            print("===== JWT认证成功 =====")
            # 调用被装饰的函数
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError as e:
            print(f"错误: 令牌已过期 - {str(e)}")
            raise AuthenticationException("令牌已过期")
        except jwt.InvalidTokenError as e:
            print(f"错误: 无效的令1牌 - {str(e)}")
            raise AuthenticationException("无效的令牌")
        except AuthenticationException:
            # 直接重新抛出认证异常
            raise
        except Exception as e:
            # 记录未知异常，但不做处理，让它继续传播
            print(f"认证过程中发生非认证异常 - 类型: {type(e).__name__}, 信息: {str(e)}")
            raise  # 让异常继续传播，保持原始异常类型
    return decorated_function

def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print("===== 检查管理员权限 =====")
        # 先验证JWT令牌
        @auth_required
        def check_admin(*args, **kwargs):
            # 获取用户
            db_session = g.db_session
            user_repo = UserRepository(db_session)
            user = user_repo.find_by_id(g.user_id)
            
            print(f"检查用户 {user.username} (ID: {user.id}) 的管理员权限")
            # 验证管理员权限
            if not user.is_admin:
                print(f"错误: 用户 {user.username} 不是管理员")
                raise AuthenticationException("需要管理员权限")
            
            print(f"用户 {user.username} 具有管理员权限，验证通过")
            return f(*args, **kwargs)
        return check_admin(*args, **kwargs)
    return decorated_function