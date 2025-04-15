# app/api/client/v1/subscription/subscription.py
"""客户端订阅API接口"""
import logging
from flask import Blueprint, request, g

from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.user_repository import UserSubscriptionRepository, UserFeedGroupRepository
from app.infrastructure.database.repositories.rss_feed_repository import RssFeedRepository
from app.domains.subscription.services.subscription_service import SubscriptionService
from app.api.middleware.client_auth import client_auth_required

from app.api.client.v1.subscription import subscription_bp

logger = logging.getLogger(__name__)

@subscription_bp.route("/list", methods=["GET"])
@client_auth_required
def get_subscriptions():
    """获取用户的订阅列表
    
    Returns:
        订阅列表及分组信息
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 创建会话和存储库
        db_session = get_db_session()
        subscription_repo = UserSubscriptionRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        group_repo = UserFeedGroupRepository(db_session)
        
        # 创建服务
        subscription_service = SubscriptionService(subscription_repo, feed_repo, group_repo)
        
        # 获取订阅列表
        result = subscription_service.get_user_subscriptions(user_id)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取订阅列表失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取订阅列表失败: {str(e)}")

@subscription_bp.route("/add", methods=["POST"])
@client_auth_required
def add_subscription():
    """添加订阅
    
    请求体:
    {
        "feed_id": "Feed ID",
        "group_id": 1  // 可选
    }
    
    Returns:
        添加结果
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取请求参数
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        feed_id = data.get("feed_id")
        if not feed_id:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        group_id = data.get("group_id")
        
        # 创建会话和存储库
        db_session = get_db_session()
        subscription_repo = UserSubscriptionRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        group_repo = UserFeedGroupRepository(db_session)
        
        # 创建服务
        subscription_service = SubscriptionService(subscription_repo, feed_repo, group_repo)
        
        # 添加订阅
        result = subscription_service.add_subscription(user_id, feed_id, group_id)
        
        return success_response(result, "添加订阅成功")
    except Exception as e:
        logger.error(f"添加订阅失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"添加订阅失败: {str(e)}")

@subscription_bp.route("/update", methods=["POST"])
@client_auth_required
def update_subscription():
    """更新订阅
    
    请求体:
    {
        "feed_id": "Feed ID",
        "group_id": 1,  // 可选
        "custom_title": "自定义标题",  // 可选
        "is_favorite": true  // 可选
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
        
        feed_id = data.get("feed_id")
        if not feed_id:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        # 提取更新数据
        update_data = {}
        for key in ["group_id", "custom_title", "is_favorite"]:
            if key in data:
                update_data[key] = data[key]
        
        # 创建会话和存储库
        db_session = get_db_session()
        subscription_repo = UserSubscriptionRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        group_repo = UserFeedGroupRepository(db_session)
        
        # 创建服务
        subscription_service = SubscriptionService(subscription_repo, feed_repo, group_repo)
        
        # 更新订阅
        result = subscription_service.update_subscription(user_id, feed_id, update_data)
        
        return success_response(result, "更新订阅成功")
    except Exception as e:
        logger.error(f"更新订阅失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"更新订阅失败: {str(e)}")

@subscription_bp.route("/remove", methods=["POST"])
@client_auth_required
def remove_subscription():
    """移除订阅
    
    请求体:
    {
        "feed_id": "Feed ID"
    }
    
    Returns:
        移除结果
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取请求参数
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        feed_id = data.get("feed_id")
        if not feed_id:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        subscription_repo = UserSubscriptionRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        group_repo = UserFeedGroupRepository(db_session)
        
        # 创建服务
        subscription_service = SubscriptionService(subscription_repo, feed_repo, group_repo)
        
        # 移除订阅
        result = subscription_service.remove_subscription(user_id, feed_id)
        
        return success_response(result, "移除订阅成功")
    except Exception as e:
        logger.error(f"移除订阅失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"移除订阅失败: {str(e)}")

@subscription_bp.route("/groups", methods=["GET"])
@client_auth_required
def get_groups():
    """获取用户的分组列表
    
    Returns:
        分组列表
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 创建会话和存储库
        db_session = get_db_session()
        subscription_repo = UserSubscriptionRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        group_repo = UserFeedGroupRepository(db_session)
        
        # 创建服务
        subscription_service = SubscriptionService(subscription_repo, feed_repo, group_repo)
        
        # 获取分组列表
        groups = subscription_service.get_user_groups(user_id)
        
        return success_response(groups)
    except Exception as e:
        logger.error(f"获取分组列表失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取分组列表失败: {str(e)}")

@subscription_bp.route("/group/add", methods=["POST"])
@client_auth_required
def add_group():
    """添加分组
    
    请求体:
    {
        "name": "分组名称"
    }
    
    Returns:
        添加结果
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取请求参数
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        name = data.get("name")
        if not name:
            return error_response(PARAMETER_ERROR, "缺少name参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        subscription_repo = UserSubscriptionRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        group_repo = UserFeedGroupRepository(db_session)
        
        # 创建服务
        subscription_service = SubscriptionService(subscription_repo, feed_repo, group_repo)
        
        # 添加分组
        group = subscription_service.add_group(user_id, name)
        
        return success_response(group, "添加分组成功")
    except Exception as e:
        logger.error(f"添加分组失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"添加分组失败: {str(e)}")

@subscription_bp.route("/group/update", methods=["POST"])
@client_auth_required
def update_group():
    """更新分组
    
    请求体:
    {
        "group_id": 1,
        "name": "新分组名称"
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
        
        group_id = data.get("group_id")
        if not group_id:
            return error_response(PARAMETER_ERROR, "缺少group_id参数")
        
        name = data.get("name")
        if not name:
            return error_response(PARAMETER_ERROR, "缺少name参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        subscription_repo = UserSubscriptionRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        group_repo = UserFeedGroupRepository(db_session)
        
        # 创建服务
        subscription_service = SubscriptionService(subscription_repo, feed_repo, group_repo)
        
        # 更新分组
        group = subscription_service.update_group(user_id, group_id, name)
        
        return success_response(group, "更新分组成功")
    except Exception as e:
        logger.error(f"更新分组失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"更新分组失败: {str(e)}")

@subscription_bp.route("/group/delete", methods=["POST"])
@client_auth_required
def delete_group():
    """删除分组
    
    请求体:
    {
        "group_id": 1
    }
    
    Returns:
        删除结果
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取请求参数
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        group_id = data.get("group_id")
        if not group_id:
            return error_response(PARAMETER_ERROR, "缺少group_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        subscription_repo = UserSubscriptionRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        group_repo = UserFeedGroupRepository(db_session)
        
        # 创建服务
        subscription_service = SubscriptionService(subscription_repo, feed_repo, group_repo)
        
        # 删除分组
        result = subscription_service.delete_group(user_id, group_id)
        
        return success_response(result, "删除分组成功")
    except Exception as e:
        logger.error(f"删除分组失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"删除分组失败: {str(e)}")