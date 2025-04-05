# app/api/v1/rss/article.py
"""RSS文章API控制器"""
import logging
from flask import Blueprint, request, Response
from urllib.parse import unquote

from app.api.middleware.auth import auth_required
from app.core.responses import success_response
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss_feed_repository import RssFeedRepository
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss_article_content_repository import RssFeedArticleContentRepository
from app.domains.rss.services.article_service import ArticleService

logger = logging.getLogger(__name__)

# 创建蓝图
article_bp = Blueprint("article", __name__)

@article_bp.route("/list", methods=["GET"])
@auth_required
def get_articles():
    """获取文章列表
    
    查询参数:
    - page: 页码，默认1
    - per_page: 每页数量，默认10
    - id: 文章ID
    - feed_id: Feed ID
    - status: 状态
    - title: 标题关键词
    - start_date: 开始日期
    - end_date: 结束日期
    - is_locked: 是否被锁定(1=是, 0=否)
    - min_retries: 最小重试次数
    - max_retries: 最大重试次数
    
    Returns:
        文章列表和分页信息
    """
    try:
        # 获取分页参数
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        
        # 构建筛选条件
        filters = {}
        
        # 文章ID筛选
        article_id = request.args.get("id", type=int)
        if article_id is not None:
            filters["id"] = article_id
        
        # Feed ID筛选
        feed_id = request.args.get("feed_id", type=str)
        if feed_id:
            filters["feed_id"] = feed_id
        
        # 状态筛选
        status = request.args.get("status", type=int)
        if status is not None:
            filters["status"] = status
        
        # 标题搜索
        title = request.args.get("title", type=str)
        if title:
            filters["title"] = title
        
        # 发布日期范围
        start_date = request.args.get("start_date", type=str)
        end_date = request.args.get("end_date", type=str)
        if start_date or end_date:
            filters["date_range"] = (start_date, end_date)
        
        # 锁定状态筛选
        is_locked = request.args.get("is_locked", type=int)
        if is_locked is not None:
            filters["is_locked"] = bool(is_locked)
        
        # 重试次数筛选
        min_retries = request.args.get("min_retries", type=int)
        max_retries = request.args.get("max_retries", type=int)
        if min_retries is not None or max_retries is not None:
            filters["retry_range"] = (min_retries, max_retries)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 获取文章
        result = article_service.get_articles(page=page, per_page=per_page, filters=filters)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取文章列表失败: {str(e)}")
        return success_response(None, f"获取文章列表失败: {str(e)}", 60001)

@article_bp.route("/detail", methods=["GET"])
@auth_required
def get_article_detail():
    """获取文章详情
    
    查询参数:
    - article_id: 文章ID
    
    Returns:
        文章详情
    """
    try:
        # 获取文章ID
        article_id = request.args.get("article_id")
        if not article_id:
            return success_response(None, "缺少article_id参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 获取文章详情
        article = article_service.get_article(int(article_id))
        
        return success_response(article)
    except Exception as e:
        logger.error(f"获取文章详情失败: {str(e)}")
        return success_response(None, f"获取文章详情失败: {str(e)}", 60001)

@article_bp.route("/sync", methods=["POST"])
@auth_required
def sync_feed_articles():
    """同步Feed文章
    
    请求体:
    {
        "feed_id": "Feed ID"
    }
    
    Returns:
        同步结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        feed_id = data.get("feed_id")
        
        if not feed_id:
            return success_response(None, "缺少feed_id参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 同步文章
        result = article_service.sync_feed_articles(feed_id)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"同步Feed文章失败: {str(e)}")
        return success_response(None, f"同步Feed文章失败: {str(e)}", 60001)

@article_bp.route("/batch_sync", methods=["POST"])
@auth_required
def batch_sync_articles():
    """批量同步多个Feed的文章
    
    请求体:
    {
        "feed_ids": ["Feed ID 1", "Feed ID 2", ...]
    }
    
    Returns:
        同步结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        feed_ids = data.get("feed_ids", [])
        
        if not feed_ids:
            return success_response(None, "缺少feed_ids参数或为空", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 批量同步文章
        result = article_service.batch_sync_articles(feed_ids)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"批量同步Feed文章失败: {str(e)}")
        return success_response(None, f"批量同步Feed文章失败: {str(e)}", 60001)

@article_bp.route("/reset", methods=["POST"])
@auth_required
def reset_failed_article():
    """重置失败的文章，允许重新抓取
    
    请求体:
    {
        "article_id": 1
    }
    
    Returns:
        操作结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return success_response(None, "未提供数据", 60001)
        
        article_id = data.get("article_id")
        if not article_id:
            return success_response(None, "缺少article_id参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 重置文章状态
        result = article_service.reset_article(int(article_id))
        
        return success_response(result, "重置文章成功")
    except Exception as e:
        logger.error(f"重置文章失败: {str(e)}")
        return success_response(None, f"重置文章失败: {str(e)}", 60001)

@article_bp.route("/proxy-image", methods=["GET"])
def proxy_image():
    """代理获取图片
    
    查询参数:
    - url: 图片URL(URL编码)
    
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

@article_bp.route("/get_content_from_url", methods=["GET"])
@auth_required
def get_content_from_url():
    """从URL获取文章内容
    
    查询参数:
    - url: 文章URL
    
    Returns:
        文章内容
    """
    try:
        # 获取URL
        url = request.args.get("url")
        if not url:
            return success_response(None, "URL参数是必须的", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 获取内容
        content, error = article_service.get_content_from_url(url)
        if error:
            return success_response(None, error, 60001)
        
        return success_response(content)
    except Exception as e:
        logger.error(f"从URL获取文章内容失败: {str(e)}")
        return success_response(None, f"获取文章内容失败: {str(e)}", 60001)