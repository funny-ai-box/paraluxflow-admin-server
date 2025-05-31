# app/api/client/v1/user/preferences.py
"""用户偏好设置API接口"""
from datetime import datetime
import logging
from flask import Blueprint, request, g

from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, NOT_FOUND
from app.core.exceptions import ValidationException
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.user_preferences_repository import UserPreferencesRepository
from app.domains.user.services.preferences_service import UserPreferencesService
from app.api.middleware.client_auth import client_auth_required

preferences_bp = Blueprint("preferences_bp", __name__)

logger = logging.getLogger(__name__)

@preferences_bp.route("get_preferences", methods=["GET"])
@client_auth_required
def get_user_preferences():
    """获取用户偏好设置
    
    查询参数:
    - category: 设置分类，可选
    
    Returns:
        用户偏好设置
    """
    try:
        user_id = g.user_id
        category = request.args.get("category")
        
        db_session = get_db_session()
        preferences_repo = UserPreferencesRepository(db_session)
        preferences_service = UserPreferencesService(preferences_repo)
        
        preferences = preferences_service.get_user_preferences(user_id, category)
        
        return success_response(preferences)
    except Exception as e:
        logger.error(f"获取用户偏好设置失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取用户偏好设置失败: {str(e)}")

@preferences_bp.route("/update_preferences", methods=["POST"])
@client_auth_required
def update_user_preferences():
    """批量更新用户偏好设置
    
    请求体:
    {
        "language": {
            "preferred_language": "zh-CN",
            "auto_translate": true,
            "summary_language": "zh-CN"
        },
        "reading": {
            "articles_per_page": 20,
            "auto_mark_read": true,
            "reading_mode": "comfortable"
        },
        "theme": {
            "color_scheme": "auto",
            "font_size": "medium"
        }
    }
    
    Returns:
        更新结果
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        db_session = get_db_session()
        preferences_repo = UserPreferencesRepository(db_session)
        preferences_service = UserPreferencesService(preferences_repo)
        
        result = preferences_service.update_user_preferences(user_id, data)
        
        return success_response(result, "偏好设置更新成功")
    except ValidationException as e:
        logger.warning(f"偏好设置验证失败: {e.message}")
        return error_response(e.code, e.message)
    except Exception as e:
        logger.error(f"更新用户偏好设置失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"更新用户偏好设置失败: {str(e)}")

@preferences_bp.route("/get_preference_by_key", methods=["GET"])
@client_auth_required
def get_user_preference(category, setting_key):
    """获取用户单个偏好设置
    
    Args:
        category: 设置分类
        setting_key: 设置键名
    
    Returns:
        偏好设置值
    """
    try:
        user_id = g.user_id
        
        db_session = get_db_session()
        preferences_repo = UserPreferencesRepository(db_session)
        preferences_service = UserPreferencesService(preferences_repo)
        
        value = preferences_service.get_user_preference(user_id, category, setting_key)
        
        return success_response({
            "category": category,
            "setting_key": setting_key,
            "value": value
        })
    except Exception as e:
        logger.error(f"获取用户偏好设置失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取用户偏好设置失败: {str(e)}")

@preferences_bp.route("/setting_preference", methods=["POST"])
@client_auth_required
def set_user_preference(category, setting_key):
    """设置用户单个偏好
    
    Args:
        category: 设置分类
        setting_key: 设置键名
    
    请求体:
    {
        "value": "设置值"
    }
    
    Returns:
        设置结果
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data or "value" not in data:
            return error_response(PARAMETER_ERROR, "未提供设置值")
        
        value = data["value"]
        
        db_session = get_db_session()
        preferences_repo = UserPreferencesRepository(db_session)
        preferences_service = UserPreferencesService(preferences_repo)
        
        result = preferences_service.set_user_preference(user_id, category, setting_key, value)
        
        return success_response(result, "偏好设置更新成功")
    except ValidationException as e:
        logger.warning(f"偏好设置验证失败: {e.message}")
        return error_response(e.code, e.message)
    except Exception as e:
        logger.error(f"设置用户偏好失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"设置用户偏好失败: {str(e)}")


@preferences_bp.route("/preferences/reset", methods=["POST"])
@client_auth_required
def reset_user_preferences():
    """重置用户偏好设置
    
    请求体:
    {
        "category": "language"  // 可选，不提供则重置所有
    }
    
    Returns:
        重置结果
    """
    try:
        user_id = g.user_id
        data = request.get_json() or {}
        category = data.get("category")
        
        db_session = get_db_session()
        preferences_repo = UserPreferencesRepository(db_session)
        preferences_service = UserPreferencesService(preferences_repo)
        
        result = preferences_service.reset_user_preferences(user_id, category)
        
        message = f"偏好设置重置成功" if not category else f"{category}偏好设置重置成功"
        return success_response(result, message)
    except Exception as e:
        logger.error(f"重置用户偏好设置失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"重置用户偏好设置失败: {str(e)}")

@preferences_bp.route("/preferences/definitions", methods=["GET"])
@client_auth_required
def get_preference_definitions():
    """获取偏好设置定义
    
    查询参数:
    - category: 设置分类，可选
    
    Returns:
        偏好设置定义列表
    """
    try:
        category = request.args.get("category")
        
        db_session = get_db_session()
        preferences_repo = UserPreferencesRepository(db_session)
        preferences_service = UserPreferencesService(preferences_repo)
        
        definitions = preferences_service.get_preference_definitions(category)
        
        # 按分类组织数据
        if not category:
            organized_definitions = {}
            for definition in definitions:
                cat = definition["category"]
                if cat not in organized_definitions:
                    organized_definitions[cat] = []
                organized_definitions[cat].append(definition)
            
            return success_response(organized_definitions)
        else:
            return success_response(definitions)
    except Exception as e:
        logger.error(f"获取偏好设置定义失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取偏好设置定义失败: {str(e)}")
