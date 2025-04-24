# app/api/client/v1/subscription/subscription.py
"""客户端订阅API接口 (GET/POST only, No groups)"""
import logging
from flask import Blueprint, request, g

from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, NOT_FOUND
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.user_repository import UserSubscriptionRepository # 
from app.infrastructure.database.repositories.rss.rss_feed_repository import RssFeedRepository
from app.domains.subscription.services.subscription_service import SubscriptionService
from app.api.middleware.client_auth import client_auth_required

# Assuming subscription_bp is defined in app/api/client/v1/subscription/__init__.py
subscription_bp = Blueprint("client_subscription", __name__) # Removed url_prefix

logger = logging.getLogger(__name__)


def get_subscription_service():
    db_session = get_db_session()
    subscription_repo = UserSubscriptionRepository(db_session)
    feed_repo = RssFeedRepository(db_session)

    return SubscriptionService(subscription_repo, feed_repo)


@subscription_bp.route("/list", methods=["GET"])
@client_auth_required
def get_subscriptions():
    """获取用户的订阅列表 (无分组)
    
    Returns:
        订阅列表 (包含Feed详情)
    """
    try:
        user_id = g.user_id
        subscription_service = get_subscription_service()
        
        # Service method needs adjustment if it previously relied heavily on groups
        # Assuming get_user_subscriptions can work without groups or needs modification
        # Let's simplify: directly use the repo here or adapt the service.
        
        db_session = get_db_session()
        subscription_repo = UserSubscriptionRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        subscriptions = subscription_repo.get_user_subscriptions(user_id)
        
        # Fetch Feed details for each subscription
        subscriptions_with_details = []
        for sub in subscriptions:
            err, feed = feed_repo.get_feed_by_id(sub["feed_id"])
            if not err and feed:
                 # Remove group_id if it exists in the sub dict
                 sub.pop("group_id", None)
                 subscriptions_with_details.append({**sub, "feed": feed})
            else:
                 logger.warning(f"Feed ID {sub['feed_id']} not found for subscription {sub['id']}")
                 # Optionally skip subscriptions with missing feeds
                 # subscriptions_with_details.append({**sub, "feed": None, "error": "Feed not found"})

        return success_response(subscriptions_with_details)
        
    except Exception as e:
        logger.error(f"获取订阅列表失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取订阅列表失败: {str(e)}")

@subscription_bp.route("/add", methods=["POST"])
@client_auth_required
def add_subscription():
    """添加订阅
    
    请求体:
    {
        "feed_id": "Feed ID" 
    }
    
    Returns:
        添加结果 { "subscription": ..., "feed": ... }
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        feed_id = data.get("feed_id")
        if not feed_id:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        subscription_service = get_subscription_service()
        

        result = subscription_service.add_subscription(user_id, feed_id) 
        

            
        return success_response(None, "添加订阅成功")
    except Exception as e:
        # Check if error is due to feed not found
        if "获取Feed失败" in str(e):
             return error_response(NOT_FOUND, f"添加订阅失败: Feed不存在或无法访问")
        # Check if error is due to already subscribed (assuming repo/service handles this)
        elif "已经订阅" in str(e): # Hypothetical error message check
             return error_response(PARAMETER_ERROR, f"添加订阅失败: 您已订阅该Feed")
        else:
             logger.error(f"添加订阅失败: {str(e)}", exc_info=True)
             return error_response(PARAMETER_ERROR, f"添加订阅失败: {str(e)}")


@subscription_bp.route("/remove", methods=["POST"])
@client_auth_required
def remove_subscription():
    """移除订阅
    
    请求体:
    {
        "feed_id": "Feed ID"
    }
    
    Returns:
        移除结果 { "success": true }
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        feed_id = data.get("feed_id")
        if not feed_id:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        subscription_service = get_subscription_service()
        
        # Call service method (ensure it doesn't require group_id logic)
        result = subscription_service.remove_subscription(user_id, feed_id)
        
        return success_response(None, "移除订阅成功")
    except Exception as e:
        logger.error(f"移除订阅失败: {str(e)}", exc_info=True)
        db_session = get_db_session()
        sub_repo = UserSubscriptionRepository(db_session)
        if not sub_repo.get_subscription(user_id, feed_id):
             return error_response(NOT_FOUND, f"移除订阅失败: 未找到对应的订阅记录")
        else:
            return error_response(PARAMETER_ERROR, f"移除订阅失败: {str(e)}")

