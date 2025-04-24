# app/infrastructure/database/repositories/rss_category_repository.py
"""RSS Feed分类仓库"""
import logging
from typing import Dict, List, Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.rss import RssFeedCategory

logger = logging.getLogger(__name__)

class RssFeedCategoryRepository:
    """RSS Feed分类仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """获取所有分类
        
        Returns:
            所有分类列表
        """
        try:
            categories = self.db.query(RssFeedCategory).filter(
                RssFeedCategory.is_delete == 0
            ).all()
            return [self._category_to_dict(category) for category in categories]
        except SQLAlchemyError as e:
            logger.error(f"获取所有分类失败: {str(e)}")
            return []

    def get_category_by_id(self, category_id: int) -> Dict[str, Any]:
        """根据ID获取分类
        
        Args:
            category_id: 分类ID
            
        Returns:
            分类信息
            
        Raises:
            Exception: 获取失败时抛出异常
        """
        try:
            category = self.db.query(RssFeedCategory).filter(
                RssFeedCategory.id == category_id,
                RssFeedCategory.is_delete == 0
            ).first()
            
            if not category:
                raise Exception(f"未找到ID为{category_id}的分类")
            
            return self._category_to_dict(category)
        except SQLAlchemyError as e:
            logger.error(f"获取分类失败, ID={category_id}: {str(e)}")
            raise

    def _category_to_dict(self, category: RssFeedCategory) -> Dict[str, Any]:
        """将分类对象转换为字典
        
        Args:
            category: 分类对象
            
        Returns:
            分类字典
        """
        return {
            "id": category.id,
            "name": category.name,
            "is_delete": category.is_delete
        }