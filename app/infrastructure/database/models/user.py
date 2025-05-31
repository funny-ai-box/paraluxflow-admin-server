# app/infrastructure/database/models/user.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON

from app.extensions import db
from app.core.security import generate_uuid

class User(db.Model):
    """用户模型"""
    __tablename__ = "app_users"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    google_id = Column(String(100), unique=True, nullable=True, comment="Google账户ID")
    email = Column(String(255), unique=True, nullable=False, comment="用户邮箱")
    # --- Add password_hash field ---
    password_hash = Column(String(255), nullable=True, comment="邮箱密码哈希")
    # -----------------------------
    username = Column(String(100), comment="用户名")
    avatar_url = Column(String(512), comment="头像URL")
    status = Column(Integer, default=1, comment="状态: 1=正常, 0=禁用")
    last_login_at = Column(DateTime, comment="最后登录时间")
 
    # 统计信息
    subscription_count = Column(Integer, default=0, comment="订阅源数量")
    reading_count = Column(Integer, default=0, comment="已读文章数量")
    favorite_count = Column(Integer, default=0, comment="收藏文章数量")

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<User {self.email}>"

class UserSubscription(db.Model):
    """用户订阅模型"""
    __tablename__ = "user_subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(32), nullable=False, comment="用户ID")
    feed_id = Column(String(32), nullable=False, comment="Feed ID")
    group_id = Column(Integer, comment="分组ID")
    is_favorite = Column(Boolean, default=False, comment="是否收藏")
    custom_title = Column(String(255), comment="自定义标题")
    read_count = Column(Integer, default=0, comment="已读文章数")
    unread_count = Column(Integer, default=0, comment="未读文章数")
    last_read_at = Column(DateTime, comment="最后阅读时间")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<UserSubscription user_id={self.user_id}, feed_id={self.feed_id}>"

class UserReadingHistory(db.Model):
    """用户阅读历史模型"""
    __tablename__ = "user_reading_history"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(32), nullable=False, comment="用户ID")
    article_id = Column(Integer, nullable=False, comment="文章ID")
    feed_id = Column(String(32), nullable=False, comment="Feed ID")
    is_favorite = Column(Boolean, default=False, comment="是否收藏")
    is_read = Column(Boolean, default=True, comment="是否已读")
    read_position = Column(Integer, default=0, comment="阅读位置")
    read_progress = Column(Integer, default=0, comment="阅读进度(百分比)")
    read_time = Column(Integer, default=0, comment="阅读时间(秒)")
    last_read_at = Column(DateTime,default=datetime.now,onupdate=datetime.now, comment="最后阅读时间")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<UserReadingHistory user_id={self.user_id}, article_id={self.article_id}>"

