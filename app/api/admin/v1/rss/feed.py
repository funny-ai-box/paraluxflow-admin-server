# app/api/v1/rss/feed.py
"""RSS Feed API控制器"""
import os
import logging
from flask import Blueprint, request, g, current_app
from werkzeug.utils import secure_filename

from app.api.middleware.auth import auth_required
from app.core.responses import success_response
from app.core.exceptions import ValidationException
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss.rss_feed_repository import RssFeedRepository
from app.infrastructure.database.repositories.rss.rss_category_repository import RssFeedCategoryRepository
from app.domains.rss.services.feed_service import FeedService

logger = logging.getLogger(__name__)

# 创建蓝图
feed_bp = Blueprint("feed", __name__)

@feed_bp.route("/list", methods=["GET"])
@auth_required
def get_feed_list():
    """获取Feed列表，支持分页和筛选
    
    支持的筛选参数:
    - page: 页码，默认1
    - per_page: 每页数量，默认20
    - title: 标题模糊搜索
    - category_id: 分类ID
    - is_active: 状态(1=启用, 0=禁用)
    
    Returns:
        Feed列表和分页信息
    """
    try:
        # 获取分页参数
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        
        # 构建筛选条件
        filters = {}
        
        # 标题筛选（模糊搜索）
        title = request.args.get("title")
        if title:
            filters["title"] = title
        
        # 分类筛选
        category_id = request.args.get("category_id", type=int)
        if category_id:
            filters["category_id"] = category_id
        
        # 状态筛选
        is_active = request.args.get("is_active", type=int)
        if is_active is not None:
            filters["is_active"] = bool(is_active)
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        category_repo = RssFeedCategoryRepository(db_session)
        
        # 创建服务
        feed_service = FeedService(feed_repo, category_repo)
        
        # 获取Feed列表
        result = feed_service.get_feeds(page, per_page, filters)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取Feed列表失败: {str(e)}")
        return success_response(None, f"获取Feed列表失败: {str(e)}", 60001)

