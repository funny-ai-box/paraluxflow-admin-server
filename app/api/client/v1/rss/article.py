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

def _add_reading_status_to_articles(user_id: str, articles: list, reading_history_repo: UserReadingHistoryRepository):
    """Helper function to add is_read and is_favorite status to a list of articles."""
    if not articles:
        return articles
        
    # 获取文章ID列表
    article_ids = [article["id"] for article in articles]
    
    try:
        # 为每篇文章单独获取阅读状态
        # 替代不存在的 get_readings_by_articles 方法
        user_readings_map = {}
        for article_id in article_ids:
            reading = reading_history_repo.get_reading(user_id, article_id)
            if reading:
                # 将读取对象转为字典
                reading_dict = reading_history_repo.reading_history_to_dict(reading)
                user_readings_map[article_id] = reading_dict
        
        # 将阅读状态添加到文章对象中
        for article in articles:
            reading_info = user_readings_map.get(article["id"])
            if reading_info:
                article["is_read"] = reading_info.get("is_read", False)
                article["is_favorite"] = reading_info.get("is_favorite", False)
                article["read_progress"] = reading_info.get("read_progress", 0)
            else:
                article["is_read"] = False
                article["is_favorite"] = False
                article["read_progress"] = 0
                
    except Exception as e:
        logger.warning(f"获取文章阅读状态失败 (User: {user_id}): {str(e)}")
        # 确保即使出错也给每篇文章设置默认值
        for article in articles:
            article["is_read"] = False
            article["is_favorite"] = False
            article["read_progress"] = 0
            
    return articles
@article_bp.route("/list", methods=["GET"])
@client_auth_required
def get_articles():
    """获取用户订阅的所有Feed的文章列表，支持过滤和分页
    
    查询参数:
    - page: 页码，默认1
    - per_page: 每页数量，默认20
    - feed_id: 可选，按特定Feed过滤
    - read_status: 可选，'read', 'unread'
    - favorite_status: 可选, 'true', 'false'
    - search: 可选，按标题或摘要搜索关键词
    
    Returns:
        文章列表和分页信息
    """
    try:
        user_id = g.user_id
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        feed_id = request.args.get("feed_id")
        read_status = request.args.get("read_status") # 'read' or 'unread'
        favorite_status = request.args.get("favorite_status") # 'true' or 'false'
        search_query = request.args.get("search")

        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        reading_history_repo = UserReadingHistoryRepository(db_session)
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

        required_article_ids = None
        if read_status or favorite_status:
             reading_filters = {"user_id": user_id}
             if read_status == 'read':
                 reading_filters["is_read"] = True
             elif read_status == 'unread':
                 reading_filters["is_read"] = False # Needs repo logic

             if favorite_status == 'true':
                 reading_filters["is_favorite"] = True
             elif favorite_status == 'false':
                 pass # Needs repo logic for 'not favorite'

             required_article_ids = reading_history_repo.get_article_ids_by_status(reading_filters)
             
             if not required_article_ids:
                  return success_response({"list": [], "total": 0, "page": page, "per_page": per_page, "pages": 0})
             
             # Combine with existing article_ids filter if needed (e.g., search results)
             if "article_ids" in filters:
                  filters["article_ids"] = list(set(filters["article_ids"]) & set(required_article_ids))
                  if not filters["article_ids"]: # Intersection is empty
                       return success_response({"list": [], "total": 0, "page": page, "per_page": per_page, "pages": 0})
             else:
                  filters["article_ids"] = required_article_ids


        result = article_repo.get_articles(page, per_page, filters)
        
        result["list"] = _add_reading_status_to_articles(user_id, result["list"], reading_history_repo)

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
                 similar_articles_raw = vectorization_service.get_similar_articles(article_id, limit=5)
                 similar_articles = _add_reading_status_to_articles(user_id, similar_articles_raw, reading_history_repo)

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


