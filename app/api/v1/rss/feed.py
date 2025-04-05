"""RSS Feed API控制器"""
import os
import time
import logging
from datetime import datetime
from typing import Dict, Any
from urllib.parse import urlparse, unquote

from flask import Blueprint, request, jsonify, Response, g, current_app
from werkzeug.utils import secure_filename

from app.api.middleware.auth import auth_required
from app.core.responses import error_response, success_response
from app.core.exceptions import ValidationException, NotFoundException
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss_repository import (
    RssFeedRepository,
    RssFeedCategoryRepository,

    RssFeedArticleRepository,
    RssFeedArticleContentRepository
)
from app.domains.feed.services.feed_service import FeedService
from app.core.status_codes import PARAMETER_ERROR

logger = logging.getLogger(__name__)

# 创建蓝图
feed_bp = Blueprint("feed", __name__)

# 允许上传的文件扩展名
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


def allowed_file(filename):
    """检查文件扩展名是否允许
    
    Args:
        filename: 文件名
        
    Returns:
        是否允许
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


 

@feed_bp.route("/upload-logo", methods=["POST"])
@auth_required
def upload_logo():
    """上传Feed图标
    
    Returns:
        上传结果
    """
    # 检查是否有文件
    if "file" not in request.files:
        return success_response(None, "未找到文件", 60005)
    
    file = request.files["file"]
    
    # 检查文件名是否为空
    if file.filename == "":
        return success_response(None, "未选择文件", 60006)
    
    if file and allowed_file(file.filename):
        # 处理文件名
        original_filename = file.filename
        filename = secure_filename(original_filename)
        
        # 确保文件扩展名被保留
        file_ext = os.path.splitext(original_filename)[1]
        if not filename.lower().endswith(file_ext.lower()):
            filename = f"{filename}{file_ext}"
        
        # 生成唯一文件名
        unique_filename = f"{int(time.time())}_{filename}"
        
        # 暂存文件
        temp_path = os.path.join("/tmp", unique_filename)
        file.save(temp_path)
        
        try:
            # TODO: 实现文件上传到对象存储
            # 模拟成功上传
            file_url = f"https://example.com/uploads/{unique_filename}"
            
            # 删除临时文件
            os.remove(temp_path)
            
            return success_response({"url": file_url})
        except Exception as e:
            # 确保删除临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"文件上传失败: {str(e)}")
            return success_response(None, f"文件上传失败: {str(e)}", 60007)
    
    return success_response(None, "不支持的文件类型，只支持png、jpg、jpeg", 60008)


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
      
        
        # 获取分页Feed列表
        result = feed_repo.get_filtered_feeds(filters, page, per_page)
        
        # 获取所有分类和集合（用于关联数据）
        all_categories = category_repo.get_all_categories()

        # 关联数据
        for feed in result["list"]:
            # 关联分类
            category = next(
                (cat for cat in all_categories if cat["id"] == feed["category_id"]), None
            )
            feed["category"] = category
         
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取Feed列表失败: {str(e)}")
        return error_response(60002, f"获取Feed列表失败: {str(e)}", )


@feed_bp.route("/detail", methods=["GET"])
@auth_required
def get_feed_detail():
    """获取Feed详情
    
    Returns:
        Feed详情
    """
    try:
        # 获取Feed ID
        feed_id = request.args.get("feed_id")
        if not feed_id:
            return error_response(60001, "缺少feed_id参数", )
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        
        # 获取Feed详情
        err, feed = feed_repo.get_feed_by_id(feed_id)
        if err:
            return error_response(60002, f"获取Feed信息失败: {err}", )
        
        return success_response(feed)
    except Exception as e:
        logger.error(f"获取Feed详情失败: {str(e)}")
        return error_response(60003, f"获取Feed详情失败: {str(e)}", )


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
        category_repo = RssFeedCategoryRepository(db_session)
        
        # 获取所有分类
        categories = category_repo.get_all_categories()
        
        return success_response(categories)
    except Exception as e:
        logger.error(f"获取Feed分类失败: {str(e)}")
        return success_response(None, f"获取Feed分类失败: {str(e)}", 60001)


@feed_bp.route("/add_feed", methods=["POST"])
@auth_required
def add_feed():
    """添加新Feed
    
    Returns:
        添加结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(60001, "未提供数据")
        
        # 验证必填字段
        required_fields = ["title", "logo", "url", "category_id"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return error_response(60001, f"缺少必填字段: {', '.join(missing_fields)}")
        

        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        
        # 添加Feed
        err, result = feed_repo.add_feed(data)
        if err:
            return error_response(60002, f"添加Feed失败: {err}")
        
        return success_response(result)
    except Exception as e:
        logger.error(f"添加Feed失败: {str(e)}")
        return error_response(60003, f"添加Feed失败: {str(e)}")


@feed_bp.route("/sync_articles", methods=["POST"])
@auth_required
def sync_feed_articles():
    """同步Feed文章
    
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
        feed_repo = RssFeedRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)
        
        # 获取Feed信息
        err, feed = feed_repo.get_feed_by_id(int(feed_id))
        if err:
            return success_response(None, f"获取Feed信息失败: {err}", 60002)
        
        feed_url = feed.get("url")
        if not feed_url:
            return success_response(None, "Feed URL不存在", 60003)
        
        # 获取Feed条目
        try:
            entries, error = FeedService.format_feed_entries(feed_url)
        except Exception as e:
            return success_response(None, f"获取Feed条目失败: {str(e)}", 60004)
        
        if error:
            return success_response(None, f"获取Feed条目失败: {error}", 60004)
        
        # 转换为文章格式
        articles_to_insert = []
        for entry in entries:
            try:
                article = {
                    "feed_id": feed_id,
                    "feed_logo": feed.get("logo"),
                    "feed_title": feed.get("title"),
                    "link": entry.get("link"),
                    "title": entry.get("title"),
                    "summary": entry.get("summary", ""),
                    "thumbnail_url": entry.get("thumbnail_url"),
                    "status": 0,
                    "published_date": datetime.fromisoformat(entry.get("published_date")),
                }
                articles_to_insert.append(article)
            except Exception as e:
                logger.error(f"处理条目失败: {str(e)}")
                continue
        
        if not articles_to_insert:
            return success_response(None, "没有有效文章可插入", 60005)
        
        # 插入新文章
        success = article_repo.insert_articles(articles_to_insert)
        if success:
            # 更新Feed获取时间
            feed_repo.bulk_update_feeds_fetch_time([int(feed_id)])
            return success_response({
                "total_processed": len(articles_to_insert),
                "feed_id": feed_id
            })
        
        return success_response(None, "插入文章失败", 60005)
    except Exception as e:
        logger.error(f"同步Feed文章失败: {str(e)}")
        return success_response(None, f"同步Feed文章失败: {str(e)}", 60007)


