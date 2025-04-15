# app/api/client/v1/rss/article.py
"""客户端文章API接口"""
import logging
from flask import Blueprint, request, g, Response
from urllib.parse import unquote

from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss_feed_repository import RssFeedRepository
from app.infrastructure.database.repositories.user_repository import UserReadingHistoryRepository
from app.domains.rss.services.article_service import ArticleService
from app.api.middleware.client_auth import client_auth_required

from app.api.client.v1.rss import article_bp

logger = logging.getLogger(__name__)

@article_bp.route("/feed_articles", methods=["GET"])
@client_auth_required
def get_feed_articles():
    """获取指定Feed的文章列表
    
    查询参数:
    - feed_id: Feed ID
    - page: 页码，默认1
    - per_page: 每页数量，默认20
    
    Returns:
        文章列表和分页信息
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取Feed ID
        feed_id = request.args.get("feed_id")
        if not feed_id:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        # 获取分页参数
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        reading_history_repo = UserReadingHistoryRepository(db_session)
        
        # 获取文章列表
        filters = {
            "feed_id": feed_id,
            "status": 1  # 只显示已成功抓取的文章
        }
        
        result = article_repo.get_articles(page, per_page, filters)
        
        # 获取用户阅读记录，用于标记已读/收藏状态
        try:
            user_readings = {}
            article_ids = [article["id"] for article in result["list"]]
            
            if article_ids:
                readings = reading_history_repo.get_readings_by_articles(user_id, article_ids)
                for reading in readings:
                    user_readings[reading["article_id"]] = reading
            
            # 标记已读/收藏状态
            for article in result["list"]:
                article_id = article["id"]
                if article_id in user_readings:
                    article["is_read"] = user_readings[article_id]["is_read"]
                    article["is_favorite"] = user_readings[article_id]["is_favorite"]
                    article["read_progress"] = user_readings[article_id]["read_progress"]
                else:
                    article["is_read"] = False
                    article["is_favorite"] = False
                    article["read_progress"] = 0
        except Exception as e:
            logger.warning(f"获取阅读状态失败: {str(e)}")
            # 忽略错误，不影响文章列表返回
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取Feed文章列表失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取Feed文章列表失败: {str(e)}")

@article_bp.route("/detail", methods=["GET"])
@client_auth_required
def get_article_detail():
    """获取文章详情
    
    查询参数:
    - article_id: 文章ID
    
    Returns:
        文章详情和用户阅读状态
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取文章ID
        article_id = request.args.get("article_id", type=int)
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        reading_history_repo = UserReadingHistoryRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 获取文章详情
        article = article_service.get_article(article_id)
        
        # 获取用户阅读记录
        reading = reading_history_repo.get_reading(user_id, article_id)
        
        # 如果没有阅读记录，创建一个
        if not reading:
            reading_data = {
                "user_id": user_id,
                "article_id": article_id,
                "feed_id": article["feed_id"],
                "is_read": True,
                "read_position": 0,
                "read_progress": 0,
                "read_time": 0
            }
            reading = reading_history_repo.add_reading_record(reading_data)
        else:
            # 更新为已读
            reading_history_repo.update_reading(user_id, article_id, {"is_read": True})
        
        # 构建结果
        result = {
            "article": article,
            "reading": reading
        }
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取文章详情失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取文章详情失败: {str(e)}")

