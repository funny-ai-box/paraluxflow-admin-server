# app/api/v1/rss/crawler.py
"""RSS爬虫API控制器"""
import logging
import socket
import uuid
from flask import Blueprint, request, g
from flasgger import swag_from

from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss_crawler_repository import RssCrawlerRepository
from app.infrastructure.database.repositories.rss_script_repository import RssFeedCrawlScriptRepository
from app.domains.rss.services.crawler_service import CrawlerService

logger = logging.getLogger(__name__)

# 创建蓝图
crawler_bp = Blueprint("crawler", __name__)

@crawler_bp.route("/pending_articles", methods=["GET"])
@app_key_required
def get_pending_articles():
    """获取待抓取的文章列表
    
    查询参数:
    - limit: 获取数量，默认10
    
    Returns:
        待抓取文章列表
    """
    try:
        # 获取请求参数
        limit = request.args.get("limit", 10, type=int)
        
        # 获取爬虫标识
        crawler_id = request.headers.get("X-Crawler-ID") or socket.gethostname()
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        crawler_repo = RssCrawlerRepository(db_session)
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        crawler_service = CrawlerService(article_repo, content_repo, crawler_repo, script_repo)
        
        # 获取待抓取文章
        articles = crawler_service.get_pending_articles(limit, crawler_id)
        
        return success_response(articles)
    except Exception as e:
        logger.error(f"获取待抓取文章失败: {str(e)}")
        return success_response(None, f"获取待抓取文章失败: {str(e)}", 60001)

@crawler_bp.route("/claim_article", methods=["POST"])
@app_key_required
def claim_article():
    #认领(锁定)文章进行抓取
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "article_id" not in data:
            return success_response(None, "缺少article_id参数", 60001)
        
        article_id = data["article_id"]
        
        # 获取爬虫标识
        crawler_id = request.headers.get("X-Crawler-ID") or socket.gethostname()
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        crawler_repo = RssCrawlerRepository(db_session)
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        crawler_service = CrawlerService(article_repo, content_repo, crawler_repo, script_repo)
        
        # 认领文章
        result = crawler_service.claim_article(article_id, crawler_id)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"认领文章失败: {str(e)}")
        return success_response(None, f"认领文章失败: {str(e)}", 60001)

@crawler_bp.route("/submit_result", methods=["POST"])
@app_key_required
def submit_crawl_result():
    """提交抓取结果
    
    请求体:
    {
        "article_id": 1,              # 文章ID
        "batch_id": "uuid",           # 批次ID，不提供则自动生成
        "status": 1,                  # 状态：1=成功, 2=失败
        "error_message": "",          # 失败信息
        "error_type": "",             # 错误类型
        "html_content": "",           # 抓取到的HTML内容
        "text_content": "",           # 处理后的文本内容
        "processing_time": 1.5,       # 处理时间(秒)
        "request_time": 0.8,          # 请求时间(秒)
        "http_status": 200,           # HTTP状态码
        "memory_usage": 150,          # 内存使用(MB)
        "image_count": 5              # 图片数量
    }
    
    Returns:
        抓取结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "article_id" not in data:
            return success_response(None, "缺少article_id参数", 60001)
        
        # 获取爬虫标识
        crawler_id = request.headers.get("X-Crawler-ID") or socket.gethostname()
        
        # 生成批次ID
        batch_id = data.get("batch_id") or str(uuid.uuid4())
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        crawler_repo = RssCrawlerRepository(db_session)
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        crawler_service = CrawlerService(article_repo, content_repo, crawler_repo, script_repo)
        
        # 提交抓取结果
        result = crawler_service.submit_crawl_result(
            article_id=data["article_id"],
            crawler_id=crawler_id,
            batch_id=batch_id,
            result_data=data
        )
        
        return success_response(result)
    except Exception as e:
        logger.error(f"提交抓取结果失败: {str(e)}")
        return success_response(None, f"提交抓取结果失败: {str(e)}", 60001)

@crawler_bp.route("/logs", methods=["GET"])
@app_key_required
def get_crawl_logs():
    """获取抓取日志
    
    查询参数:
    - page: 页码，默认1
    - per_page: 每页数量，默认20
    - article_id: 文章ID
    - batch_id: 批次ID
    - crawler_id: 爬虫ID
    - status: 状态
    - start_date: 开始日期
    - end_date: 结束日期
    
    Returns:
        日志列表和分页信息
    """
    try:
        # 获取分页参数
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        
        # 构建筛选条件
        filters = {}
        
        # 文章ID筛选
        article_id = request.args.get("article_id", type=int)
        if article_id:
            filters["article_id"] = article_id
        
        # 批次ID筛选
        batch_id = request.args.get("batch_id")
        if batch_id:
            filters["batch_id"] = batch_id
        
        # 爬虫ID筛选
        crawler_id = request.args.get("crawler_id")
        if crawler_id:
            filters["crawler_id"] = crawler_id
        
        # 状态筛选
        status = request.args.get("status", type=int)
        if status:
            filters["status"] = status
        
        # 日期范围筛选
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        if start_date or end_date:
            filters["date_range"] = (start_date, end_date)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        crawler_repo = RssCrawlerRepository(db_session)
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        crawler_service = CrawlerService(article_repo, content_repo, crawler_repo, script_repo)
        
        # 获取抓取日志
        logs = crawler_service.get_crawl_logs(filters, page, per_page)
        
        return success_response(logs)
    except Exception as e:
        logger.error(f"获取抓取日志失败: {str(e)}")
        return success_response(None, f"获取抓取日志失败: {str(e)}", 60001)

@crawler_bp.route("/stats", methods=["GET"])
@app_key_required
def get_crawler_stats():
    """获取爬虫统计信息
    
    查询参数:
    - time_range: 时间范围，可选：today, yesterday, last7days, last30days，默认today
    
    Returns:
        爬虫统计信息
    """
    try:
        # 获取时间范围
        time_range = request.args.get("time_range", "today")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        crawler_repo = RssCrawlerRepository(db_session)
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        crawler_service = CrawlerService(article_repo, content_repo, crawler_repo, script_repo)
        
        # 获取爬虫统计信息
        stats = crawler_service.get_crawler_stats(time_range)
        
        return success_response(stats)
    except Exception as e:
        logger.error(f"获取爬虫统计信息失败: {str(e)}")
        return success_response(None, f"获取爬虫统计信息失败: {str(e)}", 60001)

@crawler_bp.route("/reset_batch", methods=["POST"])
@app_key_required
def reset_batch():
    """重置批次状态
    
    请求体:
    {
        "batch_id": "uuid"  # 批次ID
    }
    
    Returns:
        操作结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "batch_id" not in data:
            return success_response(None, "缺少batch_id参数", 60001)
        
        batch_id = data["batch_id"]
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        crawler_repo = RssCrawlerRepository(db_session)
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        crawler_service = CrawlerService(article_repo, content_repo, crawler_repo, script_repo)
        
        # 重置批次状态
        result = crawler_service.reset_batch(batch_id)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"重置批次状态失败: {str(e)}")
        return success_response(None, f"重置批次状态失败: {str(e)}", 60001)