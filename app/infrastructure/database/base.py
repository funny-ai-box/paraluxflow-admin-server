"""数据库模型基类"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.inspection import inspect
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import Column, DateTime, func
from datetime import datetime

# 创建模型基类
Base = declarative_base()

class TimestampMixin:
    """时间戳混入类，用于记录创建和更新时间"""
    
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

class ModelBase(Base):
    """模型基类，提供通用功能"""
    
    __abstract__ = True
    
    @declared_attr
    def __tablename__(cls):
        """默认使用类名的小写形式作为表名"""
        return cls.__name__.lower()
    
    @property
    def json(self):
        """返回模型的JSON表示"""
        return {c.key: getattr(self, c.key)
                for c in inspect(self).mapper.column_attrs}
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建模型实例"""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})
    
    def update_from_dict(self, data):
        """从字典更新模型实例"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)