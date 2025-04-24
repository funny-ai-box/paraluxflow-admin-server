# app/infrastructure/database/repositories/rss_article_content_repository.py
"""RSS文章内容仓库"""
import logging
from typing import Dict, Optional, Tuple, Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.rss import RssFeedArticleContent

logger = logging.getLogger(__name__)

class RssFeedArticleContentRepository:
    """RSS Feed文章内容仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_article_content(self, content_id: int) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """根据ID获取文章内容
        
        Args:
            content_id: 内容ID
            
        Returns:
            (错误信息, 内容信息)
        """
        try:
            content = self.db.query(RssFeedArticleContent).filter(RssFeedArticleContent.id == content_id).first()
            if not content:
                return f"未找到ID为{content_id}的文章内容", None
            
            return None, self._content_to_dict(content)
        except SQLAlchemyError as e:
            logger.error(f"获取文章内容失败, ID={content_id}: {str(e)}")
            return str(e), None

    def insert_article_content(self, content_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """插入文章内容
        
        Args:
            content_data: 内容数据
            
        Returns:
            (错误信息, 内容信息)
        """
        try:
            new_content = RssFeedArticleContent(**content_data)
            self.db.add(new_content)
            self.db.commit()
            self.db.refresh(new_content)
            
            return None, self._content_to_dict(new_content)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"插入文章内容失败: {str(e)}")
            return str(e), None

    def _content_to_dict(self, content: RssFeedArticleContent) -> Dict[str, Any]:
        """将内容对象转换为字典
        
        Args:
            content: 内容对象
            
        Returns:
            内容字典
        """
        return {
            "id": content.id,
            "html_content": content.html_content,
            "text_content": content.text_content,
            "created_at": content.created_at.isoformat() if content.created_at else None,
            "updated_at": content.updated_at.isoformat() if content.updated_at else None,
        }