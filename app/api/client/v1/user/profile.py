# app/api/client/v1/user/profile.py
"""用户资料API接口"""
import logging
from flask import Blueprint, request, g

from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.user_repository import UserRepository
from app.infrastructure.database.repositories.user_repository import UserReadingHistoryRepository
from app.infrastructure.database.repositories.user_repository import UserSubscriptionRepository
from app.domains.user.services.profile_service import ProfileService
from app.api.middleware.client_auth import client_auth_required

from app.api.client.v1.user import profile_bp

logger = logging.getLogger(__name__)

@profile_bp.route("/info", methods=["GET"])
@client_auth_required
def get_user_profile():
    """获取用户资料
    
    Returns:
        用户资料
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 创建会话和存储库
        db_session = get_db_session()
        user_repo = UserRepository(db_session)
        reading_history_repo = UserReadingHistoryRepository(db_session)
        subscription_repo = UserSubscriptionRepository(db_session)
        
        # 创建服务
        profile_service = ProfileService(user_repo, reading_history_repo, subscription_repo)
        
        # 获取用户资料
        profile = profile_service.get_user_profile(user_id)
        
        return success_response(profile)
    except Exception as e:
        logger.error(f"获取用户资料失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取用户资料失败: {str(e)}")

@profile_bp.route("/update", methods=["POST"])
@client_auth_required
def update_user_profile():
    """更新用户资料
    
    请求体:
    {
        "username": "新用户名",  // 可选
        "avatar_url": "新头像URL",  // 可选
        "preferences": {  // 可选，用户偏好设置
            "theme": "dark",
            "font_size": "medium",
            "...": "..."
        }
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
        
        # 创建会话和存储库
        db_session = get_db_session()
        user_repo = UserRepository(db_session)
        
        # 创建服务
        profile_service = ProfileService(user_repo)
        
        # 更新用户资料
        result = profile_service.update_user_profile(user_id, data)
        
        return success_response(result, "更新用户资料成功")
    except Exception as e:
        logger.error(f"更新用户资料失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"更新用户资料失败: {str(e)}")

@profile_bp.route("/stats", methods=["GET"])
@client_auth_required
def get_reading_stats():
    """获取用户阅读统计
    
    Returns:
        阅读统计
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 创建会话和存储库
        db_session = get_db_session()
        user_repo = UserRepository(db_session)
        reading_history_repo = UserReadingHistoryRepository(db_session)
        
        # 创建服务
        profile_service = ProfileService(user_repo, reading_history_repo)
        
        # 获取阅读统计
        stats = profile_service.get_reading_stats(user_id)
        
        return success_response(stats)
    except Exception as e:
        logger.error(f"获取阅读统计失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取阅读统计失败: {str(e)}")

@profile_bp.route("/history", methods=["GET"])
@client_auth_required
def get_reading_history():
    """获取用户阅读历史
    
    查询参数:
    - limit: 限制数量，默认20
    - offset: 偏移量，默认0
    
    Returns:
        阅读历史
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取分页参数
        limit = request.args.get("limit", 20, type=int)
        offset = request.args.get("offset", 0, type=int)
        
        # 创建会话和存储库
        db_session = get_db_session()
        reading_history_repo = UserReadingHistoryRepository(db_session)
        
        # 获取阅读历史
        history = reading_history_repo.get_reading_history(user_id, limit, offset)
        
        return success_response(history)
    except Exception as e:
        logger.error(f"获取阅读历史失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取阅读历史失败: {str(e)}")

@profile_bp.route("/favorites", methods=["GET"])
@client_auth_required
def get_favorites():
    """获取用户收藏文章
    
    查询参数:
    - limit: 限制数量，默认20
    - offset: 偏移量，默认0
    
    Returns:
        收藏文章
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取分页参数
        limit = request.args.get("limit", 20, type=int)
        offset = request.args.get("offset", 0, type=int)
        
        # 创建会话和存储库
        db_session = get_db_session()
        reading_history_repo = UserReadingHistoryRepository(db_session)
        
        # 获取收藏文章
        favorites = reading_history_repo.get_favorites(user_id, limit, offset)
        
        return success_response(favorites)
    except Exception as e:
        logger.error(f"获取收藏文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取收藏文章失败: {str(e)}")