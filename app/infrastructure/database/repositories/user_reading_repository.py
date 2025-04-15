# app/infrastructure/database/repositories/user_reading_repository.py
"""用户阅读历史仓库"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, or_, desc, exists, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.user import UserReadingHistory
from app.infrastructure.database.models.rss import RssFeedArticle

logger = logging.getLogger(__name__)

class UserReadingHistoryRepository:
    """用户阅读历史仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session
    
    def get_reading_history(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """获取用户阅读历史
        
        Args:
            user_id: 用户ID
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            阅读历史列表
        """
        try:
            history = self.db.query(UserReadingHistory).filter(
                UserReadingHistory.user_id == user_id
            ).order_by(
                desc(UserReadingHistory.updated_at)
            ).offset(offset).limit(limit).all()
            
            return [self.reading_history_to_dict(item) for item in history]
        except SQLAlchemyError as e:
            logger.error(f"获取阅读历史失败, user_id={user_id}: {str(e)}")
            return []
    
    def get_readings_by_articles(self, user_id: str, article_ids: List[int]) -> List[Dict[str, Any]]:
        """获取用户对指定文章的阅读记录
        
        Args:
            user_id: 用户ID
            article_ids: 文章ID列表
            
        Returns:
            阅读记录列表
        """
        try:
            readings = self.db.query(UserReadingHistory).filter(
                UserReadingHistory.user_id == user_id,
                UserReadingHistory.article_id.in_(article_ids)
            ).all()
            
            return [self.reading_history_to_dict(reading) for reading in readings]
        except SQLAlchemyError as e:
            logger.error(f"获取文章阅读记录失败, user_id={user_id}: {str(e)}")
            return []
    
    def get_reading(self, user_id: str, article_id: int) -> Optional[Dict[str, Any]]:
        """获取用户对指定文章的阅读记录
        
        Args:
            user_id: 用户ID
            article_id: 文章ID
            
        Returns:
            阅读记录或None
        """
        try:
            reading = self.db.query(UserReadingHistory).filter(
                UserReadingHistory.user_id == user_id,
                UserReadingHistory.article_id == article_id
            ).first()
            
            if not reading:
                return None
            
            return self.reading_history_to_dict(reading)
        except SQLAlchemyError as e:
            logger.error(f"获取文章阅读记录失败, user_id={user_id}, article_id={article_id}: {str(e)}")
            return None
    
    def add_reading_record(self, reading_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """添加阅读记录
        
        Args:
            reading_data: 阅读数据
            
        Returns:
            添加的阅读记录对象或None
        """
        try:
            user_id = reading_data.get("user_id")
            article_id = reading_data.get("article_id")
            
            # 检查是否已存在记录
            record = self.db.query(UserReadingHistory).filter(
                UserReadingHistory.user_id == user_id,
                UserReadingHistory.article_id == article_id
            ).first()
            
            if record:
                # 更新现有记录
                for key, value in reading_data.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
            else:
                # 创建新记录
                record = UserReadingHistory(**reading_data)
                self.db.add(record)
                
                # 更新用户的阅读计数
                from app.infrastructure.database.models.user import User
                user = self.db.query(User).filter(User.id == user_id).first()
                if user:
                    user.reading_count = user.reading_count + 1
            
            self.db.commit()
            self.db.refresh(record)
            
            # 如果标记为已读，更新订阅的已读/未读计数
            if reading_data.get("is_read", False):
                self._update_subscription_read_count(user_id, reading_data.get("feed_id"))
            
            return self.reading_history_to_dict(record)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"添加阅读记录失败: {str(e)}")
            return None
    
    def update_reading(self, user_id: str, article_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新阅读记录
        
        Args:
            user_id: 用户ID
            article_id: 文章ID
            update_data: 更新数据
            
        Returns:
            更新后的阅读记录或None
        """
        try:
            reading = self.db.query(UserReadingHistory).filter(
                UserReadingHistory.user_id == user_id,
                UserReadingHistory.article_id == article_id
            ).first()
            
            if not reading:
                return None
            
            # 更新字段
            for key, value in update_data.items():
                if hasattr(reading, key):
                    setattr(reading, key, value)
            
            self.db.commit()
            self.db.refresh(reading)
            return self.reading_history_to_dict(reading)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新阅读记录失败, user_id={user_id}, article_id={article_id}: {str(e)}")
            return None
    
    def toggle_favorite(self, user_id: str, article_id: int) -> Tuple[bool, bool]:
        """切换文章收藏状态
        
        Args:
            user_id: 用户ID
            article_id: 文章ID
            
        Returns:
            (是否成功, 当前是否为收藏状态)
        """
        try:
            record = self.db.query(UserReadingHistory).filter(
                UserReadingHistory.user_id == user_id,
                UserReadingHistory.article_id == article_id
            ).first()
            
            if not record:
                # 获取文章信息
                article = self.db.query(RssFeedArticle).filter(RssFeedArticle.id == article_id).first()
                if not article:
                    return False, False
                
                # 创建新记录
                record = UserReadingHistory(
                    user_id=user_id,
                    article_id=article_id,
                    feed_id=article.feed_id,
                    is_favorite=True
                )
                self.db.add(record)
                is_favorite = True
            else:
                # 切换收藏状态
                record.is_favorite = not record.is_favorite
                is_favorite = record.is_favorite
            
            # 更新用户收藏计数
            from app.infrastructure.database.models.user import User
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                if is_favorite:
                    user.favorite_count = user.favorite_count + 1
                elif user.favorite_count > 0:
                    user.favorite_count = user.favorite_count - 1
            
            self.db.commit()
            return True, is_favorite
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"切换收藏状态失败, user_id={user_id}, article_id={article_id}: {str(e)}")
            return False, False
    
    def get_favorites(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """获取用户收藏文章
        
        Args:
            user_id: 用户ID
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            收藏文章列表
        """
        try:
            favorites = self.db.query(UserReadingHistory).filter(
                UserReadingHistory.user_id == user_id,
                UserReadingHistory.is_favorite == True
            ).order_by(
                desc(UserReadingHistory.updated_at)
            ).offset(offset).limit(limit).all()
            
            return [self.reading_history_to_dict(item) for item in favorites]
        except SQLAlchemyError as e:
            logger.error(f"获取收藏文章失败, user_id={user_id}: {str(e)}")
            return []
    
    def mark_all_read(self, user_id: str, feed_id: Optional[str] = None) -> int:
        """标记全部已读
        
        Args:
            user_id: 用户ID
            feed_id: Feed ID，可选
            
        Returns:
            标记的文章数量
        """
        try:
            # 查询未读的文章
            query = self.db.query(RssFeedArticle).filter(
                RssFeedArticle.status == 1  # 只处理成功抓取的文章
            )
            
            if feed_id:
                query = query.filter(RssFeedArticle.feed_id == feed_id)
            
            # 获取文章ID列表
            articles = query.all()
            article_ids = [article.id for article in articles]
            
            if not article_ids:
                return 0
            
            # 查询已有的阅读记录
            existing_readings = self.db.query(UserReadingHistory).filter(
                UserReadingHistory.user_id == user_id,
                UserReadingHistory.article_id.in_(article_ids)
            ).all()
            
            existing_article_ids = [reading.article_id for reading in existing_readings]
            
            # 更新已有的阅读记录
            for reading in existing_readings:
                reading.is_read = True
            
            # 为没有阅读记录的文章创建新记录
            new_readings = []
            for article_id in article_ids:
                if article_id not in existing_article_ids:
                    # 获取文章对应的Feed ID
                    for article in articles:
                        if article.id == article_id:
                            article_feed_id = article.feed_id
                            break
                    
                    new_reading = UserReadingHistory(
                        user_id=user_id,
                        article_id=article_id,
                        feed_id=article_feed_id,
                        is_read=True
                    )
                    new_readings.append(new_reading)
            
            if new_readings:
                self.db.add_all(new_readings)
            
            # 提交事务
            self.db.commit()
            
            return len(article_ids)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"标记全部已读失败, user_id={user_id}: {str(e)}")
            return 0
    
    def get_unread_count(self, user_id: str, feed_id: Optional[str] = None) -> int:
        """获取未读文章数量
        
        Args:
            user_id: 用户ID
            feed_id: Feed ID，可选
            
        Returns:
            未读文章数量
        """
        try:
            from sqlalchemy import func, and_, exists
            
            # 构建查询
            query = self.db.query(func.count(RssFeedArticle.id)).filter(
                RssFeedArticle.status == 1,  # 只统计成功抓取的文章
                ~exists().where(
                    and_(
                        UserReadingHistory.user_id == user_id,
                        UserReadingHistory.article_id == RssFeedArticle.id,
                        UserReadingHistory.is_read == True
                    )
                )
            )
            
            if feed_id:
                query = query.filter(RssFeedArticle.feed_id == feed_id)
            
            # 执行查询
            count = query.scalar()
            
            return count or 0
        except SQLAlchemyError as e:
            logger.error(f"获取未读数量失败, user_id={user_id}: {str(e)}")
            return 0
    
    def _update_subscription_read_count(self, user_id: str, feed_id: str) -> None:
        """更新订阅的已读/未读计数
        
        Args:
            user_id: 用户ID
            feed_id: Feed ID
        """
        try:
            from app.infrastructure.database.models.user import UserSubscription
            
            subscription = self.db.query(UserSubscription).filter(
                UserSubscription.user_id == user_id,
                UserSubscription.feed_id == feed_id
            ).first()
            
            if subscription:
                subscription.read_count += 1
                subscription.last_read_at = datetime.now()
                self.db.commit()
        except SQLAlchemyError as e:
            logger.error(f"更新订阅计数失败, user_id={user_id}, feed_id={feed_id}: {str(e)}")
    
    def reading_history_to_dict(self, history: UserReadingHistory) -> Dict[str, Any]:
        """将阅读历史对象转为字典
        
        Args:
            history: 阅读历史对象
            
        Returns:
            阅读历史字典
        """
        return {
            "id": history.id,
            "user_id": history.user_id,
            "article_id": history.article_id,
            "feed_id": history.feed_id,
            "is_favorite": history.is_favorite,
            "is_read": history.is_read,
            "read_position": history.read_position,
            "read_progress": history.read_progress,
            "read_time": history.read_time,
            "created_at": history.created_at.isoformat(),
            "updated_at": history.updated_at.isoformat()
        }