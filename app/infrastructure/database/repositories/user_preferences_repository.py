# app/infrastructure/database/repositories/user_preferences_repository.py
"""用户偏好设置仓库"""
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.user_preferences import UserPreference, PreferenceDefinition

logger = logging.getLogger(__name__)

class UserPreferencesRepository:
    """用户偏好设置仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_user_preferences(self, user_id: str, category: Optional[str] = None) -> Dict[str, Any]:
        """获取用户偏好设置
        
        Args:
            user_id: 用户ID
            category: 设置分类，可选
            
        Returns:
            偏好设置字典，按分类组织
        """
        try:
            query = self.db.query(UserPreference).filter(
                UserPreference.user_id == user_id,
                UserPreference.is_active == True
            )
            
            if category:
                query = query.filter(UserPreference.category == category)
            
            preferences = query.all()
            
            # 组织数据结构
            result = {}
            for pref in preferences:
                if pref.category not in result:
                    result[pref.category] = {}
                
                # 解析设置值
                parsed_value = self._parse_setting_value(pref.setting_value, pref.value_type)
                result[pref.category][pref.setting_key] = {
                    "value": parsed_value,
                    "type": pref.value_type,
                    "description": pref.description,
                    "updated_at": pref.updated_at.isoformat() if pref.updated_at else None
                }
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"获取用户偏好设置失败, user_id={user_id}: {str(e)}")
            return {}

    def get_user_preference(self, user_id: str, category: str, setting_key: str) -> Optional[Any]:
        """获取用户单个偏好设置
        
        Args:
            user_id: 用户ID
            category: 设置分类
            setting_key: 设置键名
            
        Returns:
            设置值或None
        """
        try:
            preference = self.db.query(UserPreference).filter(
                UserPreference.user_id == user_id,
                UserPreference.category == category,
                UserPreference.setting_key == setting_key,
                UserPreference.is_active == True
            ).first()
            
            if preference:
                return self._parse_setting_value(preference.setting_value, preference.value_type)
            
            # 如果用户没有设置，返回默认值
            return self.get_default_value(category, setting_key)
        except SQLAlchemyError as e:
            logger.error(f"获取用户偏好设置失败, user_id={user_id}, {category}.{setting_key}: {str(e)}")
            return None

    def set_user_preference(self, user_id: str, category: str, setting_key: str, 
                          value: Any, description: Optional[str] = None) -> bool:
        """设置用户偏好
        
        Args:
            user_id: 用户ID
            category: 设置分类
            setting_key: 设置键名
            value: 设置值
            description: 设置描述
            
        Returns:
            是否设置成功
        """
        try:
            # 获取设置定义来确定值类型
            definition = self.get_preference_definition(category, setting_key)
            value_type = definition.get("value_type", "string") if definition else "string"
            
            # 序列化设置值
            serialized_value = self._serialize_setting_value(value, value_type)
            
            # 查找现有设置
            existing = self.db.query(UserPreference).filter(
                UserPreference.user_id == user_id,
                UserPreference.category == category,
                UserPreference.setting_key == setting_key
            ).first()
            
            if existing:
                # 更新现有设置
                existing.setting_value = serialized_value
                existing.value_type = value_type
                existing.is_active = True
                existing.updated_at = datetime.now()
                if description:
                    existing.description = description
            else:
                # 创建新设置
                new_preference = UserPreference(
                    user_id=user_id,
                    category=category,
                    setting_key=setting_key,
                    setting_value=serialized_value,
                    value_type=value_type,
                    description=description,
                    is_active=True
                )
                self.db.add(new_preference)
            
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"设置用户偏好失败, user_id={user_id}, {category}.{setting_key}: {str(e)}")
            return False

    def set_user_preferences_batch(self, user_id: str, preferences: Dict[str, Dict[str, Any]]) -> bool:
        """批量设置用户偏好
        
        Args:
            user_id: 用户ID
            preferences: 偏好设置字典，格式：{category: {setting_key: value}}
            
        Returns:
            是否设置成功
        """
        try:
            for category, settings in preferences.items():
                for setting_key, value in settings.items():
                    self.set_user_preference(user_id, category, setting_key, value)
            
            return True
        except Exception as e:
            logger.error(f"批量设置用户偏好失败, user_id={user_id}: {str(e)}")
            return False

    def reset_user_preferences(self, user_id: str, category: Optional[str] = None) -> bool:
        """重置用户偏好设置到默认值
        
        Args:
            user_id: 用户ID
            category: 设置分类，可选
            
        Returns:
            是否重置成功
        """
        try:
            query = self.db.query(UserPreference).filter(UserPreference.user_id == user_id)
            
            if category:
                query = query.filter(UserPreference.category == category)
            
            # 标记为不活跃而不是删除
            query.update({"is_active": False, "updated_at": datetime.now()})
            
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"重置用户偏好设置失败, user_id={user_id}: {str(e)}")
            return False

    def get_preference_definitions(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取偏好设置定义
        
        Args:
            category: 设置分类，可选
            
        Returns:
            设置定义列表
        """
        try:
            query = self.db.query(PreferenceDefinition).filter(PreferenceDefinition.is_active == True)
            
            if category:
                query = query.filter(PreferenceDefinition.category == category)
            
            definitions = query.order_by(PreferenceDefinition.sort_order).all()
            
            result = []
            for definition in definitions:
                result.append({
                    "id": definition.id,
                    "category": definition.category,
                    "setting_key": definition.setting_key,
                    "setting_name": definition.setting_name,
                    "description": definition.description,
                    "value_type": definition.value_type,
                    "default_value": self._parse_setting_value(definition.default_value, definition.value_type),
                    "validation_rules": definition.validation_rules,
                    "options": definition.options,
                    "is_required": definition.is_required,
                    "sort_order": definition.sort_order
                })
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"获取偏好设置定义失败: {str(e)}")
            return []

    def get_preference_definition(self, category: str, setting_key: str) -> Optional[Dict[str, Any]]:
        """获取单个偏好设置定义
        
        Args:
            category: 设置分类
            setting_key: 设置键名
            
        Returns:
            设置定义或None
        """
        try:
            definition = self.db.query(PreferenceDefinition).filter(
                PreferenceDefinition.category == category,
                PreferenceDefinition.setting_key == setting_key,
                PreferenceDefinition.is_active == True
            ).first()
            
            if definition:
                return {
                    "id": definition.id,
                    "category": definition.category,
                    "setting_key": definition.setting_key,
                    "setting_name": definition.setting_name,
                    "description": definition.description,
                    "value_type": definition.value_type,
                    "default_value": self._parse_setting_value(definition.default_value, definition.value_type),
                    "validation_rules": definition.validation_rules,
                    "options": definition.options,
                    "is_required": definition.is_required
                }
            
            return None
        except SQLAlchemyError as e:
            logger.error(f"获取偏好设置定义失败, {category}.{setting_key}: {str(e)}")
            return None

    def get_default_value(self, category: str, setting_key: str) -> Any:
        """获取默认值
        
        Args:
            category: 设置分类
            setting_key: 设置键名
            
        Returns:
            默认值
        """
        definition = self.get_preference_definition(category, setting_key)
        return definition.get("default_value") if definition else None

    def _parse_setting_value(self, value: str, value_type: str) -> Any:
        """解析设置值
        
        Args:
            value: 设置值字符串
            value_type: 值类型
            
        Returns:
            解析后的值
        """
        if value is None:
            return None
        
        try:
            if value_type == "boolean":
                return value.lower() in ("true", "1", "yes", "on") if isinstance(value, str) else bool(value)
            elif value_type == "number":
                return float(value) if "." in str(value) else int(value)
            elif value_type in ("json", "array"):
                return json.loads(value) if isinstance(value, str) else value
            else:  # string
                return str(value)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"解析设置值失败: {value}, type: {value_type}, error: {str(e)}")
            return value

    def _serialize_setting_value(self, value: Any, value_type: str) -> str:
        """序列化设置值
        
        Args:
            value: 设置值
            value_type: 值类型
            
        Returns:
            序列化后的字符串
        """
        try:
            if value_type in ("json", "array"):
                return json.dumps(value, ensure_ascii=False)
            else:
                return str(value)
        except Exception as e:
            logger.warning(f"序列化设置值失败: {value}, type: {value_type}, error: {str(e)}")
            return str(value)