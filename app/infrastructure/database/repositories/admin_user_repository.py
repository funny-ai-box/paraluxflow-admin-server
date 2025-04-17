"""用户数据存储库"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.orm import Session
from app.infrastructure.database.models.admin_user import AdminUser
from app.infrastructure.database.models.user import User

logger = logging.getLogger(__name__)


class UserRepository:
    """用户数据存储库，负责用户相关数据的持久化操作"""

    def __init__(self, db_session: Session):
        """初始化存储库

        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def create(self, user: AdminUser) -> AdminUser:
        try:
            self.db.add(user)  # 正确: 直接使用 self.db
            self.db.commit()  # 正确: 直接使用 self.db
            logger.info(f"Created user: {user.username}")
            return user
        except SQLAlchemyError as e:
            self.db.rollback()  # 正确: 直接使用 self.db
            logger.error(f"Failed to create user: {str(e)}")
            raise

    def update(self, user: AdminUser) -> AdminUser:
        """更新用户信息

        Args:
            user: 用户对象

        Returns:
            更新后的用户对象

        Raises:
            SQLAlchemyError: 数据库操作失败
        """
        try:
            user.updated_at = datetime.now()
            self.db.commit()
            logger.info(f"Updated user: {user.username}")
            return user
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to update user: {str(e)}")
            raise

    def delete(self, user_id: str) -> bool:
        """删除用户

        Args:
            user_id: 用户ID

        Returns:
            是否成功删除

        Raises:
            SQLAlchemyError: 数据库操作失败
        """
        try:
            user = self.find_by_id(user_id)
            if not user:
                logger.warning(f"Cannot delete user: User with ID {user_id} not found")
                return False

            self.db.delete(user)
            self.db.commit()
            logger.info(f"Deleted user: {user.username}")
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to delete user: {str(e)}")
            raise

    def find_by_id(self, user_id: str) -> Optional[AdminUser]:
        """通过ID查找用户

        Args:
            user_id: 用户ID

        Returns:
            用户对象或None
        """
        try:
            return AdminUser.query.get(user_id)
        except SQLAlchemyError as e:
            logger.error(f"Error finding user by ID: {str(e)}")
            return None

    def find_by_username(self, username: str) -> Optional[AdminUser]:
        """通过用户名查找用户

        Args:
            username: 用户名

        Returns:
            用户对象或None
        """
        try:
            return User.query.filter_by(username=username).first()
        except SQLAlchemyError as e:
            logger.error(f"Error finding user by username: {str(e)}")
            return None

    def find_by_email(self, email: str) -> Optional[AdminUser]:
        """通过邮箱查找用户

        Args:
            email: 邮箱

        Returns:
            用户对象或None
        """
        try:
            return AdminUser.query.filter_by(email=email).first()
        except SQLAlchemyError as e:
            logger.error(f"Error finding user by email: {str(e)}")
            return None

    def find_by_username_or_email(self, username_or_email: str) -> Optional[AdminUser]:
        """通过用户名或邮箱查找用户

        Args:
            username_or_email: 用户名或邮箱

        Returns:
            用户对象或None
        """
        try:
            return AdminUser.query.filter(
                (AdminUser.username == username_or_email) | (AdminUser.email == username_or_email)
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error finding user by username or email: {str(e)}")
            return None

    def find_by_reset_token(self, token: str) -> Optional[AdminUser]:
        """通过密码重置令牌查找用户

        Args:
            token: 重置令牌

        Returns:
            用户对象或None
        """
        try:
            return AdminUser.query.filter_by(reset_password_token=token).first()
        except SQLAlchemyError as e:
            logger.error(f"Error finding user by reset token: {str(e)}")
            return None

    def find_by_email_verification_token(self, token: str) -> Optional[AdminUser]:
        """通过邮箱验证令牌查找用户

        Args:
            token: 验证令牌

        Returns:
            用户对象或None
        """
        try:
            return AdminUser.query.filter_by(email_verification_token=token).first()
        except SQLAlchemyError as e:
            logger.error(f"Error finding user by email verification token: {str(e)}")
            return None

    def find_all(
        self, page: int = 1, per_page: int = 20, **filters
    ) -> tuple[List[AdminUser], int]:
        """查询用户列表

        Args:
            page: 页码
            per_page: 每页记录数
            **filters: 过滤条件

        Returns:
            (用户列表, 总记录数)
        """
        try:
            query = AdminUser.query

            # 应用过滤条件
            if "username" in filters and filters["username"]:
                query = query.filter(AdminUser.username.like(f"%{filters['username']}%"))

            if "email" in filters and filters["email"]:
                query = query.filter(AdminUser.email.like(f"%{filters['email']}%"))

            if "role" in filters and filters["role"]:
                query = query.filter(AdminUser.role == filters["role"])

            if "status" in filters and filters["status"]:
                query = query.filter(AdminUser.status == filters["status"])

            # 计算总记录数
            total = query.count()

            # 应用分页
            users = (
                query.order_by(AdminUser.created_at.desc())
                .paginate(page=page, per_page=per_page)
                .items
            )

            return users, total
        except SQLAlchemyError as e:
            logger.error(f"Error finding users: {str(e)}")
            return [], 0

 