@article_bp.route("/update_reading", methods=["POST"])
@client_auth_required
def update_reading_history():
    """更新阅读记录 (进度, 时间等), 不改变 is_read 状态
    
    请求体:
    {
        "article_id": 1,
        "read_position": 100,  // 可选, e.g., scroll position
        "read_progress": 50,   // 可选, 百分比 0-100
        "read_time_delta": 30  // 可选, 本次阅读增加的时间(秒)
    }
    
    Returns:
        更新后的阅读记录
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        article_id = data.get("article_id")
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        db_session = get_db_session()
        reading_history_repo = UserReadingHistoryRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session) # Needed to get feed_id if creating

        update_data = {}
        if "read_position" in data:
            update_data["read_position"] = data["read_position"]
        if "read_progress" in data:
            update_data["read_progress"] = data["read_progress"]
            # Note: We no longer automatically mark as read here based on progress=100
            # Use the dedicated /article/mark_read endpoint for that.
        
        read_time_delta = data.get("read_time_delta")

        reading = reading_history_repo.get_reading(user_id, article_id)
        
        if reading:
            if read_time_delta is not None:
                 # 修复: 直接访问模型的属性而不是使用.get()方法
                 current_read_time = reading.read_time or 0
                 update_data["read_time"] = current_read_time + read_time_delta
            # Only update if there's data to update
            if update_data:
                 reading = reading_history_repo.update_reading(user_id, article_id, update_data)
            # If no update_data but record exists, return current record
            elif not update_data:
                 pass # Return existing reading object below
            
        else:
            # Create a new record if it doesn't exist
            err, article = article_repo.get_article_by_id(article_id)
            if err:
                 return error_response(NOT_FOUND, "无法找到关联的文章以创建阅读记录")

            reading_data = {
                "user_id": user_id,
                "article_id": article_id,
                "feed_id": article["feed_id"],
                "is_read": False, # Default is_read to false
                "is_favorite": False,
                "read_position": update_data.get("read_position", 0),
                "read_progress": update_data.get("read_progress", 0),
                "read_time": read_time_delta or 0
            }
            reading = reading_history_repo.add_reading_record(reading_data)
            
        if not reading: # Handle case where add/update failed
            return error_response(PARAMETER_ERROR, "更新或创建阅读记录失败")
            
        # 修复: 将SQLAlchemy model对象转换为字典再返回
        reading_dict = reading_history_repo.reading_history_to_dict(reading)
        return success_response(reading_dict)
    except Exception as e:
        logger.error(f"更新阅读记录失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"更新阅读记录失败: {str(e)}")

@article_bp.route("/toggle_favorite", methods=["POST"])
@client_auth_required
def toggle_favorite():
    """切换文章收藏状态
    
    请求体:
    {
        "article_id": 1
    }
    
    Returns:
        { "article_id": 1, "is_favorite": true/false }
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        article_id = data.get("article_id")
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        db_session = get_db_session()
        reading_history_repo = UserReadingHistoryRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)

        # Assume toggle_favorite handles creation if needed and returns (success, new_status)
        success, is_favorite = reading_history_repo.toggle_favorite(user_id, article_id)
        
        if not success:
            err, _ = article_repo.get_article_by_id(article_id)
            if err:
                 return error_response(NOT_FOUND, "无法找到要收藏的文章")
            else:
                 return error_response(PARAMETER_ERROR, "更新收藏状态失败")
        
        return success_response({
            "article_id": article_id,
            "is_favorite": is_favorite
        }, "收藏状态更新成功")
    except Exception as e:
        logger.error(f"切换收藏状态失败 (Article: {article_id}): {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"切换收藏状态失败: {str(e)}")

@article_bp.route("/favorites", methods=["GET"])
@client_auth_required
def get_favorite_articles():
    """获取用户收藏的文章列表
    
    查询参数:
    - page: 页码，默认1
    - per_page: 每页数量，默认20
    
    Returns:
        收藏的文章列表和分页信息
    """
    try:
        user_id = g.user_id
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        reading_history_repo = UserReadingHistoryRepository(db_session)

        favorite_article_ids = reading_history_repo.get_article_ids_by_status({
            "user_id": user_id,
            "is_favorite": True
        })

        if not favorite_article_ids:
             return success_response({"list": [], "total": 0, "page": page, "per_page": per_page, "pages": 0})

        filters = {
            "article_ids": favorite_article_ids,
            "status": 1
        }
        
        result = article_repo.get_articles(page, per_page, filters)
        
        result["list"] = _add_reading_status_to_articles(user_id, result["list"], reading_history_repo)

        return success_response(result)
    except Exception as e:
        logger.error(f"获取收藏文章列表失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取收藏文章列表失败: {str(e)}")


@article_bp.route("/mark_read", methods=["POST"])
@client_auth_required
def mark_article_read_status():
    """标记文章为已读或未读
    
    请求体:
    {
        "article_id": 1,
        "is_read": true  // true to mark as read, false to mark as unread
    }
    
    Returns:
        { "article_id": 1, "is_read": true/false }
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        article_id = data.get("article_id")
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
            
        is_read = data.get("is_read")
        if is_read is None or not isinstance(is_read, bool):
             return error_response(PARAMETER_ERROR, "缺少或无效的is_read参数 (应为 true 或 false)")

        db_session = get_db_session()
        reading_history_repo = UserReadingHistoryRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)

        reading = reading_history_repo.get_reading(user_id, article_id)
        update_data = {"is_read": is_read}
        if is_read:
            update_data["last_read_at"] = datetime.now()
            update_data["read_progress"] = 100

        if reading:
            reading = reading_history_repo.update_reading(user_id, article_id, update_data)
        else:
            err, article = article_repo.get_article_by_id(article_id)
            if err:
                 return error_response(NOT_FOUND, "无法找到要标记的文章")

            reading_data = {
                "user_id": user_id,
                "article_id": article_id,
                "feed_id": article["feed_id"],
                "is_read": is_read,
                "is_favorite": False,
                "last_read_at": update_data.get("last_read_at"),
                "read_progress": update_data.get("read_progress", 0)
            }
            reading = reading_history_repo.add_reading_record(reading_data)
        
        if not reading:
             return error_response(PARAMETER_ERROR, "更新已读状态失败")

        return success_response({
            "article_id": article_id,
            "is_read": is_read
        }, "已读状态更新成功")
    except Exception as e:
        logger.error(f"标记文章已读状态失败 (Article: {article_id}): {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"标记文章已读状态失败: {str(e)}")


@article_bp.route("/mark_all_read", methods=["POST"])
@client_auth_required
def mark_all_read():
    """标记指定Feed或所有订阅Feed的文章为已读
    
    请求体:
    {
        "feed_id": "Feed ID"  // 可选，不提供则标记所有订阅的文章已读
        "before_date": "YYYY-MM-DDTHH:MM:SS" // 可选, 只标记此日期之前的文章
    }
    
    Returns:
        { "count": number_of_articles_marked_read }
    """
    try:
        user_id = g.user_id
        data = request.get_json() or {}
        feed_id = data.get("feed_id")
        before_date_str = data.get("before_date")
        
        before_date = None
        if before_date_str:
            try:
                 before_date = datetime.fromisoformat(before_date_str)
            except ValueError:
                 return error_response(PARAMETER_ERROR, "无效的 before_date 格式, 请使用 ISO 格式")

        db_session = get_db_session()
        reading_history_repo = UserReadingHistoryRepository(db_session)
        subscription_repo = UserSubscriptionRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)

        target_feed_ids = []
        if feed_id:
            if subscription_repo.get_subscription(user_id, feed_id):
                 target_feed_ids = [feed_id]
            else:
                 return error_response(PARAMETER_ERROR, "未订阅指定的Feed")
        else:
            target_feed_ids = [sub["feed_id"] for sub in subscription_repo.get_user_subscriptions(user_id)]

        if not target_feed_ids:
             return success_response({"count": 0}, "没有需要标记的订阅Feed")

        article_filters = {
            "feed_ids": target_feed_ids,
            "status": 1
        }
        if before_date:
            article_filters["published_before"] = before_date

        article_ids_to_mark = article_repo.get_all_article_ids(article_filters)

        if not article_ids_to_mark:
             return success_response({"count": 0}, "没有找到需要标记的文章")

        count = reading_history_repo.mark_list_read(user_id, article_ids_to_mark)
        
        return success_response({
            "count": count,
            "feed_id": feed_id
        }, f"成功标记 {count} 篇文章为已读")
    except Exception as e:
        logger.error(f"标记全部已读失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"标记全部已读失败: {str(e)}")

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

@article_bp.route("/unread_count", methods=["GET"])
@client_auth_required
def get_unread_count():
    """获取未读文章数量
    
    查询参数:
    - feed_id: Feed ID(可选, 不提供则返回所有订阅的未读总数)
    
    Returns:
        { "unread_count": number, "feed_id": feed_id | null }
    """
    try:
        user_id = g.user_id
        feed_id = request.args.get("feed_id")

        db_session = get_db_session()
        reading_history_repo = UserReadingHistoryRepository(db_session)
        subscription_repo = UserSubscriptionRepository(db_session)

        target_feed_ids = None
        if feed_id:
             if not subscription_repo.get_subscription(user_id, feed_id):
                  return error_response(PARAMETER_ERROR, "未订阅指定的Feed")
             target_feed_ids = [feed_id]
        # If feed_id is None, target_feed_ids remains None, repo handles 'all subscribed'

        unread_count = reading_history_repo.get_unread_count(user_id, feed_ids=target_feed_ids)
        
        return success_response({
            "unread_count": unread_count,
            "feed_id": feed_id
        })
    except Exception as e:
        logger.error(f"获取未读数量失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取未读数量失败: {str(e)}")