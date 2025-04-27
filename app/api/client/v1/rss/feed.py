# app/api/client/v1/rss/feed.py
"""客户端Feed API接口 (GET/POST only, No user add, No groups)"""
import logging
from flask import Blueprint, request, g

from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, NOT_FOUND
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss.rss_feed_repository import RssFeedRepository
from app.infrastructure.database.repositories.rss.rss_category_repository import RssFeedCategoryRepository
from app.infrastructure.database.repositories.user_repository import UserSubscriptionRepository
from app.domains.rss.services.feed_service import FeedService # Assuming admin service can be reused if logic fits
from app.api.middleware.client_auth import client_auth_required

# Define blueprint with a base prefix if desired, e.g., /client/v1/feed
# Assuming feed_bp is defined in app/api/client/v1/rss/__init__.py
feed_bp = Blueprint("client_feed", __name__) # Removed url_prefix for flatter routes


logger = logging.getLogger(__name__)

@feed_bp.route("/discover", methods=["GET"])
@client_auth_required
def discover_feeds():
    """发现Feed列表，支持分页和筛选
    
    查询参数:
    - page: 页码，默认1
    - per_page: 每页数量，默认20
    - title: 标题模糊搜索
    - category_id: 分类ID
    
    Returns:
        Feed列表和分页信息
    """
    try:
        user_id = g.user_id
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        
        filters = {"is_active": True}
        title = request.args.get("title")
        if title:
            filters["title"] = title
        category_id = request.args.get("category_id", type=int)
        if category_id:
            filters["category_id"] = category_id
            
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        category_repo = RssFeedCategoryRepository(db_session) # Needed for FeedService
        subscription_repo = UserSubscriptionRepository(db_session)
        
        # Use FeedService from domains layer
        feed_service = FeedService(feed_repo, category_repo)
        
        # Fetch feeds using the service
        result = feed_service.get_feeds(page, per_page, filters)
        
        # Get user's subscriptions to mark status
        user_subscriptions = subscription_repo.get_user_subscriptions(user_id)
        subscribed_feed_ids = {sub["feed_id"] for sub in user_subscriptions}
        
        # Mark subscription status and add category name
        for feed in result["list"]:
            feed["is_subscribed"] = feed["id"] in subscribed_feed_ids
            # Category info should already be added by FeedService.get_feeds

        return success_response(result)
    except Exception as e:
        logger.error(f"发现Feed列表失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"发现Feed列表失败: {str(e)}")

@feed_bp.route("/detail", methods=["GET"])
@client_auth_required
def get_feed_detail():
    """获取Feed详情

    查询参数:
    - feed_id: Feed ID (Required)

    Returns:
        Feed详情和用户订阅状态
    """
    try:
        user_id = g.user_id
        feed_id = request.args.get("feed_id")
        if not feed_id:
            return error_response(PARAMETER_ERROR, "缺少 feed_id 查询参数")

        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        category_repo = RssFeedCategoryRepository(db_session)
        subscription_repo = UserSubscriptionRepository(db_session) # Repository 实例

        feed_service = FeedService(feed_repo, category_repo)

        # Get Feed detail using service
        feed = feed_service.get_feed(feed_id) # Raises exception if not found

        # Check subscription status
        subscription_obj = subscription_repo.get_subscription(user_id, feed_id) # 获取 UserSubscription 对象
        is_subscribed = subscription_obj is not None
        subscription_dict = None # 初始化为 None
        if subscription_obj:
            # *** 使用 subscription_to_dict 方法转换对象 ***
            subscription_dict = subscription_repo.subscription_to_dict(subscription_obj)

        # Add category name (保持不变)
        if feed.get("category_id"):
             category = category_repo.get_category_by_id(feed["category_id"])
             if category:
                feed["category_name"] = category.get("name")

        result = {
            "feed": feed,
            "is_subscribed": is_subscribed,
            "subscription": subscription_dict # <--- 使用转换后的字典
        }

        return success_response(result)
    except Exception as e:
        logger.error(f"获取Feed详情失败 (ID: {feed_id}): {str(e)}", exc_info=True)
        return error_response(NOT_FOUND if "获取Feed信息失败" in str(e) else PARAMETER_ERROR, f"获取Feed详情失败: {str(e)}")



@feed_bp.route("/categories", methods=["GET"])
@client_auth_required
def get_categories():
    """获取Feed分类列表
    
    Returns:
        分类列表
    """
    try:
        db_session = get_db_session()
        category_repo = RssFeedCategoryRepository(db_session)
        
        # Get all active categories
        categories = category_repo.get_all_categories()
        
        return success_response(categories)
    except Exception as e:
        logger.error(f"获取Feed分类失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取Feed分类失败: {str(e)}")

