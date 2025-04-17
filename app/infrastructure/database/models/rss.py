from datetime import datetime, timedelta
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, JSON, Float, func

from app.extensions import db
from app.core.security import generate_uuid


class RssFeed(db.Model):
    """RSS Feed模型"""
    __tablename__ = "rss_feeds"

    id = Column(String(32), primary_key=True, default=generate_uuid)
    url = Column(String(255))
    category_id = Column(Integer)
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
    
    # 新增元数据字段
    language = Column(String(10), comment="语言代码")
    update_frequency = Column(Integer, comment="更新频率(分钟)")
    author = Column(String(100), comment="作者")
    copyright = Column(String(255), comment="版权信息")
    favicon_url = Column(String(255), comment="网站图标URL")
    feed_type = Column(String(50), comment="Feed类型(RSS 1.0, RSS 2.0, Atom等)")
    
    # 抓取控制
    crawl_with_js = Column(Boolean, default=False, comment="是否需要JavaScript渲染")
    crawl_delay = Column(Integer, default=0, comment="抓取延迟(秒)")
    custom_headers = Column(Text, comment="自定义请求头(JSON字符串)")
    
    # 代理相关字段
    use_proxy = Column(Boolean, default=False, comment="是否使用代理")

    
    # 更多统计
    avg_article_length = Column(Integer, comment="平均文章长度(字符)")
    last_new_article_at = Column(DateTime, comment="最近新文章时间")

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class RssFeedCategory(db.Model):
    """RSS Feed分类模型"""
    __tablename__ = "rss_feed_categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    is_delete = Column(Integer, default=0)


class RssFeedArticle(db.Model):
    """RSS Feed文章模型"""
    __tablename__ = "rss_feed_articles"

    id = Column(Integer, primary_key=True)
    feed_id = Column(String(32), nullable=False)
    feed_logo = Column(String(255))
    feed_title = Column(String(255))
    link = Column(Text, nullable=False)
    content_id = Column(Integer)
    status = Column(Integer, nullable=False, comment="1可展示，0待爬取内容")
    title = Column(String(255))
    summary = Column(Text)
    thumbnail_url = Column(String(512))
    published_date = Column(DateTime)
    
    # 爬虫相关字段
    is_locked = Column(Boolean, default=False, comment="是否被锁定(正在爬取)")
    lock_timestamp = Column(DateTime, comment="锁定时间")
    crawler_id = Column(String(255), comment="爬虫标识(机器标识)")
    retry_count = Column(Integer, default=0, comment="重试次数")
    max_retries = Column(Integer, default=3, comment="最大重试次数")
    error_message = Column(Text, comment="错误信息")

    # 向量化相关字段
    is_vectorized = Column(Boolean, default=False, comment="是否已向量化")
    vector_id = Column(String(64), comment="向量库中的ID")
    vectorized_at = Column(DateTime, comment="向量化时间")
    embedding_model = Column(String(100), comment="嵌入模型名称")
    vector_dimension = Column(Integer, comment="向量维度")
    generated_summary = Column(Text, comment="AI生成的摘要")
    vectorization_error = Column(Text, comment="向量化错误信息")
    vectorization_status = Column(Integer, default=0, comment="向量化状态：0=未处理，1=已成功，2=失败，3=正在处理")

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
    batch_id = Column(String(36), nullable=False, comment="关联到批次表")
    
    # 关联信息
    article_id = Column(Integer, nullable=False)
    feed_id = Column(String(32), nullable=False)
    article_url = Column(String(512), nullable=False)
    crawler_id = Column(String(255), nullable=False)
    
    # 执行状态
    status = Column(Integer, nullable=False, comment="1=成功, 2=失败")
    stage = Column(String(50), comment="执行阶段: script_fetch, html_fetch, content_parse, content_save")
    error_type = Column(String(50), comment="错误类型: network_error, timeout, parse_error等")
    error_message = Column(Text)
    retry_count = Column(Integer, default=0, comment="当前重试次数")
    
    # 网络请求信息
    request_started_at = Column(DateTime, comment="请求开始时间")
    request_ended_at = Column(DateTime, comment="请求结束时间")
    request_duration = Column(Float, comment="请求耗时(秒)")
    http_status_code = Column(Integer, comment="HTTP状态码")
    response_headers = Column(Text, comment="响应头信息(JSON)")
    
    # 内容信息
    original_html_length = Column(Integer, comment="原始HTML长度")
    processed_html_length = Column(Integer, comment="处理后HTML长度")
    processed_text_length = Column(Integer, comment="处理后文本长度")
    content_hash = Column(String(64), comment="内容哈希值，用于判断内容是否变化")
    
    # 资源统计
    image_count = Column(Integer, comment="图片数量")
    link_count = Column(Integer, comment="链接数量")
    video_count = Column(Integer, comment="视频数量")
    
    # 浏览器信息
    browser_version = Column(String(50), comment="浏览器版本")
    user_agent = Column(String(255), comment="User Agent")
    
    # 性能指标
    memory_usage = Column(Float, comment="内存使用(MB)")
    cpu_usage = Column(Float, comment="CPU使用率(%)")
    processing_started_at = Column(DateTime, comment="处理开始时间")
    processing_ended_at = Column(DateTime, comment="处理结束时间")
    total_processing_time = Column(Float, comment="总处理时间(秒)")
    parsing_time = Column(Float, comment="解析耗时(秒)")
    
    # 系统信息
    crawler_host = Column(String(255), comment="爬虫所在机器")
    crawler_ip = Column(String(50), comment="爬虫IP")
    
    # 新增监控字段
    script_version = Column(Integer, comment="使用的脚本版本")
    network_type = Column(String(50), comment="网络类型(http, https, etc)")
    content_encoding = Column(String(50), comment="内容编码")
    script_execution_time = Column(Float, comment="脚本执行时间(秒)")
    error_stack_trace = Column(Text, comment="错误堆栈信息")
    crawler_version = Column(String(50), comment="爬虫版本")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class RssFeedArticleCrawlBatch(db.Model):
    """RSS文章爬取批次表 - 记录整体处理结果"""
    __tablename__ = "rss_feed_article_crawl_batches"

    id = Column(Integer, primary_key=True)
    # 批次信息
    batch_id = Column(String(36), nullable=False, unique=True, comment="UUID")
    crawler_id = Column(String(255), nullable=False)
    
    # 文章信息
    article_id = Column(Integer, nullable=False)
    feed_id = Column(String(32), nullable=False)
    article_url = Column(String(512), nullable=False)
    
    # 处理结果
    final_status = Column(Integer, nullable=False, comment="1=成功, 2=失败")
    error_stage = Column(String(50), comment="最后失败的阶段")
    error_type = Column(String(50), comment="最后的错误类型")
    error_message = Column(Text, comment="最后的错误信息")
    retry_count = Column(Integer, default=0)
    
    # 内容信息
    original_html_length = Column(Integer)
    processed_html_length = Column(Integer)
    processed_text_length = Column(Integer)
    content_hash = Column(String(64))
    
    # 性能统计
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime)
    total_processing_time = Column(Float, comment="总处理时间(秒)")
    
    # 资源使用
    max_memory_usage = Column(Float, comment="峰值内存使用(MB)")
    avg_cpu_usage = Column(Float, comment="平均CPU使用率(%)")
    
    # 统计信息
    image_count = Column(Integer)
    link_count = Column(Integer)
    video_count = Column(Integer)
    
    # 系统信息
    crawler_host = Column(String(255))
    crawler_ip = Column(String(50))
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class RssFeedCrawlScript(db.Model):
    """RSS Feed爬取脚本模型"""
    __tablename__ = "rss_feed_crawl_scripts"

    id = Column(Integer, primary_key=True)
    feed_id = Column(String(32), nullable=False)
    group_id = Column(Integer, comment="分组ID，与feed_id互斥")
    script = Column(LONGTEXT)
    version = Column(Integer, default=1, comment="脚本版本号")
    description = Column(String(255), comment="版本描述")
    is_published = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<RssFeedCrawlScript id={self.id}, feed_id={self.feed_id}, is_published={self.is_published}>"


