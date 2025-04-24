# app/api/v1/rss/crawler.py
"""RSS爬虫API控制器"""
import logging
import os
import socket
import uuid

from app.api.middleware.auth import auth_required
from app.core.status_codes import PARAMETER_ERROR
from flask import Blueprint, request, g, current_app

from app.core.responses import error_response, success_response
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss.rss_crawler_repository import RssCrawlerRepository
from app.infrastructure.database.repositories.rss.rss_script_repository import RssFeedCrawlScriptRepository
from app.infrastructure.database.repositories.rss.rss_feed_repository import RssFeedRepository
from app.domains.rss.services.crawler_service import CrawlerService

logger = logging.getLogger(__name__)

# 创建蓝图
crawler_bp = Blueprint("crawler", __name__)


@crawler_bp.route("/logs", methods=["GET"])
@auth_required
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
@auth_required
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


@crawler_bp.route("/analyze", methods=["GET"])
@auth_required
def analyze_crawler_performance():
    """分析爬虫性能和成功/失败情况
    
    详细分析RSS源的爬虫爬取成功率和性能情况，支持按不同维度分组统计
    
    可选参数:
      - feed_id: 源ID，仅分析指定源的爬取结果
      - start_date: 开始日期，格式：YYYY-MM-DD
      - end_date: 结束日期，格式：YYYY-MM-DD
      - group_by: 分组方式，可选值：feed(按源分组)、date(按日期分组)、crawler(按爬虫分组)，默认按源分组
    
    返回数据:
      - total_batches: 总批次数
      - success_batches: 成功批次数
      - failed_batches: 失败批次数
      - overall_success_rate: 总体成功率(百分比)
      - avg_processing_time: 平均处理时间(秒)
      - group_by: 分组方式
      - items: 分组统计数据数组
    """
    try:
        # 获取参数
        feed_id = request.args.get("feed_id")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        group_by = request.args.get("group_by", "feed")
        
        # 创建会话和存储库
        db_session = get_db_session()
        crawler_repo = RssCrawlerRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 构建筛选条件
        filters = {}
        if feed_id:
            filters["feed_id"] = feed_id
        if start_date or end_date:
            filters["date_range"] = (start_date, end_date)
        
        # 获取分析数据
        analysis = crawler_repo.analyze_crawler_performance(filters, group_by)
        
        # 如果按源分组，补充源信息
        if group_by == "feed" and not feed_id:
            for item in analysis["items"]:
                if "feed_id" in item:
                    err, feed = feed_repo.get_feed_by_id(item["feed_id"])
                    if not err and feed:
                        item["feed_title"] = feed["title"]
                        item["feed_url"] = feed["url"]
        
        return success_response(analysis, "爬虫性能分析成功")
    except Exception as e:
        logger.error(f"分析爬虫性能失败: {str(e)}")
        return error_response(60001, f"分析爬虫性能失败: {str(e)}")

@crawler_bp.route("/error_analysis", methods=["GET"])
@auth_required
def analyze_crawler_errors():
    """分析爬虫错误
    
    详细分析RSS源爬取过程中的错误类型、错误阶段和失败原因
    
    可选参数:
      - feed_id: 源ID，仅分析指定源的错误
      - start_date: 开始日期，格式：YYYY-MM-DD
      - end_date: 结束日期，格式：YYYY-MM-DD
      - limit: 返回的错误类型数量，默认为10
    
    返回数据:
      - total_errors: 总错误数
      - error_types: 错误类型统计数组，包含错误类型、数量和百分比
      - error_stages: 错误阶段统计数组，包含错误阶段、数量和百分比
      - top_error_feeds: 错误次数最多的源统计数组
      - common_error_messages: 最常见的错误消息样本数组
    """
    try:
        # 获取参数
        feed_id = request.args.get("feed_id")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        limit = request.args.get("limit", 10, type=int)
        
        # 创建会话和存储库
        db_session = get_db_session()
        crawler_repo = RssCrawlerRepository(db_session)
        
        # 构建筛选条件
        filters = {}
        if feed_id:
            filters["feed_id"] = feed_id
        if start_date or end_date:
            filters["date_range"] = (start_date, end_date)
        
        # 获取错误分析
        error_analysis = crawler_repo.analyze_crawler_errors(filters, limit)
        
        return success_response(error_analysis, "爬虫错误分析成功")
    except Exception as e:
        logger.error(f"分析爬虫错误失败: {str(e)}")
        return error_response(60001, f"分析爬虫错误失败: {str(e)}")
    
@crawler_bp.route("/feed_failed_articles", methods=["GET"])
@auth_required
def get_feed_failed_articles():
    """获取指定订阅源的失败文章列表
    
    获取指定订阅源中抓取失败的文章列表，包括失败原因和重试次数
    
    URL参数:
      - feed_id: 订阅源ID(必填)
      - page: 页码，默认1
      - per_page: 每页数量，默认20
    
    返回数据:
      - 失败文章列表及分页信息
    """
    try:
        # 获取URL参数
        feed_id = request.args.get("feed_id")
        if not feed_id:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        crawler_repo = RssCrawlerRepository(db_session)
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        crawler_service = CrawlerService(article_repo, content_repo, crawler_repo, script_repo)
        
        # 获取失败文章列表
        failed_articles = crawler_service.get_feed_failed_articles(feed_id, page, per_page)
        
        return success_response(failed_articles, "获取失败文章列表成功")
    except Exception as e:
        logger.error(f"获取订阅源失败文章列表错误: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取失败文章列表失败: {str(e)}")

@crawler_bp.route("/article_errors", methods=["GET"])
@auth_required
def get_article_crawl_errors():
    """获取文章的爬取失败详情
    
    获取指定文章的所有爬取失败记录，包括详细的错误信息和爬取日志
    
    URL参数:
      - article_id: 文章ID(必填)
    
    返回数据:
      - 爬取失败记录列表，按时间倒序排列
    """
    try:
        # 获取URL参数
        article_id = request.args.get("article_id", type=int)
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        crawler_repo = RssCrawlerRepository(db_session)
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        crawler_service = CrawlerService(article_repo, content_repo, crawler_repo, script_repo)
        
        # 获取文章基本信息
        err, article = article_repo.get_article_by_id(article_id)
        if err:
            return error_response(PARAMETER_ERROR, f"获取文章信息失败: {err}")
        
        # 获取爬取失败详情
        crawl_errors = crawler_service.get_article_crawl_errors(article_id)
        
        # 构建响应数据
        response_data = {
            "article": {
                "id": article["id"],
                "title": article["title"],
                "link": article["link"],
                "feed_id": article["feed_id"],
                "feed_title": article["feed_title"],
                "status": article["status"],
                "retry_count": article["retry_count"],
                "max_retries": article["max_retries"],
                "error_message": article["error_message"]
            },
            "crawl_errors": crawl_errors
        }
        
        return success_response(response_data, "获取文章爬取失败详情成功")
    except Exception as e:
        logger.error(f"获取文章爬取失败详情错误: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取文章爬取失败详情失败: {str(e)}")