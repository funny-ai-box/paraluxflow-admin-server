# app/domains/auth/services/firebase_auth_service.py
"""Firebase认证服务实现 - JWT方式"""
import logging
from typing import Dict, Any, Optional, Tuple

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from flask import current_app

from app.infrastructure.database.repositories.user_repository import UserRepository
from app.core.security import generate_token

logger = logging.getLogger(__name__)

class FirebaseAuthService:
    """Firebase认证服务 - JWT方式"""
    
    def __init__(self, user_repository: UserRepository):
        """初始化服务
        
        Args:
            user_repository: 用户仓库
        """
        self.user_repo = user_repository
        
        # 初始化Firebase Admin SDK (如果尚未初始化)
        if not firebase_admin._apps:
            # 从环境变量或配置中获取凭证
            firebase_config = current_app.config.get("FIREBASE_CONFIG")
            print(firebase_config)
            if firebase_config:
                cred = credentials.Certificate(firebase_config)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK已初始化")
            else:
                logger.warning("未找到Firebase配置，使用默认服务账号凭证")
                firebase_admin.initialize_app()
    
    def verify_id_token(self, id_token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """验证Firebase ID令牌
        
        Args:
            id_token: Firebase ID令牌
            
        Returns:
            (用户信息, 错误信息)
        """
        try:
            # 验证令牌
            decoded_token = firebase_auth.verify_id_token(id_token)
            print(f"令牌验证成功: {decoded_token}")
            if not decoded_token:
                print("无效的令牌")
                return None, "无效的令牌"
            
            return decoded_token, None
        except ValueError as e:
            logger.error(f"令牌验证失败: {str(e)}")
            return None, f"令牌验证失败: {str(e)}"
        except Exception as e:
            logger.error(f"令牌验证过程中发生错误: {str(e)}")
            return None, f"令牌验证错误: {str(e)}"
    
    def authenticate_user(self, id_token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
        """认证用户并获取或创建用户记录，生成JWT令牌
        
        Args:
            id_token: Firebase ID令牌
            
        Returns:
            (用户信息, JWT令牌, 错误信息)
        """
        # 验证令牌
        decoded_token, error = self.verify_id_token(id_token)
        if error:
            return None, None, error
        
        # 提取用户信息
        uid = decoded_token.get("uid")
        email = decoded_token.get("email")
        name = decoded_token.get("name")
        picture = decoded_token.get("picture")
        
        if not uid or not email:
            return None, None, "令牌中缺少必要的用户信息"
        
        # 查找用户
        user = self.user_repo.find_by_google_id(uid)
        
        # 如果用户不存在，创建新用户
        if not user:
            # 查找是否有相同邮箱的用户
            user = self.user_repo.find_by_email(email)
            
            if user:
                # 更新Google ID
                user = self.user_repo.update_user(user.id, {"google_id": uid})
            else:
                # 创建新用户
                user_data = {
                    "google_id": uid,
                    "email": email,
                    "username": name or email.split('@')[0],
                    "avatar_url": picture,
                    "status": 1
                }
                user = self.user_repo.create_user(user_data)
                
                if not user:
                    return None, None, "创建用户失败"
        
        # 更新登录时间
        self.user_repo.update_login_time(user.id)
        
        # 生成JWT令牌
        jwt_token = generate_token({
            "sub": user.id,
            "email": user.email,
            "google_id": user.google_id,
            "firebase_uid": uid
        })
        
        # 转换用户对象为字典
        user_dict = self.user_repo.user_to_dict(user)
        
        return user_dict, jwt_token, None