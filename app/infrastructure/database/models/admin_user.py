"""用户数据库模型"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from app.core.security import generate_uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLAEnum,
    Integer,
    String,
    Table,
    Text,
)

from app.extensions import db


class AdminUser(db.Model):
    """用户模型"""

    __tablename__ = "admin_users"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    username = Column(String(50), nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Integer, default=1, nullable=False)
    status = Column(Integer, default=1, nullable=False)

    avatar_url = Column(String(255))

    company = Column(String(100))
    title = Column(String(100))
    bio = Column(Text)

    # 系统相关
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # API相关
    api_key = Column(String(64), unique=True, index=True)
    api_secret = Column(String(128))

    def __repr__(self):
        return f"<User {self.username}>"

    @property
    def is_active(self):
        """用户是否处于活跃状态"""
        return self.status == 1

    @property
    def is_admin(self):
        """用户是否为管理员"""
        return self.role == 1
