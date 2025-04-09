# app/api/v1/rss/crawler.py
"""RSS爬虫API控制器"""
import logging
import os
import socket
import uuid

from flask import Blueprint, request, g, current_app
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import error_response, success_response
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss_crawler_repository import RssCrawlerRepository
from app.infrastructure.database.repositories.rss_script_repository import RssFeedCrawlScriptRepository
from app.domains.rss.services.crawler_service import CrawlerService

logger = logging.getLogger(__name__)

# 创建蓝图
crawler_bp = Blueprint("crawler", __name__)


@crawler_bp.route("/logs", methods=["GET"])
@app_key_required
def get_crawl_logs():
    """获取抓取日志"""
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
        return error_response(60001, f"获取抓取日志失败: {str(e)}")

@crawler_bp.route("/stats", methods=["GET"])
@app_key_required
def get_crawler_stats():
    """获取爬虫统计信息"""
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
        return error_response(60001, f"获取爬虫统计信息失败: {str(e)}")

@crawler_bp.route("/reset_batch", methods=["POST"])
@app_key_required
def reset_batch():
    """重置批次状态"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "batch_id" not in data:
            return error_response(60001, "缺少batch_id参数")
        
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
        return error_response(60001, f"重置批次状态失败: {str(e)}")