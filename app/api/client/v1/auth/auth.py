# app/api/client/v1/auth/auth.py
"""客户端认证API接口"""
from datetime import datetime, timedelta
import logging
import json
import uuid
from app.core.exceptions import AuthenticationException, ValidationException
from app.domains.auth.services.client_auth_service import ClientAuthService
from app.domains.auth.services.firebase_auth_service import FirebaseAuthService
from flask import Blueprint, request, redirect, jsonify, current_app, g, url_for

from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, AUTH_FAILED
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.user_repository import UserRepository
from app.domains.auth.services.google_auth_service import GoogleAuthService
from app.api.middleware.client_auth import client_auth_required

from app.api.client.v1.auth import auth_bp

logger = logging.getLogger(__name__)

@auth_bp.route("/login_by_token", methods=["POST"])
def login_by_token():
    """通过Firebase ID令牌登录 - 使用JWT认证
    
    查询参数:
    - id_token: Firebase ID令牌
    
    Returns:
        登录结果和JWT令牌
    """
    try:
        # 获取ID令牌
        print("-----------------")
        data=request.get_json()
        id_token = data.get("id_token")
        print("*"*100)
        print(id_token)
        print("*"*100)
        if not id_token:
            return error_response(PARAMETER_ERROR, "idToken is required")
        print(f"id_token: {id_token}")
        
        # 创建会话和存储库
        db_session = get_db_session()
        user_repo = UserRepository(db_session)
        
        # 创建服务
        auth_service = FirebaseAuthService(user_repo)
        
        # 认证用户并获取JWT令牌
        user_info, jwt_token, error = auth_service.authenticate_user(id_token)
        if error:
            return error_response(AUTH_FAILED, error)
        
        if not jwt_token:
            return error_response(AUTH_FAILED, "生成JWT令牌失败")
        
        # 构建结果
        result = {
            "user": user_info,
            "token": jwt_token
        }
        
        return success_response(result)
    except Exception as e:
        print(f"通过令牌登录失败: {str(e)}")
        logger.error(f"通过令牌登录失败: {str(e)}")
        return error_response(AUTH_FAILED, f"登录失败: {str(e)}")

@auth_bp.route("/refresh_token", methods=["POST"])
@client_auth_required
def refresh_token():
    """刷新JWT令牌
    
    此路由需要有效的JWT令牌才能访问，会生成一个新的JWT令牌
    
    Returns:
        新的JWT令牌
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        user_email = g.user_email
        user_google_id = g.user_google_id
        firebase_uid = g.firebase_uid
        
        # 创建会话和存储库
        db_session = get_db_session()
        user_repo = UserRepository(db_session)
        
        # 获取用户信息
        user = user_repo.find_by_id(user_id)
        if not user:
            return error_response(AUTH_FAILED, "用户不存在")
        
        # 生成新的JWT令牌
        from app.core.security import generate_token
        jwt_token = generate_token({
            "sub": user_id,
            "email": user_email,
            "google_id": user_google_id,
            "firebase_uid": firebase_uid
        })
        
        return success_response({
            "token": jwt_token
        }, "令牌刷新成功")
    except Exception as e:
        logger.error(f"刷新令牌失败: {str(e)}")
        return error_response(AUTH_FAILED, f"刷新令牌失败: {str(e)}")
    
@auth_bp.route("/register", methods=["POST"])
def register_with_email():
    """邮箱密码注册"""
    try:
        data = request.get_json()
        if not data:
            raise ValidationException("请求数据不能为空")

        email = data.get("email")
        encrypted_password = data.get("password") # Expecting RSA encrypted password
        username = data.get("username") # Optional

        if not email or not encrypted_password:
            raise ValidationException("缺少必要参数: email, password")

        db_session = get_db_session()
        user_repo = UserRepository(db_session)
        client_auth_service = ClientAuthService(user_repo)

        result = client_auth_service.register_with_email_password(
            email, encrypted_password, username
        )
        return success_response(result, message=result.pop("message", "注册成功")) # Pass potential specific message

    except (ValidationException, AuthenticationException) as e:
         logger.warning(f"邮箱注册失败: {e.message} (Code: {e.code})")
         return error_response(e.code, e.message)
    except Exception as e:
        logger.error(f"邮箱注册时发生意外错误: {str(e)}", exc_info=True)
        return error_response(AUTH_FAILED, "注册过程中发生错误")

@auth_bp.route("/login", methods=["POST"])
def login_with_email():
    """邮箱密码登录"""
    try:
        data = request.get_json()
        if not data:
            raise ValidationException("请求数据不能为空",PARAMETER_ERROR)

        email = data.get("email")
        encrypted_password = data.get("password") # Expecting RSA encrypted password

        if not email or not encrypted_password:
            raise ValidationException("缺少必要参数: email, password", AUTH_FAILED)

        db_session = get_db_session()
        user_repo = UserRepository(db_session)
        client_auth_service = ClientAuthService(user_repo)

        result = client_auth_service.login_with_email_password(
            email, encrypted_password
        )
        return success_response(result, "登录成功")

    except (ValidationException, AuthenticationException) as e:
         logger.warning(f"邮箱登录失败: {e.message} (Code: {e.code})")
         return error_response(e.code, e.message)
    except Exception as e:
        logger.error(f"邮箱登录时发生意外错误: {str(e)}", exc_info=True)
        return error_response(AUTH_FAILED, "登录过程中发生错误")
    
@auth_bp.route("/logout", methods=["POST"])
@client_auth_required
def logout():
    """用户注销
    
    此路由需要有效的JWT令牌才能访问
    注销后，客户端需要删除本地存储的JWT令牌
    服务端不做任何数据库操作，JWT令牌通过客户端删除来失效
    
    Returns:
        注销成功响应
    """
    try:
        # 从g对象获取用户信息
        user_id = g.user_id
        username = getattr(g, 'username', None)
        
        # 记录注销日志
        logger.info(f"用户注销: user_id={user_id}, username={username}")
        
        # 返回注销成功响应
        # 客户端收到此响应后应立即删除本地存储的JWT令牌
        return success_response({
            "message": "注销成功，请删除本地令牌",
            "timestamp": datetime.utcnow().isoformat()
        }, "用户已成功注销")
        
    except Exception as e:
        logger.error(f"用户注销失败: {str(e)}")
        return error_response(AUTH_FAILED, f"注销失败: {str(e)}")