# app/api/jobs/crawler.py
"""爬虫任务API接口"""
import logging
import socket
import uuid
from app.infrastructure.database.repositories.rss_feed_repository import RssFeedRepository
from flask import Blueprint, request, current_app
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session

# 仓库导入
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss_crawler_repository import RssCrawlerRepository
from app.infrastructure.database.repositories.rss_script_repository import RssFeedCrawlScriptRepository

# 服务导入
from app.domains.rss.services.crawler_service import CrawlerService

logger = logging.getLogger(__name__)

# 创建爬虫任务蓝图
crawler_jobs_bp = Blueprint("crawler_jobs", __name__)
@crawler_jobs_bp.route("/pending_articles", methods=["GET"])
@app_key_required
def pending_articles():
    """获取待抓取的文章列表"""
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
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        crawler_service = CrawlerService(article_repo, content_repo, crawler_repo, script_repo, feed_repo)
        
        # 获取待抓取文章
        articles = crawler_service.get_pending_articles(limit, crawler_id)
        
        return success_response(articles)
    except Exception as e:
        logger.error(f"获取待抓取文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取待抓取文章失败: {str(e)}")

@crawler_jobs_bp.route("/claim_article", methods=["POST"])
@app_key_required
def claim_article():
    """认领(锁定)文章进行抓取"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "article_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        article_id = data["article_id"]
        
        # 获取爬虫标识
        crawler_id = request.headers.get("X-Crawler-ID") or socket.gethostname()
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        crawler_repo = RssCrawlerRepository(db_session)
        script_repo = RssFeedCrawlScriptRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        crawler_service = CrawlerService(article_repo, content_repo, crawler_repo, script_repo, feed_repo)
        
        # 认领文章
        result = crawler_service.claim_article(article_id, crawler_id)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"认领文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"认领文章失败: {str(e)}")

@crawler_jobs_bp.route("/submit_result", methods=["POST"])
@app_key_required
def submit_crawl_result():
    """提交抓取结果"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "article_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
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
        return error_response(PARAMETER_ERROR, f"提交抓取结果失败: {str(e)}")

