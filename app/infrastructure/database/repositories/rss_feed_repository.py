# app/infrastructure/database/repositories/rss_feed_repository.py
"""RSS Feed仓库"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, or_, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.rss import RssFeed, RssFeedCategory

logger = logging.getLogger(__name__)

class RssFeedRepository:
    """RSS Feed仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_feeds_eligible_for_update(self) -> List[Dict[str, Any]]:
        """获取需要更新的Feed列表
        
        Returns:
            符合条件的Feed列表
        """
        try:
            # 获取超过6小时未更新且处于激活状态的Feed
            six_hours_ago = datetime.now() - timedelta(hours=6)
            
            eligible_feeds = self.db.query(RssFeed).filter(
                RssFeed.is_active == True,
                or_(
                    RssFeed.last_successful_fetch_at == None,
                    RssFeed.last_successful_fetch_at < six_hours_ago,
                )
            ).order_by(RssFeed.last_successful_fetch_at).all()
            
            return [self._feed_to_dict(feed) for feed in eligible_feeds]
        except SQLAlchemyError as e:
            logger.error(f"获取需要更新的Feed列表失败: {str(e)}")
            return []

    def get_all_feeds(self) -> List[Dict[str, Any]]:
        """获取所有Feed
        
        Returns:
            所有Feed列表
        """
        try:
            feeds = self.db.query(RssFeed).order_by(desc(RssFeed.created_at)).all()
            return [self._feed_to_dict(feed) for feed in feeds]
        except SQLAlchemyError as e:
            logger.error(f"获取所有Feed失败: {str(e)}")
            return []

    def get_filtered_feeds(self, filters: Dict[str, Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """根据条件筛选Feed，支持分页
        
        Args:
            filters: 筛选条件字典
            page: 页码，从1开始
            per_page: 每页记录数
                
        Returns:
            分页结果，包含列表和分页信息
        """
        try:
            query = self.db.query(RssFeed)
            
            # 应用筛选条件
            if filters:
                if filters.get("title"):
                    query = query.filter(RssFeed.title.like(f"%{filters['title']}%"))
                
                if filters.get("category_id"):
                    query = query.filter(RssFeed.category_id == filters["category_id"])
                    
                if filters.get("url"):
                    query = query.filter(RssFeed.url.like(f"%{filters['url']}%"))
                    
                if filters.get("description"):
                    query = query.filter(RssFeed.description.like(f"%{filters['description']}%"))
                    
                if "is_active" in filters:
                    query = query.filter(RssFeed.is_active == filters["is_active"])
            
            # 计算总记录数
            total = query.count()
            
            # 按ID降序排列
            query = query.order_by(desc(RssFeed.id))
            
            # 应用分页
            feeds = query.limit(per_page).offset((page - 1) * per_page).all()
            
            # 计算总页数
            pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            return {
                "list": [self._feed_to_dict(feed) for feed in feeds],
                "total": total,
                "pages": pages,
                "current_page": page,
                "per_page": per_page
            }
        except SQLAlchemyError as e:
            logger.error(f"筛选Feed失败: {str(e)}")
            return {
                "list": [],
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "error": str(e)
            }

    def get_feed_by_id(self, feed_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """根据ID获取Feed
        
        Args:
            feed_id: Feed ID
            
        Returns:
            (错误信息, Feed信息)
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return f"未找到ID为{feed_id}的Feed", None
            
            return None, self._feed_to_dict(feed)
        except SQLAlchemyError as e:
            logger.error(f"获取Feed失败, ID={feed_id}: {str(e)}")
            return str(e), None

    def add_feed(self, feed_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """添加新Feed
        
        Args:
            feed_data: Feed数据
            
        Returns:
            (错误信息, 新增的Feed信息)
        """
        try:
            new_feed = RssFeed(**feed_data)
            self.db.add(new_feed)
            self.db.commit()
            self.db.refresh(new_feed)
            
            return None, self._feed_to_dict(new_feed)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"添加Feed失败: {str(e)}")
            return str(e), None

    def update_feed(self, feed_id: str, feed_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新Feed信息
        
        Args:
            feed_id: Feed ID
            feed_data: 更新的数据
            
        Returns:
            (错误信息, 更新后的Feed信息)
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return f"未找到ID为{feed_id}的Feed", None
            
            # 更新字段
            for key, value in feed_data.items():
                if hasattr(feed, key):
                    setattr(feed, key, value)
            
            self.db.commit()
            self.db.refresh(feed)
            
            return None, self._feed_to_dict(feed)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新Feed失败, ID={feed_id}: {str(e)}")
            return str(e), None

    def update_feed_status(self, feed_id: str, status: bool) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新Feed状态
        
        Args:
            feed_id: Feed ID
            status: 新状态
            
        Returns:
            (错误信息, 更新后的Feed信息)
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return f"未找到ID为{feed_id}的Feed", None
            
            feed.is_active = status
            self.db.commit()
            self.db.refresh(feed)
            
            return None, self._feed_to_dict(feed)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新Feed状态失败, ID={feed_id}: {str(e)}")
            return str(e), None

    def update_feed_fetch_status(
        self, feed_id: str, status: int, error_message: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新Feed获取状态
        
        Args:
            feed_id: Feed ID
            status: 状态(1=成功, 2=失败)
            error_message: 错误信息
            
        Returns:
            (错误信息, 更新后的Feed信息)
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return f"未找到ID为{feed_id}的Feed", None
            
            current_time = datetime.now()
            feed.last_fetch_at = current_time
            feed.last_fetch_status = status
            
            if status == 1:  # 成功
                feed.last_successful_fetch_at = current_time
                feed.consecutive_failures = 0
                feed.last_fetch_error = None
            else:  # 失败
                feed.consecutive_failures += 1
                feed.last_fetch_error = error_message
            
            self.db.commit()
            self.db.refresh(feed)
            
            return None, self._feed_to_dict(feed)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新Feed获取状态失败, ID={feed_id}: {str(e)}")
            return str(e), None

    def bulk_update_feeds_fetch_time(self, feed_ids: List[str]) -> Optional[str]:
        """批量更新Feed获取时间
        
        Args:
            feed_ids: Feed ID列表
            
        Returns:
            错误信息
        """
        try:
            self.db.query(RssFeed).filter(RssFeed.id.in_(feed_ids)).update(
                {RssFeed.last_fetch_at: datetime.now()},
                synchronize_session=False
            )
            self.db.commit()
            return None
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"批量更新Feed获取时间失败: {str(e)}")
            return str(e)

    def _feed_to_dict(self, feed: RssFeed) -> Dict[str, Any]:
        """将Feed对象转换为字典
        
        Args:
            feed: Feed对象
            
        Returns:
            Feed字典
        """
        return {
            "id": feed.id,
            "url": feed.url,
            "category_id": feed.category_id,
            "logo": feed.logo,
            "title": feed.title,
            "description": feed.description,
            "is_active": feed.is_active,
            "last_fetch_at": feed.last_fetch_at.isoformat() if feed.last_fetch_at else None,
            "last_fetch_status": feed.last_fetch_status,
            "last_fetch_error": feed.last_fetch_error,
            "last_successful_fetch_at": feed.last_successful_fetch_at.isoformat() if feed.last_successful_fetch_at else None,
            "total_articles_count": feed.total_articles_count,
            "consecutive_failures": feed.consecutive_failures,
            "created_at": feed.created_at.isoformat() if feed.created_at else None,
            "updated_at": feed.updated_at.isoformat() if feed.updated_at else None,
        }