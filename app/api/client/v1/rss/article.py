# app/api/client/v1/rss/article.py
"""客户端文章API接口 (GET/POST only, No groups)"""
import logging
from flask import Blueprint, request, g, Response
from urllib.parse import unquote
from datetime import datetime

from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, NOT_FOUND
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss.rss_feed_repository import RssFeedRepository
from app.infrastructure.database.repositories.user_repository import UserReadingHistoryRepository, UserSubscriptionRepository
from app.domains.rss.services.article_service import ArticleService
from app.api.middleware.client_auth import client_auth_required

# Optional: Import vectorization service if similar articles feature is desired
try:
    from app.domains.rss.services.vectorization_service import ArticleVectorizationService
    from app.infrastructure.database.repositories.rss.rss_vectorization_repository import RssFeedArticleVectorizationTaskRepository
    VECTORIZATION_ENABLED = True
except ImportError:
    VECTORIZATION_ENABLED = False
    ArticleVectorizationService = None
    RssFeedArticleVectorizationTaskRepository = None

# Assuming article_bp is defined in app/api/client/v1/rss/__init__.py
article_bp = Blueprint("client_article", __name__) # Removed url_prefix


logger = logging.getLogger(__name__)


@article_bp.route("/list", methods=["GET"])
@client_auth_required
def get_articles():
    """获取用户订阅的所有Feed的文章列表，支持过滤和分页
    
    查询参数:
    - page: 页码，默认1
    - per_page: 每页数量，默认20
    - feed_id: 可选，按特定Feed过滤
    - search: 可选，按标题或摘要搜索关键词
    
    Returns:
        文章列表和分页信息
    """
    try:
        user_id = g.user_id
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        feed_id = request.args.get("feed_id")

        search_query = request.args.get("search")

        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        subscription_repo = UserSubscriptionRepository(db_session)

        # Get user's subscribed feed IDs
        subscribed_feed_ids = [sub["feed_id"] for sub in subscription_repo.get_user_subscriptions(user_id)]

        if not subscribed_feed_ids and not feed_id:
             return success_response({"list": [], "total": 0, "page": page, "per_page": per_page, "pages": 0})

        filters = {"status": 1}

        if feed_id:
                # 移除订阅检查，直接添加 feed_id 过滤
                filters["feed_id"] = feed_id
        else:
                # 只有当没有指定 feed_id 时，才限制为已订阅的 feeds
                filters["feed_ids"] = subscribed_feed_ids

        if search_query:
            filters["search_query"] = search_query

        result = article_repo.get_articles(page, per_page, filters)
        

        return success_response(result)
    except Exception as e:
        logger.error(f"获取文章列表失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取文章列表失败: {str(e)}")


@article_bp.route("/detail", methods=["GET"])
@client_auth_required
def get_article_detail():
    """获取文章详情
    
    查询参数:
    - article_id: 文章ID (Required)
    - include_similar: 可选, 'true' to try fetching similar articles. Default is false.
    
    Returns:
        文章详情, 用户阅读状态, 和可选的相似文章列表
    """
    try:
        user_id = g.user_id
        article_id = request.args.get("article_id", type=int)
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少 article_id 查询参数")
            
        include_similar = request.args.get("include_similar", "false").lower() == 'true'

        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session) # Needed for ArticleService
        reading_history_repo = UserReadingHistoryRepository(db_session)
        
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # Get article detail using service (includes content)
        article = article_service.get_article(article_id) # Raises exception if article not found
        
        # Get reading history (don't mark as read here, use separate endpoint)
        reading_obj = reading_history_repo.get_reading(user_id, article_id)
        
        # If no reading history, create a default one (is_read=False)
        if not reading_obj:
              reading_data = {
                    "user_id": user_id,
                    "article_id": article_id,
                    "feed_id": article["feed_id"],
                    "is_read": False,
                    "is_favorite": False,
               }
              reading_obj = reading_history_repo.add_reading_record(reading_data)
        
        # Convert reading object to dictionary
        reading = reading_history_repo.reading_history_to_dict(reading_obj) if reading_obj else None

        similar_articles = []
        if include_similar and VECTORIZATION_ENABLED and article.get("is_vectorized"):
            try:
                 # Ensure necessary repos are available
                 if not all([RssFeedArticleVectorizationTaskRepository, content_repo]):
                     raise ImportError("Vectorization dependencies missing for similar articles")
                 
                 vectorization_service = ArticleVectorizationService(
                     article_repo=article_repo,
                     content_repo=content_repo,
                     task_repo=RssFeedArticleVectorizationTaskRepository(db_session)
                 )
                 similar_articles = vectorization_service.get_similar_articles(article_id, limit=5)
                

            except Exception as sim_err:
                 logger.warning(f"获取相似文章失败 (Article: {article_id}): {str(sim_err)}")


        result = {
            "article": article,
            "reading": reading,
            "similar_articles": similar_articles
        }
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取文章详情失败 (ID: {article_id}): {str(e)}", exc_info=True)
        return error_response(NOT_FOUND if "获取文章失败" in str(e) else PARAMETER_ERROR, f"获取文章详情失败: {str(e)}")


   
@article_bp.route("/proxy_image", methods=["GET"])
@client_auth_required
def proxy_image():
    """代理获取图片 (需要认证)
    
    查询参数:
    - url: 图片URL(需URL编码)
    
    Returns:
        图片内容
    """
    try:
        image_url = unquote(request.args.get("url", ""))
        if not image_url:
            return "未提供URL", 400
        
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        image_content, mime_type, error = article_service.proxy_image(image_url)
        if error:
            status_code = 404 if "获取图片失败" in error else 500
            return f"代理获取图片失败: {error}", status_code
        
        return Response(
            image_content,
            mimetype=mime_type,
            headers={
                "Cache-Control": "public, max-age=31536000",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except Exception as e:
        logger.error(f"代理获取图片失败: {str(e)}", exc_info=True)
        return "代理获取图片时发生内部错误", 500

