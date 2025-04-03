"""文章摘要相关数据库模型"""
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, Boolean,JSON, Float

from app.extensions import db
from app.core.security import generate_uuid


class ArticleDigest(db.Model):
    """文章摘要模型"""
    __tablename__ = "article_digests"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    user_id = Column(String(32), nullable=False, comment="所属用户ID")
    title = Column(String(255), nullable=False, comment="摘要标题")
    content = Column(Text, nullable=False, comment="摘要内容")
    article_count = Column(Integer, default=0, comment="总结的文章数量")
    source_date = Column(DateTime, comment="源文章的日期")
    digest_type = Column(String(50), default="daily", comment="摘要类型: daily, weekly, custom")
    
    # 元数据
    meta_info = Column(JSON, nullable=True, comment="元数据，如使用的模型、处理时间等")
    
    # 状态
    status = Column(Integer, default=1, comment="状态: 0=生成中, 1=已完成, 2=失败")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DigestRule(db.Model):
    """摘要生成规则模型"""
    __tablename__ = "digest_rules"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    user_id = Column(String(32), nullable=False, comment="所属用户ID")
    name = Column(String(100), nullable=False, comment="规则名称")
    
    # 规则配置
    digest_type = Column(String(50), default="daily", comment="摘要类型: daily, weekly, custom")
    feed_filter = Column(JSON, nullable=True, comment="RSS源筛选条件")
    article_filter = Column(JSON, nullable=True, comment="文章筛选条件")
    
    # 摘要生成配置
    summary_length = Column(Integer, default=300, comment="摘要长度")
    include_categories = Column(Boolean, default=True, comment="是否按分类汇总")
    include_keywords = Column(Boolean, default=True, comment="是否包含关键词")
    
    # 大模型配置
    provider_type = Column(String(50), nullable=True, comment="AI提供商类型，如openai, anthropic, volcano")
    model_id = Column(String(100), nullable=True, comment="模型标识符，如gpt-4o")
    temperature = Column(Float, default=0.7, comment="温度参数(0-1)")
    max_tokens = Column(Integer, default=1500, comment="最大生成的令牌数量")
    top_p = Column(Float, default=1.0, comment="核采样参数(0-1)")
    
    # 调度配置
    schedule_time = Column(String(50), default="03:00", comment="调度时间，格式HH:MM")
    is_active = Column(Boolean, default=True, comment="是否启用")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DigestArticleMapping(db.Model):
    """摘要与文章的映射关系"""
    __tablename__ = "digest_article_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    digest_id = Column(String(32), nullable=False, comment="摘要ID")
    article_id = Column(Integer, nullable=False, comment="文章ID")
    
    # 文章在摘要中的位置
    section = Column(String(100), nullable=True, comment="文章在摘要中的分类")
    summary = Column(Text, nullable=True, comment="文章的单独摘要")
    rank = Column(Integer, default=0, comment="文章在分类中的排序")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)