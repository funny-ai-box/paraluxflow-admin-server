# app/api/client/v1/auth/auth.py
"""客户端认证API接口"""
from datetime import datetime, timedelta
import logging
import json
import uuid
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

@auth_bp.route("/google/url", methods=["GET"])
def google_auth_url():
    """获取Google认证URL
    
    Returns:
        包含认证URL的响应
    """
    try:
        # 生成状态参数，用于防止CSRF
        state = str(uuid.uuid4())
        
        # 创建会话和存储库
        db_session = get_db_session()
        user_repo = UserRepository(db_session)
        
        # 创建服务
        auth_service = GoogleAuthService(user_repo)
        
        # 获取认证URL
        auth_url = auth_service.get_auth_url(state)
        
        return success_response({
            "auth_url": auth_url,
            "state": state
        })
    except Exception as e:
        logger.error(f"获取Google认证URL失败: {str(e)}")
        return error_response(AUTH_FAILED, f"获取认证URL失败: {str(e)}")

@auth_bp.route("/google/callback", methods=["GET"])
def google_callback():
    """Google认证回调
    
    处理Google认证回调，获取用户信息并生成JWT令牌
    
    Returns:
        重定向到前端携带令牌的URL
    """
    try:
        # 获取授权码和状态
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")
        
        # 获取前端回调URL
        frontend_callback_url = current_app.config.get("FRONTEND_CALLBACK_URL", "app://auth-callback")
        
        if error:
            logger.error(f"Google认证失败: {error}")
            return redirect(f"{frontend_callback_url}?error={error}")
        
        if not code:
            logger.error("缺少授权码")
            return redirect(f"{frontend_callback_url}?error=missing_code")
        
        # 创建会话和存储库
        db_session = get_db_session()
        user_repo = UserRepository(db_session)
        
        # 创建服务
        auth_service = GoogleAuthService(user_repo)
        
        # 认证用户
        auth_result, error = auth_service.authenticate(code)
        
        if error:
            logger.error(f"认证失败: {error}")
            return redirect(f"{frontend_callback_url}?error={error}")
        
        # 重定向到前端，携带令牌
        token = auth_result.get("token")
        return redirect(f"{frontend_callback_url}?token={token}&state={state}")
    except Exception as e:
        logger.error(f"认证回调处理失败: {str(e)}")
        frontend_callback_url = current_app.config.get("FRONTEND_CALLBACK_URL", "app://auth-callback")
        return redirect(f"{frontend_callback_url}?error=server_error")

@auth_bp.route("/validate", methods=["GET"])
@client_auth_required
def validate_token():
    """验证令牌并返回用户信息
    
    Returns:
        用户信息
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 创建会话和存储库
        db_session = get_db_session()
        user_repo = UserRepository(db_session)
        
        # 获取用户信息
        user = user_repo.find_by_id(user_id)
        if not user:
            return error_response(AUTH_FAILED, "用户不存在")
        
        return success_response({
            "user": user_repo.user_to_dict(user)
        })
    except Exception as e:
        logger.error(f"验证令牌失败: {str(e)}")
        return error_response(AUTH_FAILED, f"验证令牌失败: {str(e)}")

@auth_bp.route("/logout", methods=["POST"])
@client_auth_required
def logout():
    """用户登出
    
    Returns:
        操作结果
    """
    # 客户端应自行处理令牌的清除
    return success_response(None, "登出成功")
@auth_bp.route("/login_by_token", methods=["GET"])
def login_by_token():
    """通过Firebase ID令牌登录 - 使用JWT认证
    
    查询参数:
    - id_token: Firebase ID令牌
    
    Returns:
        登录结果和JWT令牌
    """
    try:
        # 获取ID令牌
        id_token = request.args.get("id_token")
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