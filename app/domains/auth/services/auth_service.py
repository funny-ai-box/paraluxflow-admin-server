"""认证服务实现"""

import logging
import random
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, Union

import jwt
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash

from app.core.exceptions import (
    APIException,
    AuthenticationException,
    ValidationException,
)
from app.core.status_codes import (
    AUTH_FAILED,
    USER_ALREADY_EXISTS,
)
from app.infrastructure.database.repositories.auth_repository import AuthRepository
from app.infrastructure.database.repositories.admin_user_repository import UserRepository
from app.utils.rsa_util import decrypt_with_private_key

logger = logging.getLogger(__name__)


class AuthService:
    """认证服务实现"""

    def __init__(
        self,
        auth_repository: AuthRepository,
        user_repository: Optional[UserRepository] = None,
    ):
        """初始化认证服务

        Args:
            auth_repository: 认证存储库
            user_repository: 用户存储库(可选)
        """
        self.auth_repo = auth_repository
        self.user_repo = user_repository

    def generate_verification_code(self, phone: str, purpose: str) -> str:
        """生成并发送手机验证码

        Args:
            phone: 手机号码
            purpose: 用途，如login, register, reset_password

        Returns:
            生成的验证码

        Raises:
            ValidationException: 手机号格式不正确
            APIException: 验证码生成失败
        """
        # 验证手机号格式
        if not self._validate_phone(phone):
            raise ValidationException("手机号格式不正确:{PARAMETER_ERROR}")

        # 生成验证码
        code = self._generate_random_code(6)

        try:
            # 保存验证码
            self.auth_repo.create_verification_code(phone, code, purpose)

            # TODO: 集成短信发送服务
            # 这里应该调用短信API发送验证码
            # 目前仅记录日志
            logger.info(f"SMS code for {phone}: {code}")

            return code
        except Exception as e:
            logger.error(f"Failed to generate verification code: {str(e)}")
            raise APIException("验证码生成失败", AUTH_FAILED)

    def register_with_phone_password(
        self, phone: str, encrypted_password: str, username: Optional[str] = None
    ) -> Dict[str, Any]:
        """手机号密码注册

        Args:
            phone: 手机号码
            encrypted_password: RSA加密的密码
            username: 用户名(可选)

        Returns:
            用户信息和JWT令牌

        Raises:
            ValidationException: 参数验证失败
            APIException: 注册失败
        """
        # 验证手机号格式
        if not self._validate_phone(phone):
            raise ValidationException("手机号格式不正确")

        # 解密密码
        try:
            password = decrypt_with_private_key(encrypted_password)
            print(password)
        except Exception as e:

            logger.error(f"Password decryption failed: {str(e)}")
            raise ValidationException("密码解密失败")
        print("------1----------------")

        # 检查手机号是否已注册
        if self.auth_repo.find_user_by_phone(phone):

            raise APIException("该手机号已注册", USER_ALREADY_EXISTS)

        try:
            # 密码加盐哈希
            password_hash = generate_password_hash(password, method="pbkdf2:sha256")
            print(password_hash)

            # 注册用户
            user = self.auth_repo.register_user(
                phone=phone, password_hash=password_hash, username=username or phone
            )

            # 生成JWT令牌
            token = self._generate_jwt_token(user)

            return {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "phone": user.phone,
                    "role": user.role,
                    "status": user.status,
                    "created_at": (
                        user.created_at.isoformat() if user.created_at else None
                    ),
                },
                "token": token,
            }
        except Exception as e:
            print("注册失败")
            print(e)
            logger.error(f"Registration failed: {str(e)}")
            raise APIException(f"注册失败: {str(e)}", AUTH_FAILED)

    def login_with_phone_password(
        self,
        phone: str,
        encrypted_password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """手机号密码登录

        Args:
            phone: 手机号码
            encrypted_password: RSA加密的密码
            ip_address: IP地址
            user_agent: 用户代理

        Returns:
            用户信息和JWT令牌

        Raises:
            AuthenticationException: 认证失败
        """
        try:
            # 查找用户
            user = self.auth_repo.find_user_by_phone(phone)

            if not user:
                logger.warning(f"Login failed: User not found - {phone}")
                # 记录登录失败

                raise ValidationException("手机号或密码不正确")

            # 检查用户状态
            if user.status != 1:
                logger.warning(f"Login failed: User not active - {phone}")
                # 记录登录失败
 
                raise ValidationException("账户不可用或已被锁定")

            # 解密密码
            try:
                password = decrypt_with_private_key(encrypted_password)
            except Exception as e:
                logger.error(f"Password decryption failed: {str(e)}")
                # 记录登录失败

                raise ValidationException("密码解密失败")

            # 验证密码
            if not check_password_hash(user.password_hash, password):
                logger.warning(f"Login failed: Invalid password - {phone}")
                # 记录登录失败
  
                raise ValidationException("手机号或密码不正确")

            # 生成访问令牌
            token = self._generate_jwt_token(user)

            # 更新最后登录时间
            user.last_login_at = datetime.utcnow()
            if self.user_repo:
                self.user_repo.update(user)
            else:
                self.auth_repo.db.commit()

            # 记录登录成功


            logger.info(f"User logged in successfully: {user.username}")

            return {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "phone": user.phone,
                    "role": user.role,
                    "status": user.status,
                    "last_login_at": (
                        user.last_login_at.isoformat() if user.last_login_at else None
                    ),
                },
                "token": token,
            }

        except Exception as e:
            if isinstance(e, (AuthenticationException, ValidationException)):
                raise
            print(e)
            logger.error(f"Login error: {str(e)}")
            raise ValidationException("登录过程中发生错误")

    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """验证JWT令牌

        Args:
            token: JWT令牌

        Returns:
            解码后的令牌数据

        Raises:
            AuthenticationException: 令牌无效或已过期
        """
        try:
            # 解码令牌
            secret_key = current_app.config.get("JWT_SECRET_KEY")
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])

            # 检查必要字段
            if "sub" not in payload or "exp" not in payload:
                raise AuthenticationException("无效的12令牌")

            # 检查是否过期
            exp_timestamp = payload["exp"]
            if datetime.utcnow().timestamp() > exp_timestamp:
                raise AuthenticationException("令牌已过期")

            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationException("令牌已过期")
        except jwt.InvalidTokenError:
            raise AuthenticationException("无效的3令牌")
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            raise AuthenticationException("令牌验证失败")

    def _generate_jwt_token(self, user) -> str:
        """生成JWT令牌

        Args:
            user: 用户对象

        Returns:
            JWT令牌
        """
        now = datetime.utcnow()
        token_ttl = current_app.config.get(
            "JWT_ACCESS_TOKEN_EXPIRES", timedelta(hours=144)
        )

        payload = {
            "sub": user.id,
            "iat": now,
            "exp": now + token_ttl,
            "username": user.username,
            "role": user.role,
        }

        secret_key = current_app.config.get("JWT_SECRET_KEY")
        return jwt.encode(payload, secret_key, algorithm="HS256")

    def _validate_phone(self, phone: str) -> bool:
        """验证手机号格式

        Args:
            phone: 手机号码

        Returns:
            是否为有效的手机号
        """
        # 中国大陆手机号正则表达式
        pattern = r"^1[3-9]\d{9}$"
        return bool(re.match(pattern, phone))

    def generate_verification_code(self, phone: str, purpose: str) -> str:
        """生成并发送手机验证码 - 保留接口但暂不实现功能

        Args:
            phone: 手机号码
            purpose: 用途，如login, register, reset_password

        Returns:
            生成的验证码

        Raises:
            ValidationException: 手机号格式不正确
            APIException: 验证码生成失败
        """
        raise APIException("验证码功能暂未实现", AUTH_FAILED)

    def _generate_random_code(self, length: int = 6) -> str:
        """生成随机验证码

        Args:
            length: 验证码长度

        Returns:
            随机验证码
        """
        # 生成指定长度的数字验证码
        return "".join(random.choice("0123456789") for _ in range(length))

    def _check_password_strength(self, password: str) -> bool:
        """检查密码强度

        Args:
            password: 密码

        Returns:
            密码是否足够强
        """
        # 至少8位
        if len(password) < 8:
            return False

        # 包含数字
        if not any(char.isdigit() for char in password):
            return False

        # 包含字母
        if not any(char.isalpha() for char in password):
            return False

        # 包含特殊字符
        if not any(not char.isalnum() for char in password):
            return False

        return True
