"""认证API接口"""

from flask import Blueprint, request, g, current_app
from app.core.responses import error_response, success_response
from app.core.exceptions import ValidationException, AuthenticationException
from app.domains.auth.services.auth_service import AuthService
from app.infrastructure.database.repositories.auth_repository import AuthRepository
from app.infrastructure.database.repositories.user_repository import UserRepository
from app.infrastructure.database.session import get_db_session

auth_bp = Blueprint("auth", __name__)

API_DOC_FILE = 'auth.yml'

@auth_bp.route("/public_key", methods=["GET"])

def get_public_key():
    """获取RSA公钥"""
    # 从应用配置中获取公钥
    public_key = current_app.config.get('RSA_PUBLIC_KEY')
    
    if not public_key:
        return success_response({"public_key": None}, "RSA公钥未配置")
    
    return success_response({"public_key": public_key}, "获取RSA公钥成功")

@auth_bp.route("/register", methods=["POST"])

def register():
    """手机号密码注册"""
    # 验证请求数据
    # data = request.get_json()
    # if not data:
    #     raise ValidationException("请求数据不能为空")
    
    # # 检查必要字段
    # if "phone" not in data or "password" not in data:
    #     raise ValidationException("缺少必要参数: phone, password")
    
    # phone = data.get("phone")
    # print(phone)
    # encrypted_password = data.get("password")
    # print(encrypted_password)
    # username = data.get("username")  # 可选

    
    # # 初始化存储库和服务
    # db_session = get_db_session()
 
    # auth_repo = AuthRepository(db_session)
    # user_repo = UserRepository(db_session)
    # auth_service = AuthService(auth_repo, user_repo)
    
    
  
    # result = auth_service.register_with_phone_password(
    #     phone=phone,
    #     encrypted_password=encrypted_password,
    #     username=username
    #     )
    
    return error_response(60001, "不支持注册")
 
@auth_bp.route("/login", methods=["POST"])

def login():
    """手机号密码登录"""
    # 验证请求数据
    data = request.get_json()
    if not data:
        raise ValidationException("请求数据不能为空")
    
    # 检查必要字段
    if "phone" not in data or "password" not in data:
        raise ValidationException("缺少必要参数: phone, password")
    
    phone = data.get("phone")
    encrypted_password = data.get("password")
    
    # 获取请求信息
    ip_address = request.remote_addr
    user_agent = request.headers.get("User-Agent")
    
    # 初始化存储库和服务
    db_session = get_db_session()
    auth_repo = AuthRepository(db_session)
    user_repo = UserRepository(db_session)
    auth_service = AuthService(auth_repo, user_repo)
    
    # 登录
    result = auth_service.login_with_phone_password(
        phone=phone,
        encrypted_password=encrypted_password,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    return success_response(result, "登录成功")
