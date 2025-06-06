# app/domains/auth/services/client_auth_service.py
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.infrastructure.database.repositories.user_repository import UserRepository
from app.core.exceptions import ValidationException, AuthenticationException
from app.core.status_codes import USER_ALREADY_EXISTS, AUTH_FAILED
from app.core.security import create_password_hash, verify_password, generate_token
from app.utils.rsa_util import decrypt_with_private_key
from app.utils.validators import is_email

logger = logging.getLogger(__name__)

class ClientAuthService:
    """客户端认证服务 (Email/Password)"""

    def __init__(self, user_repository: UserRepository):
        self.user_repo = user_repository

    def register_with_email_password(
        self, email: str, password: str, username: Optional[str] = None
    ) -> Dict[str, Any]:
        """邮箱密码注册"""
        if not is_email(email):
            raise ValidationException("无效的邮箱格式")



        # Check if email exists
        existing_user = self.user_repo.find_by_email(email)
        if existing_user:
            # If user exists via Google/Firebase but no password, allow setting password
            if existing_user.password_hash is None:
                 password_hash = create_password_hash(password)
                 updated_user = self.user_repo.update_user(existing_user.id, {"password_hash": password_hash})
                 if not updated_user:
                      raise AuthenticationException("更新用户密码失败")
                 logger.info(f"为现有用户 {email} 设置了密码")
                 # Generate JWT token for immediate login after setting password
                 token = generate_token({
                    "sub": updated_user.id,
                    "email": updated_user.email,
                    "google_id": updated_user.google_id
                 })
                 return {
                    "user": self.user_repo.user_to_dict(updated_user),
                    "token": token,
                    "message": "密码设置成功"
                 }
            else:
                raise ValidationException("该邮箱已被注册", USER_ALREADY_EXISTS)


        # Hash password
        password_hash = create_password_hash(password)

        # Create user
        user_data = {
            "email": email,
            "password_hash": password_hash,
            "username": username or email.split('@')[0],
            "status": 1
        }
        user = self.user_repo.create_user(user_data)
        if not user:
            raise AuthenticationException("创建用户失败")

        logger.info(f"新用户注册成功: {email}")

        # Generate JWT token
        token = generate_token({
            "sub": user.id,
            "email": user.email,
            "google_id": user.google_id # Include google_id if available
        })

        return {
            "user": self.user_repo.user_to_dict(user),
            "token": token
        }

    def login_with_email_password(
        self, email: str, password: str
    ) -> Dict[str, Any]:
        """邮箱密码登录"""
        if not is_email(email):
            raise ValidationException("无效的邮箱格式")

        # Find user
        user = self.user_repo.find_by_email(email)
        if not user or not user.password_hash:
            raise AuthenticationException("邮箱或密码错误")

        if user.status != 1:
             raise AuthenticationException("账户不可用")



        # Verify password
        if not verify_password(user.password_hash, password):
            raise AuthenticationException("邮箱或密码错误")

        # Update last login time
        self.user_repo.update_login_time(user.id)

        # Generate JWT token
        token = generate_token({
            "sub": user.id,
            "email": user.email,
            "google_id": user.google_id
        })

        logger.info(f"用户登录成功: {email}")

        return {
            "user": self.user_repo.user_to_dict(user),
            "token": token
        }