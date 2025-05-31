# app/domains/user/services/preferences_service.py
"""用户偏好设置服务实现"""
import logging
from typing import Dict, List, Any, Optional

from app.infrastructure.database.repositories.user_preferences_repository import UserPreferencesRepository
from app.core.exceptions import ValidationException
from app.core.status_codes import PARAMETER_ERROR

logger = logging.getLogger(__name__)

class UserPreferencesService:
    """用户偏好设置服务"""
    
    def __init__(self, preferences_repo: UserPreferencesRepository):
        """初始化服务
        
        Args:
            preferences_repo: 偏好设置仓库
        """
        self.preferences_repo = preferences_repo
    
    def get_user_preferences(self, user_id: str, category: Optional[str] = None) -> Dict[str, Any]:
        """获取用户偏好设置
        
        Args:
            user_id: 用户ID
            category: 设置分类，可选
            
        Returns:
            偏好设置
        """
        preferences = self.preferences_repo.get_user_preferences(user_id, category)
        
        # 如果用户没有某些设置，使用默认值补充
        if not category:
            all_definitions = self.preferences_repo.get_preference_definitions()
            
            # 按分类组织默认值
            for definition in all_definitions:
                cat = definition["category"]
                key = definition["setting_key"]
                
                if cat not in preferences:
                    preferences[cat] = {}
                
                if key not in preferences[cat]:
                    preferences[cat][key] = {
                        "value": definition["default_value"],
                        "type": definition["value_type"],
                        "description": definition["description"],
                        "is_default": True
                    }
        
        return preferences
    
    def get_user_preference(self, user_id: str, category: str, setting_key: str) -> Any:
        """获取用户单个偏好设置
        
        Args:
            user_id: 用户ID
            category: 设置分类
            setting_key: 设置键名
            
        Returns:
            设置值
        """
        return self.preferences_repo.get_user_preference(user_id, category, setting_key)
    
    def set_user_preference(self, user_id: str, category: str, setting_key: str, 
                          value: Any, validate: bool = True) -> Dict[str, Any]:
        """设置用户偏好
        
        Args:
            user_id: 用户ID
            category: 设置分类
            setting_key: 设置键名
            value: 设置值
            validate: 是否验证值
            
        Returns:
            设置结果
            
        Raises:
            ValidationException: 验证失败时抛出异常
        """
        # 验证设置
        if validate:
            self._validate_preference_value(category, setting_key, value)
        
        # 设置偏好
        success = self.preferences_repo.set_user_preference(user_id, category, setting_key, value)
        
        if not success:
            raise Exception("设置偏好失败")
        
        return {
            "user_id": user_id,
            "category": category,
            "setting_key": setting_key,
            "value": value,
            "success": True
        }
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Dict[str, Any]], 
                              validate: bool = True) -> Dict[str, Any]:
        """批量更新用户偏好设置
        
        Args:
            user_id: 用户ID
            preferences: 偏好设置字典
            validate: 是否验证值
            
        Returns:
            更新结果
            
        Raises:
            ValidationException: 验证失败时抛出异常
        """
        # 验证所有设置
        if validate:
            for category, settings in preferences.items():
                for setting_key, value in settings.items():
                    self._validate_preference_value(category, setting_key, value)
        
        # 批量设置
        success = self.preferences_repo.set_user_preferences_batch(user_id, preferences)
        
        if not success:
            raise Exception("批量更新偏好设置失败")
        
        return {
            "user_id": user_id,
            "updated_count": sum(len(settings) for settings in preferences.values()),
            "success": True
        }
    
    def reset_user_preferences(self, user_id: str, category: Optional[str] = None) -> Dict[str, Any]:
        """重置用户偏好设置
        
        Args:
            user_id: 用户ID
            category: 设置分类，可选
            
        Returns:
            重置结果
        """
        success = self.preferences_repo.reset_user_preferences(user_id, category)
        
        if not success:
            raise Exception("重置偏好设置失败")
        
        return {
            "user_id": user_id,
            "category": category,
            "success": True
        }
    
    def get_preference_definitions(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取偏好设置定义
        
        Args:
            category: 设置分类，可选
            
        Returns:
            设置定义列表
        """
        return self.preferences_repo.get_preference_definitions(category)
    
    def get_user_language_preference(self, user_id: str) -> str:
        """获取用户语言偏好
        
        Args:
            user_id: 用户ID
            
        Returns:
            语言代码，默认为 zh-CN
        """
        language = self.preferences_repo.get_user_preference(user_id, "language", "preferred_language")
        return language or "zh-CN"
    
    def get_user_reading_preferences(self, user_id: str) -> Dict[str, Any]:
        """获取用户阅读偏好设置
        
        Args:
            user_id: 用户ID
            
        Returns:
            阅读偏好设置
        """
        reading_prefs = self.preferences_repo.get_user_preferences(user_id, "reading")
        return reading_prefs.get("reading", {})
    
    def get_user_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        """获取用户通知偏好设置
        
        Args:
            user_id: 用户ID
            
        Returns:
            通知偏好设置
        """
        notification_prefs = self.preferences_repo.get_user_preferences(user_id, "notification")
        return notification_prefs.get("notification", {})
    
    def get_user_hot_topics_preferences(self, user_id: str) -> Dict[str, Any]:
        """获取用户热点话题偏好设置
        
        Args:
            user_id: 用户ID
            
        Returns:
            热点话题偏好设置
        """
        hot_topics_prefs = self.preferences_repo.get_user_preferences(user_id, "hot_topics")
        return hot_topics_prefs.get("hot_topics", {})
    
    def _validate_preference_value(self, category: str, setting_key: str, value: Any) -> None:
        """验证偏好设置值
        
        Args:
            category: 设置分类
            setting_key: 设置键名
            value: 设置值
            
        Raises:
            ValidationException: 验证失败时抛出异常
        """
        # 获取设置定义
        definition = self.preferences_repo.get_preference_definition(category, setting_key)
        
        if not definition:
            logger.warning(f"未找到偏好设置定义: {category}.{setting_key}")
            return  # 允许设置未定义的偏好
        
        # 检查必填
        if definition.get("is_required", False) and (value is None or value == ""):
            raise ValidationException(f"{definition['setting_name']}是必填项", PARAMETER_ERROR)
        
        # 检查值类型
        value_type = definition.get("value_type", "string")
        if value is not None:
            if value_type == "boolean" and not isinstance(value, bool):
                if isinstance(value, str):
                    if value.lower() not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
                        raise ValidationException(f"{definition['setting_name']}必须是布尔值", PARAMETER_ERROR)
                else:
                    raise ValidationException(f"{definition['setting_name']}必须是布尔值", PARAMETER_ERROR)
            
            elif value_type == "number" and not isinstance(value, (int, float)):
                try:
                    float(value)
                except (ValueError, TypeError):
                    raise ValidationException(f"{definition['setting_name']}必须是数字", PARAMETER_ERROR)
            
            elif value_type == "array" and not isinstance(value, list):
                raise ValidationException(f"{definition['setting_name']}必须是数组", PARAMETER_ERROR)
        
        # 检查可选值
        options = definition.get("options")
        if options and value is not None:
            valid_values = [opt.get("value") for opt in options if isinstance(opt, dict)]
            if valid_values and value not in valid_values:
                raise ValidationException(
                    f"{definition['setting_name']}的值必须是以下之一: {', '.join(map(str, valid_values))}", 
                    PARAMETER_ERROR
                )
        
        # 检查验证规则
        validation_rules = definition.get("validation_rules")
        if validation_rules and value is not None:
            self._apply_validation_rules(definition['setting_name'], value, validation_rules)
    
    def _apply_validation_rules(self, setting_name: str, value: Any, rules: Dict[str, Any]) -> None:
        """应用验证规则
        
        Args:
            setting_name: 设置名称
            value: 设置值
            rules: 验证规则
            
        Raises:
            ValidationException: 验证失败时抛出异常
        """
        # 字符串长度验证
        if "min_length" in rules and isinstance(value, str):
            if len(value) < rules["min_length"]:
                raise ValidationException(
                    f"{setting_name}长度不能少于{rules['min_length']}个字符", 
                    PARAMETER_ERROR
                )
        
        if "max_length" in rules and isinstance(value, str):
            if len(value) > rules["max_length"]:
                raise ValidationException(
                    f"{setting_name}长度不能超过{rules['max_length']}个字符", 
                    PARAMETER_ERROR
                )
        
        # 数值范围验证
        if "min_value" in rules and isinstance(value, (int, float)):
            if value < rules["min_value"]:
                raise ValidationException(
                    f"{setting_name}不能小于{rules['min_value']}", 
                    PARAMETER_ERROR
                )
        
        if "max_value" in rules and isinstance(value, (int, float)):
            if value > rules["max_value"]:
                raise ValidationException(
                    f"{setting_name}不能大于{rules['max_value']}", 
                    PARAMETER_ERROR
                )
        
        # 数组长度验证
        if "min_items" in rules and isinstance(value, list):
            if len(value) < rules["min_items"]:
                raise ValidationException(
                    f"{setting_name}至少需要{rules['min_items']}个项目", 
                    PARAMETER_ERROR
                )
        
        if "max_items" in rules and isinstance(value, list):
            if len(value) > rules["max_items"]:
                raise ValidationException(
                    f"{setting_name}最多只能有{rules['max_items']}个项目", 
                    PARAMETER_ERROR
                )
        
        # 正则表达式验证
        if "pattern" in rules and isinstance(value, str):
            import re
            if not re.match(rules["pattern"], value):
                error_message = rules.get("pattern_message", f"{setting_name}格式不正确")
                raise ValidationException(error_message, PARAMETER_ERROR)