@feed_bp.route("/detail", methods=["GET"])
@auth_required
def get_feed_detail():
    """获取Feed详情
    
    查询参数:
    - feed_id: Feed ID
    
    Returns:
        Feed详情
    """
    try:
        # 获取Feed ID
        feed_id = request.args.get("feed_id")
        if not feed_id:
            return success_response(None, "缺少feed_id参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        category_repo = RssFeedCategoryRepository(db_session)
        
        # 创建服务
        feed_service = FeedService(feed_repo, category_repo)
        
        # 获取Feed详情
        feed = feed_service.get_feed(feed_id)
        
        return success_response(feed)
    except Exception as e:
        logger.error(f"获取Feed详情失败: {str(e)}")
        return success_response(None, f"获取Feed详情失败: {str(e)}", 60001)

@feed_bp.route("/add", methods=["POST"])
@auth_required
def add_feed():
    """添加新Feed
    
    请求体:
    {
        "title": "Feed标题",
        "url": "Feed URL",
        "logo": "Logo URL",
        "category_id": 1,
        "description": "描述信息"
    }
    
    Returns:
        添加结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return success_response(None, "未提供数据", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        category_repo = RssFeedCategoryRepository(db_session)
        
        # 创建服务
        feed_service = FeedService(feed_repo, category_repo)
        
        # 添加Feed
        feed = feed_service.add_feed(data)
        
        return success_response(feed, "添加Feed成功")
    except Exception as e:
        logger.error(f"添加Feed失败: {str(e)}")
        return success_response(None, f"添加Feed失败: {str(e)}", 60001)

@feed_bp.route("/update", methods=["POST"])
@auth_required
def update_feed():
    """更新Feed信息
    
    请求体:
    {
        "feed_id": "Feed ID",
        "title": "新标题",
        "url": "新URL",
        "logo": "新Logo",
        "category_id": 2,
        "description": "新描述"
    }
    
    Returns:
        更新结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return success_response(None, "未提供数据", 60001)
        
        # 检查必需参数
        if "feed_id" not in data:
            return success_response(None, "缺少feed_id参数", 60001)
        
        feed_id = data.pop("feed_id")
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        category_repo = RssFeedCategoryRepository(db_session)
        
        # 创建服务
        feed_service = FeedService(feed_repo, category_repo)
        
        # 更新Feed
        feed = feed_service.update_feed(feed_id, data)
        
        return success_response(feed, "更新Feed成功")
    except Exception as e:
        logger.error(f"更新Feed失败: {str(e)}")
        return success_response(None, f"更新Feed失败: {str(e)}", 60001)

@feed_bp.route("/disable", methods=["POST"])
@auth_required
def disable_feed():
    """禁用Feed
    
    请求体:
    {
        "feed_id": "Feed ID"
    }
    
    Returns:
        操作结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "feed_id" not in data:
            return success_response(None, "缺少feed_id参数", 60001)
        
        feed_id = data["feed_id"]
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        category_repo = RssFeedCategoryRepository(db_session)
        
        # 创建服务
        feed_service = FeedService(feed_repo, category_repo)
        
        # 禁用Feed
        feed = feed_service.set_feed_status(feed_id, False)
        
        return success_response(feed, "禁用Feed成功")
    except Exception as e:
        logger.error(f"禁用Feed失败: {str(e)}")
        return success_response(None, f"禁用Feed失败: {str(e)}", 60001)

@feed_bp.route("/enable", methods=["POST"])
@auth_required
def enable_feed():
    """启用Feed
    
    请求体:
    {
        "feed_id": "Feed ID"
    }
    
    Returns:
        操作结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "feed_id" not in data:
            return success_response(None, "缺少feed_id参数", 60001)
        
        feed_id = data["feed_id"]
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        category_repo = RssFeedCategoryRepository(db_session)
        
        # 创建服务
        feed_service = FeedService(feed_repo, category_repo)
        
        # 启用Feed
        feed = feed_service.set_feed_status(feed_id, True)
        
        return success_response(feed, "启用Feed成功")
    except Exception as e:
        logger.error(f"启用Feed失败: {str(e)}")
        return success_response(None, f"启用Feed失败: {str(e)}", 60001)

@feed_bp.route("/categories", methods=["GET"])
@auth_required
def get_categories():
    """获取Feed分类列表
    
    Returns:
        分类列表
    """
    try:
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        category_repo = RssFeedCategoryRepository(db_session)
        
        # 创建服务
        feed_service = FeedService(feed_repo, category_repo)
        
        # 获取分类
        categories = feed_service.get_categories()
        
        return success_response(categories)
    except Exception as e:
        logger.error(f"获取Feed分类失败: {str(e)}")
        return success_response(None, f"获取Feed分类失败: {str(e)}", 60001)

@feed_bp.route("/upload-logo", methods=["POST"])
@auth_required
def upload_logo():
    """上传Feed图标
    
    Returns:
        上传结果
    """
    try:
        # 检查是否有文件
        if "file" not in request.files:
            return success_response(None, "未找到文件", 60001)
        
        file = request.files["file"]
        
        # 检查文件名是否为空
        if file.filename == "":
            return success_response(None, "未选择文件", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        category_repo = RssFeedCategoryRepository(db_session)
        
        # 创建服务
        feed_service = FeedService(feed_repo, category_repo)
        
        # 获取上传目录
        upload_folder = current_app.config.get("UPLOAD_FOLDER")
        
        # 处理上传
        try:
            file_url = feed_service.handle_logo_upload(file, upload_folder)
            return success_response({"url": file_url}, "上传成功")
        except Exception as upload_error:
            return success_response(None, f"文件上传失败: {str(upload_error)}", 60001)
    except Exception as e:
        logger.error(f"上传Feed图标失败: {str(e)}")
        return success_response(None, f"上传Feed图标失败: {str(e)}", 60001)