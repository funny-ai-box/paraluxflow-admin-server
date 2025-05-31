# app/infrastructure/database/models/user_preferences.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

from app.extensions import db

class UserPreference(db.Model):
    """用户偏好设置模型"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(32), nullable=False, comment="用户ID")
    category = Column(String(50), nullable=False, comment="设置分类")
    setting_key = Column(String(100), nullable=False, comment="设置键名")
    setting_value = Column(Text, comment="设置值")
    value_type = Column(String(20), default='string', comment="值类型")
    is_active = Column(Boolean, default=True, comment="是否启用")
    description = Column(String(255), comment="设置描述")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<UserPreference {self.user_id}.{self.category}.{self.setting_key}>"

class PreferenceDefinition(db.Model):
    """偏好设置定义模型"""
    __tablename__ = "preference_definitions"

    id = Column(Integer, primary_key=True)
    category = Column(String(50), nullable=False, comment="设置分类")
    setting_key = Column(String(100), nullable=False, comment="设置键名")
    setting_name = Column(String(100), nullable=False, comment="设置显示名称")
    description = Column(String(255), comment="设置描述")
    value_type = Column(String(20), default='string', comment="值类型")
    default_value = Column(Text, comment="默认值")
    validation_rules = Column(JSON, comment="验证规则")
    options = Column(JSON, comment="可选值列表")
    is_required = Column(Boolean, default=False, comment="是否必填")
    sort_order = Column(Integer, default=0, comment="排序顺序")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<PreferenceDefinition {self.category}.{self.setting_key}>"