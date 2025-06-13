# app/api/client/v1/rss/article.py
"""客户端文章API接口 (GET/POST only, No groups)"""
from collections import defaultdict
import logging
from flask import Blueprint, request, g, Response
from urllib.parse import unquote
from datetime import date, datetime, timedelta

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



@article_bp.route("/list/by_date", methods=["GET"])
@client_auth_required
def get_articles_by_date():
    """获取用户订阅的文章列表，按日期聚合显示
    
    查询参数:
    - date_from: 开始日期，默认7天前 (YYYY-MM-DD)
    - date_to: 结束日期，默认今天 (YYYY-MM-DD)
    - feed_id: 可选，按特定Feed过滤
    - search: 可选，按标题或摘要搜索关键词
    - timezone: 时区偏移，默认+8 (东八区)
    
    Returns:
        按日期聚合的文章列表
        {
            "data": {
                "2024-01-15": [
                    {
                        "id": 1,
                        "title": "文章标题",
                        "summary": "文章摘要",
                        "url": "文章链接",
                        "feed_name": "来源Feed名称",
                        "feed_id": 1,
                        "published_at": "2024-01-15T10:30:00",
                        "read_status": false
                    }
                ],
                "2024-01-14": [...],
                ...
            },
            "date_range": {
                "from": "2024-01-08",
                "to": "2024-01-15"
            },
            "total_articles": 125,
            "total_dates": 8
        }
    """
    try:
        user_id = g.user_id
        
        # 解析日期参数
        date_from_str = request.args.get("date_from")
        date_to_str = request.args.get("date_to") 
        timezone_offset = request.args.get("timezone", 8, type=int)  # 默认东八区
        
        # 设置默认日期范围（最近7天）
        if not date_to_str:
            date_to = date.today()
        else:
            try:
                date_to = date.fromisoformat(date_to_str)
            except ValueError:
                return error_response(PARAMETER_ERROR, "无效的结束日期格式，应为YYYY-MM-DD")
        
        if not date_from_str:
            date_from = date_to - timedelta(days=6)  # 7天范围
        else:
            try:
                date_from = date.fromisoformat(date_from_str)
            except ValueError:
                return error_response(PARAMETER_ERROR, "无效的开始日期格式，应为YYYY-MM-DD")
        
        # 验证日期范围
        if date_from > date_to:
            return error_response(PARAMETER_ERROR, "开始日期不能晚于结束日期")
        
        # 其他过滤参数
        feed_id = request.args.get("feed_id")
        search_query = request.args.get("search")

        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        subscription_repo = UserSubscriptionRepository(db_session)
        reading_history_repo = UserReadingHistoryRepository(db_session)
        feed_repo = RssFeedRepository(db_session)

        # 获取用户订阅的Feed列表
        subscriptions = subscription_repo.get_user_subscriptions(user_id)
        if not subscriptions:
            return success_response({
                "data": {},
                "date_range": {
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat()
                },
                "total_articles": 0,
                "total_dates": 0
            })

        subscribed_feed_ids = [sub["feed_id"] for sub in subscriptions]
        
        # 如果指定了特定Feed，检查用户是否订阅
        if feed_id:
            if int(feed_id) not in subscribed_feed_ids:
                return error_response(NOT_FOUND, "未找到该Feed或未订阅")
            subscribed_feed_ids = [int(feed_id)]

        # 获取文章列表（按日期范围）
        articles = article_repo.get_articles_by_date_range(
            feed_ids=subscribed_feed_ids,
            date_from=date_from,
            date_to=date_to,
            search_query=search_query,
            timezone_offset=timezone_offset
        )

        # 获取用户已读文章ID列表
        read_articles = set()
        if articles:
            read_article_ids = reading_history_repo.get_article_ids_by_status({
                "user_id": user_id,
                "is_read": True
            })
            read_articles = set(read_article_ids)

        # 获取Feed信息（使用现有方法）
        feed_info_map = {}
        if articles:
            unique_feed_ids = list(set(article["feed_id"] for article in articles))
            for feed_id in unique_feed_ids:
                err, feed = feed_repo.get_feed_by_id(feed_id)
                if not err and feed:
                    feed_info_map[feed_id] = feed

        # 按日期聚合文章
        articles_by_date = defaultdict(list)
        
        for article in articles:
            # 根据时区调整发布日期
            published_at = article["published_at"]
            if isinstance(published_at, str):
                published_at = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            
            # 调整时区后的日期作为分组key
            local_date = (published_at + timedelta(hours=timezone_offset)).date()
            date_key = local_date.isoformat()
            
            # 构建文章信息
            feed_info = feed_info_map.get(article["feed_id"], {})
            article_data = {
                "id": article["id"],
                "title": article["title"],
                "summary": article.get("summary", ""),
                "url": article["url"],
                "feed_name": feed_info.get("title", "未知来源"),
                "feed_id": article["feed_id"],
                "published_at": published_at.isoformat(),
                "read_status": article["id"] in read_articles
            }
            
            articles_by_date[date_key].append(article_data)

        # 对每个日期的文章按发布时间排序（最新的在前）
        for date_key in articles_by_date:
            articles_by_date[date_key].sort(
                key=lambda x: x["published_at"], 
                reverse=True
            )

        # 转换为普通字典并按日期倒序排列
        result_data = dict(sorted(articles_by_date.items(), reverse=True))
        
        return success_response({
            "data": result_data,
            "date_range": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat()
            },
            "total_articles": len(articles),
            "total_dates": len(result_data)
        })

    except Exception as e:
        logger.error(f"获取按日期聚合的文章列表失败: {str(e)}", exc_info=True)
        return error_response(500, f"获取文章列表失败: {str(e)}")



    
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

