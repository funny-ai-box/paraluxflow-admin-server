"""RSS Feed爬取脚本存储库"""
import logging
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy.exc import SQLAlchemyError, NoResultFound
from sqlalchemy.orm import Session

from app.infrastructure.database.models.rss import RssFeedCrawlScript
from app.core.exceptions import NotFoundException

logger = logging.getLogger(__name__)


class RssFeedCrawlScriptRepository:
    """RSS Feed爬取脚本存储库"""

    def __init__(self, db_session: Session):
        """初始化存储库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_newest_script(self, feed_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """获取最新脚本
        
        Args:
            feed_id: Feed ID
            
        Returns:
            (错误信息, 脚本信息)
        """
        try:
            # 按创建时间降序排序，获取最新的脚本
            script = (
                self.db.query(RssFeedCrawlScript)
                .filter(RssFeedCrawlScript.feed_id == feed_id)
                .order_by(RssFeedCrawlScript.created_at.desc())
                .first()
            )
            
            if not script:
                return f"未找到Feed ID {feed_id}的脚本，请先创建一个", None
            
            return None, self._script_to_dict(script)
        except SQLAlchemyError as e:
            logger.error(f"获取最新脚本失败, feed_id={feed_id}: {str(e)}")
            return str(e), None

    def get_feed_published_script(self, feed_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """获取Feed的已发布脚本
        
        Args:
            feed_id: Feed ID
            
        Returns:
            (错误信息, 脚本信息)
        """
        try:
            script = (
                self.db.query(RssFeedCrawlScript)
                .filter(
                    RssFeedCrawlScript.feed_id == feed_id,
                    RssFeedCrawlScript.is_published == True
                )
                .order_by(RssFeedCrawlScript.created_at.desc())
                .first()
            )
            
            if not script:
                return f"未找到Feed ID {feed_id}的已发布脚本", None
            
            return None, self._script_to_dict(script)
        except SQLAlchemyError as e:
            logger.error(f"获取已发布脚本失败, feed_id={feed_id}: {str(e)}")
            return str(e), None

    

    def create_script(self, feed_id: str, script: str, is_published: bool = False) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """创建脚本
        
        Args:
            feed_id: Feed ID
            script: 脚本内容
            is_published: 是否发布
            
        Returns:
            (错误信息, 脚本信息)
        """
        try:
            new_script = RssFeedCrawlScript(
                feed_id=feed_id,
                script=script,
                is_published=is_published
            )
            
            self.db.add(new_script)
            self.db.commit()
            self.db.refresh(new_script)
            
            return None, self._script_to_dict(new_script)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建脚本失败, feed_id={feed_id}: {str(e)}")
            return str(e), None

    def publish_script(self, feed_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """发布脚本
        
        Args:
            feed_id: Feed ID
            
        Returns:
            (错误信息, 脚本信息)
        """
        try:
            script = (
                self.db.query(RssFeedCrawlScript)
                .filter(RssFeedCrawlScript.feed_id == feed_id)
                .order_by(RssFeedCrawlScript.created_at.desc())
                .first()
            )
            
            if not script:
                return f"未找到Feed ID {feed_id}的脚本", None
            
            script.is_published = True
            self.db.commit()
            self.db.refresh(script)
            
            return None, self._script_to_dict(script)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"发布脚本失败, feed_id={feed_id}: {str(e)}")
            return str(e), None

    
    def get_feed_scripts(self, feed_id: str) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """获取Feed的所有脚本
        
        Args:
            feed_id: Feed ID
            
        Returns:
            (错误信息, 脚本列表)
        """
        try:
            scripts = (
                self.db.query(RssFeedCrawlScript)
                .filter(RssFeedCrawlScript.feed_id == feed_id)
                .order_by(RssFeedCrawlScript.id.desc())
                .all()
            )
            
            if not scripts:
                return f"未找到Feed ID {feed_id}的脚本", None
            
            return None, [self._script_to_dict(script) for script in scripts]
        except SQLAlchemyError as e:
            logger.error(f"获取Feed脚本列表失败, feed_id={feed_id}: {str(e)}")
            return str(e), None

   
    
    def _script_to_dict(self, script: RssFeedCrawlScript) -> Dict[str, Any]:
        """将脚本对象转换为字典
        
        Args:
            script: 脚本对象
            
        Returns:
            脚本字典
        """
        return {
            "id": script.id,
            "feed_id": script.feed_id,
        
            "script": script.script,
            "is_published": script.is_published,
            "created_at": script.created_at.isoformat() if script.created_at else None,
            "updated_at": script.updated_at.isoformat() if script.updated_at else None,
        }