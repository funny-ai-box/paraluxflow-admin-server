# app/domains/auth/services/google_auth_service.py
"""Google认证服务实现"""
import logging
import json
import time
from typing import Dict, Any, Optional, Tuple

import requests
from flask import current_app, url_for

from app.infrastructure.database.repositories.user_repository import UserRepository
from app.core.security import generate_token

logger = logging.getLogger(__name__)

class GoogleAuthService:
    """Google认证服务"""
    
    def __init__(self, user_repository: UserRepository):
        """初始化服务
        
        Args:
            user_repository: 用户仓库
        """
        self.user_repo = user_repository
    
    def get_auth_url(self, state: str = None) -> str:
        """获取Google认证URL
        
        Args:
            state: 状态参数
            
        Returns:
            认证URL
        """
        # 获取配置
        client_id = current_app.config.get("GOOGLE_CLIENT_ID")
        redirect_uri = url_for("api_client_v1.auth_bp.google_callback", _external=True)
        
        # 构建URL
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": client_id,
            "response_type": "code",
            "scope": "email profile",
            "redirect_uri": redirect_uri,
            "access_type": "offline",
            "prompt": "consent"
        }
        
        if state:
            params["state"] = state
        
        # 构建查询字符串
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{auth_url}?{query_string}"
    
    def exchange_code_for_token(self, code: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """用授权码交换令牌
        
        Args:
            code: 授权码
            
        Returns:
            (令牌数据, 错误信息)
        """
        try:
            # 获取配置
            client_id = current_app.config.get("GOOGLE_CLIENT_ID")
            client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET")
            redirect_uri = url_for("api_client_v1.auth_bp.google_callback", _external=True)
            
            # 发送令牌请求
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri
            }
            
            response = requests.post(token_url, data=data, timeout=10)
            response.raise_for_status()
            
            return response.json(), None
        except requests.RequestException as e:
            error_message = f"交换令牌失败: {str(e)}"
            if hasattr(e, "response") and e.response:
                error_message += f" - {e.response.text}"
            
            logger.error(error_message)
            return None, error_message
    
    def get_user_info(self, access_token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """获取用户信息
        
        Args:
            access_token: 访问令牌
            
        Returns:
            (用户信息, 错误信息)
        """
        try:
            user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = requests.get(user_info_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            return response.json(), None
        except requests.RequestException as e:
            error_message = f"获取用户信息失败: {str(e)}"
            if hasattr(e, "response") and e.response:
                error_message += f" - {e.response.text}"
            
            logger.error(error_message)
            return None, error_message
    
    def authenticate(self, code: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """认证用户
        
        Args:
            code: 授权码
            
        Returns:
            (认证结果, 错误信息)
        """
        # 交换令牌
        token_data, error = self.exchange_code_for_token(code)
        if error:
            return None, error
        
        access_token = token_data.get("access_token")
        if not access_token:
            return None, "无法获取访问令牌"
        
        # 获取用户信息
        user_info, error = self.get_user_info(access_token)
        if error:
            return None, error
        
        # 处理用户信息
        google_id = user_info.get("id")
        email = user_info.get("email")
        
        if not google_id or not email:
            return None, "缺少必要的用户信息"
        
        # 查找或创建用户
        user = self.user_repo.find_by_google_id(google_id)
        if not user:
            # 查找是否有相同邮箱的用户
            user = self.user_repo.find_by_email(email)
            
            if user:
                # 更新Google ID
                user = self.user_repo.update_user(user.id, {"google_id": google_id})
            else:
                # 创建新用户
                user_data = {
                    "google_id": google_id,
                    "email": email,
                    "username": user_info.get("name", email.split('@')[0]),
                    "avatar_url": user_info.get("picture"),
                    "status": 1
                }
                user = self.user_repo.create_user(user_data)
                
                if not user:
                    return None, "创建用户失败"
        
        # 更新登录时间
        self.user_repo.update_login_time(user.id)
        
        # 生成JWT令牌
        jwt_token = generate_token({
            "sub": user.id,
            "email": user.email,
            "google_id": user.google_id
        })
        
        # 构建认证结果
        result = {
            "token": jwt_token,
            "user": self.user_repo.user_to_dict(user),
            "google_data": {
                "access_token": access_token,
                "expires_in": token_data.get("expires_in"),
                "token_type": token_data.get("token_type"),
                "refresh_token": token_data.get("refresh_token")
            }
        }
        
        return result, None