@article_bp.route("/update_reading", methods=["POST"])
@client_auth_required
def update_reading():
    """更新阅读记录
    
    请求体:
    {
        "article_id": 1,
        "read_position": 0,  // 可选
        "read_progress": 50,  // 可选，百分比
        "read_time": 120,  // 可选，阅读时间(秒)
        "is_read": true  // 可选
    }
    
    Returns:
        更新结果
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取请求参数
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        article_id = data.get("article_id")
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        # 提取更新数据
        update_data = {}
        for key in ["read_position", "read_progress", "read_time", "is_read"]:
            if key in data:
                update_data[key] = data[key]
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        reading_history_repo = UserReadingHistoryRepository(db_session)
        
        # 获取文章信息
        err, article = article_repo.get_article_by_id(article_id)
        if err:
            return error_response(PARAMETER_ERROR, err)
        
        # 更新或创建阅读记录
        reading = reading_history_repo.get_reading(user_id, article_id)
        
        if reading:
            reading = reading_history_repo.update_reading(user_id, article_id, update_data)
        else:
            reading_data = {
                "user_id": user_id,
                "article_id": article_id,
                "feed_id": article["feed_id"],
                **update_data
            }
            reading = reading_history_repo.add_reading_record(reading_data)
        
        return success_response(reading)
    except Exception as e:
        logger.error(f"更新阅读记录失败: {str(e)}")
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
        切换结果
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取请求参数
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        article_id = data.get("article_id")
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        reading_history_repo = UserReadingHistoryRepository(db_session)
        
        # 切换收藏状态
        success, is_favorite = reading_history_repo.toggle_favorite(user_id, article_id)
        
        if not success:
            return error_response(PARAMETER_ERROR, "切换收藏状态失败")
        
        return success_response({
            "article_id": article_id,
            "is_favorite": is_favorite
        }, "收藏状态更新成功")
    except Exception as e:
        logger.error(f"切换收藏状态失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"切换收藏状态失败: {str(e)}")

@article_bp.route("/mark_read", methods=["POST"])
@client_auth_required
def mark_article_read():
    """标记文章为已读
    
    请求体:
    {
        "article_id": 1,
        "is_read": true  // 默认为true，设置为false可标记为未读
    }
    
    Returns:
        标记结果
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取请求参数
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        article_id = data.get("article_id")
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        is_read = data.get("is_read", True)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        reading_history_repo = UserReadingHistoryRepository(db_session)
        
        # 获取文章信息
        err, article = article_repo.get_article_by_id(article_id)
        if err:
            return error_response(PARAMETER_ERROR, err)
        
        # 更新或创建阅读记录
        reading = reading_history_repo.get_reading(user_id, article_id)
        
        if reading:
            reading = reading_history_repo.update_reading(user_id, article_id, {"is_read": is_read})
        else:
            reading_data = {
                "user_id": user_id,
                "article_id": article_id,
                "feed_id": article["feed_id"],
                "is_read": is_read
            }
            reading = reading_history_repo.add_reading_record(reading_data)
        
        return success_response({
            "article_id": article_id,
            "is_read": is_read
        }, "已读状态更新成功")
    except Exception as e:
        logger.error(f"标记文章已读失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"标记文章已读失败: {str(e)}")

@article_bp.route("/mark_all_read", methods=["POST"])
@client_auth_required
def mark_all_read():
    """标记全部已读
    
    请求体:
    {
        "feed_id": "Feed ID"  // 可选，不提供则标记所有文章已读
    }
    
    Returns:
        标记结果
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取请求参数
        data = request.get_json() or {}
        feed_id = data.get("feed_id")
        
        # 创建会话和存储库
        db_session = get_db_session()
        reading_history_repo = UserReadingHistoryRepository(db_session)
        
        # 标记全部已读
        count = reading_history_repo.mark_all_read(user_id, feed_id)
        
        return success_response({
            "count": count,
            "feed_id": feed_id
        }, "已标记全部已读")
    except Exception as e:
        logger.error(f"标记全部已读失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"标记全部已读失败: {str(e)}")

@article_bp.route("/proxy-image", methods=["GET"])
@client_auth_required
def proxy_image():
    """代理获取图片
    
    查询参数:
    - url: 图片URL(需URL编码)
    
    Returns:
        图片内容
    """
    try:
        # 获取并解码图片URL
        image_url = unquote(request.args.get("url", ""))
        if not image_url:
            return "未提供URL", 400
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 获取图片
        image_content, mime_type, error = article_service.proxy_image(image_url)
        if error:
            return f"获取图片失败: {error}", 404
        
        # 返回图片内容
        return Response(
            image_content,
            mimetype=mime_type,
            headers={
                "Cache-Control": "public, max-age=31536000",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except Exception as e:
        logger.error(f"代理获取图片失败: {str(e)}")
        return str(e), 404

@article_bp.route("/unread_count", methods=["GET"])
@client_auth_required
def get_unread_count():
    """获取未读文章数量
    
    查询参数:
    - feed_id: Feed ID(可选)
    
    Returns:
        未读数量
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取Feed ID
        feed_id = request.args.get("feed_id")
        
        # 创建会话和存储库
        db_session = get_db_session()
        reading_history_repo = UserReadingHistoryRepository(db_session)
        
        # 获取未读数量
        unread_count = reading_history_repo.get_unread_count(user_id, feed_id)
        
        return success_response({
            "unread_count": unread_count,
            "feed_id": feed_id
        })
    except Exception as e:
        logger.error(f"获取未读数量失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取未读数量失败: {str(e)}")