"""RSS Feed数据库模型"""
from datetime import datetime, timedelta
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from app.extensions import db
from app.core.security import generate_uuid


class RssFeed(db.Model):
    """RSS Feed模型"""
    __tablename__ = "rss_feeds"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    url = Column(String(255))
    category_id = Column(Integer)
    group_id = Column(Integer)
    logo = Column(String(255))
    title = Column(String(255))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    last_fetch_at = Column(DateTime, comment="最近一次拉取时间")
    last_fetch_status = Column(Integer, default=0, comment="最近一次拉取状态: 0=未拉取, 1=成功, 2=失败")
    last_fetch_error = Column(Text, comment="最近一次拉取失败原因")
    last_successful_fetch_at = Column(DateTime, comment="最近一次成功拉取时间")
    total_articles_count = Column(Integer, default=0, comment="文章总数")
    consecutive_failures = Column(Integer, default=0, comment="连续失败次数")

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class RssFeedCategory(db.Model):
    """RSS Feed分类模型"""
    __tablename__ = "rss_feed_categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    is_delete = Column(Integer, default=0)


class RssFeedCollection(db.Model):
    """RSS Feed集合模型"""
    __tablename__ = "rss_feed_collections"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    is_delete = Column(Integer, default=0)


class RssFeedCrawlScript(db.Model):
    """RSS Feed爬取脚本模型"""
    __tablename__ = "rss_feed_crawl_scripts"

    id = Column(Integer, primary_key=True)
    feed_id = Column(String(32), nullable=False)

    script = Column(LONGTEXT)
    is_published = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class RssFeedArticle(db.Model):
    """RSS Feed文章模型"""
    __tablename__ = "rss_feed_articles"

    id = Column(Integer, primary_key=True)
    feed_id = Column(String(32), nullable=False)
    feed_logo = Column(String(255))
    feed_title = Column(String(255))
    link = Column(Text, nullable=False)
    content_id = Column(Integer)
    status = Column(Integer, nullable=False)  # 1可展示，0待爬取内容
    title = Column(String(255))
    summary = Column(Text)
    thumbnail_url = Column(String(512))
    published_date = Column(DateTime)
    
    # 爬虫相关字段
    is_locked = Column(Boolean, default=False)  # 是否被锁定(正在爬取)
    lock_timestamp = Column(DateTime)  # 锁定时间
    crawler_id = Column(String(255))  # 爬虫标识(机器标识)
    retry_count = Column(Integer, default=0)  # 重试次数
    max_retries = Column(Integer, default=3)  # 最大重试次数
    error_message = Column(Text)  # 错误信息

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class RssFeedArticleContent(db.Model):
    """RSS Feed文章内容模型"""
    __tablename__ = "rss_feed_article_contents"

    id = Column(Integer, primary_key=True)
    html_content = Column(LONGTEXT, nullable=False)
    text_content = Column(LONGTEXT, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class RssFeedArticleCrawlLog(db.Model):
    """RSS文章爬取日志表"""
    __tablename__ = "rss_feed_article_crawl_logs"

    id = Column(Integer, primary_key=True)
    batch_id = Column(String(36), nullable=False)  # 关联到批次表
    
    # 关联信息
    article_id = Column(Integer, nullable=False)
    feed_id = Column(Integer, nullable=False)
    article_url = Column(String(512), nullable=False)
    crawler_id = Column(String(255), nullable=False)
    
    # 执行状态
    status = Column(Integer, nullable=False)  # 1=成功, 2=失败
    stage = Column(String(50))  # 执行阶段: script_fetch, html_fetch, content_parse, content_save
    error_type = Column(String(50))  # 错误类型: network_error, timeout, parse_error等
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)  # 当前重试次数
    
    # 网络请求信息
    request_started_at = Column(DateTime)  # 请求开始时间
    request_ended_at = Column(DateTime)  # 请求结束时间
    request_duration = Column(db.Float)  # 请求耗时(秒)
    http_status_code = Column(Integer)  # HTTP状态码
    response_headers = Column(Text)  # 响应头信息(JSON)
    
    # 内容信息
    original_html_length = Column(Integer)  # 原始HTML长度
    processed_html_length = Column(Integer)  # 处理后HTML长度
    processed_text_length = Column(Integer)  # 处理后文本长度
    content_hash = Column(String(64))  # 内容哈希值，用于判断内容是否变化
    
    # 资源统计
    image_count = Column(Integer)  # 图片数量
    link_count = Column(Integer)  # 链接数量
    video_count = Column(Integer)  # 视频数量
    
    # 浏览器信息
    browser_version = Column(String(50))  # 浏览器版本
    user_agent = Column(String(255))  # User Agent
    
    # 性能指标
    memory_usage = Column(db.Float)  # 内存使用(MB)
    cpu_usage = Column(db.Float)  # CPU使用率(%)
    processing_started_at = Column(DateTime)  # 处理开始时间
    processing_ended_at = Column(DateTime)  # 处理结束时间
    total_processing_time = Column(db.Float)  # 总处理时间(秒)
    parsing_time = Column(db.Float)  # 解析耗时(秒)
    
    # 系统信息
    crawler_host = Column(String(255))  # 爬虫所在机器
    crawler_ip = Column(String(50))  # 爬虫IP
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class RssFeedArticleCrawlBatch(db.Model):
    """RSS文章爬取批次表 - 记录整体处理结果"""
    __tablename__ = "rss_feed_article_crawl_batches"

    id = Column(Integer, primary_key=True)
    # 批次信息
    batch_id = Column(String(36), nullable=False, unique=True)  # UUID
    crawler_id = Column(String(255), nullable=False)
    
    # 文章信息
    article_id = Column(Integer, nullable=False)
    feed_id = Column(Integer, nullable=False)
    article_url = Column(String(512), nullable=False)
    
    # 处理结果
    final_status = Column(Integer, nullable=False)  # 1=成功, 2=失败
    error_stage = Column(String(50))  # 最后失败的阶段
    error_type = Column(String(50))  # 最后的错误类型
    error_message = Column(Text)  # 最后的错误信息
    retry_count = Column(Integer, default=0)
    
    # 内容信息
    original_html_length = Column(Integer)
    processed_html_length = Column(Integer)
    processed_text_length = Column(Integer)
    content_hash = Column(String(64))
    
    # 性能统计
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime)
    total_processing_time = Column(db.Float)  # 总处理时间(秒)
    
    # 资源使用
    max_memory_usage = Column(db.Float)  # 峰值内存使用(MB)
    avg_cpu_usage = Column(db.Float)  # 平均CPU使用率(%)
    
    # 统计信息
    image_count = Column(Integer)
    link_count = Column(Integer)
    video_count = Column(Integer)
    
    # 系统信息
    crawler_host = Column(String(255))
    crawler_ip = Column(String(50))
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)