class RssCrawlerAgent(db.Model):
    """爬虫代理实例管理"""
    __tablename__ = "rss_crawler_agents"
    
    id = Column(Integer, primary_key=True)
    agent_id = Column(String(50), unique=True, nullable=False, comment="爬虫实例唯一标识")
    hostname = Column(String(255), comment="主机名")
    ip_address = Column(String(50), comment="IP地址")
    version = Column(String(50), comment="爬虫版本")
    capabilities = Column(Text, comment="爬虫能力(JSON字符串)")
    
    # 状态
    status = Column(Integer, default=1, comment="状态：1=活跃, 2=闲置, 3=离线")
    last_heartbeat = Column(DateTime, comment="最后心跳时间")
    
    # 性能指标
    total_tasks = Column(Integer, default=0, comment="总任务数")
    success_tasks = Column(Integer, default=0, comment="成功任务数")
    failed_tasks = Column(Integer, default=0, comment="失败任务数")
    avg_processing_time = Column(Float, comment="平均处理时间(秒)")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class RssSyncLog(db.Model):
    """RSS同步任务日志模型"""
    __tablename__ = "rss_sync_logs"

    id = Column(Integer, primary_key=True)
    # 同步任务信息
    sync_id = Column(String(36), nullable=False, comment="同步任务ID")
    total_feeds = Column(Integer, default=0, comment="总Feed数量")
    synced_feeds = Column(Integer, default=0, comment="成功同步Feed数量")
    failed_feeds = Column(Integer, default=0, comment="失败Feed数量")
    total_articles = Column(Integer, default=0, comment="新增文章总数")
    status = Column(Integer, default=0, comment="任务状态: 0=进行中, 1=已完成, 2=失败")
    
    # 时间信息
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    total_time = Column(Float, comment="总耗时(秒)")
    
    # 详细信息
    details = Column(JSON, comment="同步详细信息")
    error_message = Column(Text, comment="错误信息")
    triggered_by = Column(String(50), comment="触发方式: schedule=定时任务, manual=手动触发")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<RssSyncLog id={self.id}, sync_id={self.sync_id}, status={self.status}>"
    
class RssFeedArticleVectorizationTask(db.Model):
    """RSS文章向量化任务表"""
    __tablename__ = "rss_feed_article_vectorization_tasks"

    id = Column(Integer, primary_key=True)
    batch_id = Column(String(36), nullable=False, comment="批次ID")
    
    # 任务信息
    total_articles = Column(Integer, default=0, comment="总文章数")
    processed_articles = Column(Integer, default=0, comment="已处理文章数")
    success_articles = Column(Integer, default=0, comment="成功向量化文章数")
    failed_articles = Column(Integer, default=0, comment="失败向量化文章数")
    
    # 任务状态
    status = Column(Integer, default=0, comment="任务状态：0=进行中，1=已完成，2=失败")
    embedding_model = Column(String(100), comment="使用的嵌入模型")
    
    # 时间信息
    started_at = Column(DateTime, default=datetime.now, comment="开始时间")
    ended_at = Column(DateTime, comment="结束时间")
    total_time = Column(Float, comment="总耗时(秒)")
    
    # 错误信息
    error_message = Column(Text, comment="错误信息")
    
    # 其他信息
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<RssFeedArticleVectorizationTask id={self.id}, batch_id={self.batch_id}, status={self.status}>"