"""认证相关存储库"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.admin_user import AdminUser

logger = logging.getLogger(__name__)


class AuthRepository:
    """认证存储库，用于处理登录历史"""

    def __init__(self, db_session: Session):
        """初始化存储库

        Args:
            db_session: 数据库会话
        """
        self.db = db_session


    def register_user(
        self,
        phone: str,
        password_hash: str,
        username: Optional[str] = None,
        **user_data,
    ) -> AdminUser:
        """注册新用户

        Args:
            phone: 手机号码
            password_hash: 哈希密码
            username: 用户名（可选，默认使用手机号）
            **user_data: 其他用户数据

        Returns:
            创建的用户对象

        Raises:
            SQLAlchemyError: 数据库操作失败
        """
        try:
            # 如果未提供用户名，使用手机号
            if not username:
                username = phone
            print(username)
            # 创建用户对象
            user = AdminUser(
                username=username,
                phone=phone,
                password_hash=password_hash,
                role=1,
                status=1,
                **user_data,
            )

            # 保存到数据库
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

            logger.info(f"Registered new user with phone: {phone}")
            return user
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to register user: {str(e)}")
            raise

    def find_user_by_phone(self, phone: str) -> Optional[AdminUser]:
        """通过手机号查找用户

        Args:
            phone: 手机号码

        Returns:
            用户对象或None
        """
        print("find_user_by_phone")
        try:
            return self.db.query(AdminUser).filter(AdminUser.phone == phone).first()
        except SQLAlchemyError as e:
            print(e)
            logger.error(f"Error finding user by phone: {str(e)}")
            return None
