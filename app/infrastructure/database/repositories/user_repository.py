# app/infrastructure/database/repositories/user_repository.py
"""用户仓库"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, func, or_, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.user import User, UserSubscription, UserReadingHistory

logger = logging.getLogger(__name__)

class UserRepository:
    """用户仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def find_by_google_id(self, google_id: str) -> Optional[User]:
        """根据Google ID查找用户
        
        Args:
            google_id: Google ID
            
        Returns:
            用户对象或None
        """
        try:
            return self.db.query(User).filter(User.google_id == google_id).first()
        except SQLAlchemyError as e:
            logger.error(f"根据Google ID查找用户失败, google_id={google_id}: {str(e)}")
            return None
    
    def find_by_email(self, email: str) -> Optional[User]:
        """根据邮箱查找用户
        
        Args:
            email: 邮箱
            
        Returns:
            用户对象或None
        """
        try:
            return self.db.query(User).filter(User.email == email).first()
        except SQLAlchemyError as e:
            logger.error(f"根据邮箱查找用户失败, email={email}: {str(e)}")
            return None
    
    def find_by_id(self, user_id: str) -> Optional[User]:
        """根据ID查找用户
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户对象或None
        """
        try:
            return self.db.query(User).filter(User.id == user_id).first()
        except SQLAlchemyError as e:
            logger.error(f"根据ID查找用户失败, user_id={user_id}: {str(e)}")
            return None
    
    def create_user(self, user_data: Dict[str, Any]) -> Optional[User]:
        """创建用户
        
        Args:
            user_data: 用户数据
            
        Returns:
            创建的用户对象或None
        """
        try:
            user = User(**user_data)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建用户失败: {str(e)}")
            return None
    
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Optional[User]:
        """更新用户信息
        
        Args:
            user_id: 用户ID
            user_data: 更新数据
            
        Returns:
            更新后的用户对象或None
        """
        try:
            user = self.find_by_id(user_id)
            if not user:
                return None
            
            for key, value in user_data.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            self.db.commit()
            self.db.refresh(user)
            return user
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新用户失败, user_id={user_id}: {str(e)}")
            return None
    
    def update_login_time(self, user_id: str) -> bool:
        """更新用户登录时间
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否成功
        """
        try:
            user = self.find_by_id(user_id)
            if not user:
                return False
            
            user.last_login_at = datetime.now()
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新用户登录时间失败, user_id={user_id}: {str(e)}")
            return False
    
    def user_to_dict(self, user: User) -> Dict[str, Any]:
        """将用户对象转为字典
        
        Args:
            user: 用户对象
            
        Returns:
            用户字典
        """
        return {
            "id": user.id,
            "google_id": user.google_id,
            "email": user.email,
            "username": user.username,
            "avatar_url": user.avatar_url,
            "status": user.status,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,

            "subscription_count": user.subscription_count,
            "reading_count": user.reading_count,
            "favorite_count": user.favorite_count,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat()
        }

class UserSubscriptionRepository:
    """用户订阅仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_subscription(self, user_id: str, feed_id: str) -> Optional[UserSubscription]:
        """获取订阅
        
        Args:
            user_id: 用户ID
            feed_id: Feed ID
            
        Returns:
            订阅对象或None
        """
        try:
            return self.db.query(UserSubscription).filter(
                UserSubscription.user_id == user_id,
                UserSubscription.feed_id == feed_id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"获取订阅失败, user_id={user_id}, feed_id={feed_id}: {str(e)}")
            return None
    
    def get_user_subscriptions(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有订阅
        
        Args:
            user_id: 用户ID
            group_id: 分组ID，可选
            
        Returns:
            订阅列表
        """
        try:
            query = self.db.query(UserSubscription).filter(UserSubscription.user_id == user_id)
            
        
            
            subscriptions = query.all()
            return [self.subscription_to_dict(sub) for sub in subscriptions]
        except SQLAlchemyError as e:
            logger.error(f"获取用户订阅失败, user_id={user_id}: {str(e)}")
            return []
    
    def add_subscription(self, subscription_data: Dict[str, Any]) -> Optional[UserSubscription]:
        """添加订阅
        
        Args:
            subscription_data: 订阅数据
            
        Returns:
            添加的订阅对象或None
        """
        try:
            # 检查是否已订阅
            user_id = subscription_data.get("user_id")
            feed_id = subscription_data.get("feed_id")
            
            existing = self.db.query(UserSubscription).filter(
                UserSubscription.user_id == user_id,
                UserSubscription.feed_id == feed_id
            ).first()
            
            if existing:
                return existing
            
            subscription = UserSubscription(**subscription_data)
            self.db.add(subscription)
            self.db.commit()
            self.db.refresh(subscription)
            
            # 更新用户的订阅计数
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                user.subscription_count = user.subscription_count + 1
                self.db.commit()
            
            return subscription
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"添加订阅失败: {str(e)}")
            return None
    
    def remove_subscription(self, user_id: str, feed_id: str) -> bool:
        """移除订阅
        
        Args:
            user_id: 用户ID
            feed_id: Feed ID
            
        Returns:
            是否成功
        """
        try:
            subscription = self.db.query(UserSubscription).filter(
                UserSubscription.user_id == user_id,
                UserSubscription.feed_id == feed_id
            ).first()
            
            if not subscription:
                return False
            
            self.db.delete(subscription)
            self.db.commit()
            
            # 更新用户的订阅计数
            user = self.db.query(User).filter(User.id == user_id).first()
            if user and user.subscription_count > 0:
                user.subscription_count = user.subscription_count - 1
                self.db.commit()
            
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"移除订阅失败, user_id={user_id}, feed_id={feed_id}: {str(e)}")
            return False
    
    def update_subscription(self, user_id: str, feed_id: str, update_data: Dict[str, Any]) -> Optional[UserSubscription]:
        """更新订阅信息
        
        Args:
            user_id: 用户ID
            feed_id: Feed ID
            update_data: 更新数据
            
        Returns:
            更新后的订阅对象或None
        """
        try:
            subscription = self.db.query(UserSubscription).filter(
                UserSubscription.user_id == user_id,
                UserSubscription.feed_id == feed_id
            ).first()
            
            if not subscription:
                return None
            
            for key, value in update_data.items():
                if hasattr(subscription, key):
                    setattr(subscription, key, value)
            
            self.db.commit()
            self.db.refresh(subscription)
            return subscription
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新订阅失败, user_id={user_id}, feed_id={feed_id}: {str(e)}")
            return None
    
    def subscription_to_dict(self, subscription: UserSubscription) -> Dict[str, Any]:
        """将订阅对象转为字典
        
        Args:
            subscription: 订阅对象
            
        Returns:
            订阅字典
        """
        return {
            "id": subscription.id,
            "user_id": subscription.user_id,
            "feed_id": subscription.feed_id,
            "group_id": subscription.group_id,
            "is_favorite": subscription.is_favorite,
            "custom_title": subscription.custom_title,
            "read_count": subscription.read_count,
            "unread_count": subscription.unread_count,
            "last_read_at": subscription.last_read_at.isoformat() if subscription.last_read_at else None,
            "created_at": subscription.created_at.isoformat(),
            "updated_at": subscription.updated_at.isoformat()
        }

class UserReadingHistoryRepository:
    """用户阅读历史仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session
    
    def get_reading(self, user_id: str, article_id: int) -> Optional[UserReadingHistory]:
        """获取用户阅读记录
        
        Args:
            user_id: 用户ID
            article_id: 文章ID
            
        Returns:
            阅读记录对象或None
        """
        try:
            return self.db.query(UserReadingHistory).filter(
                UserReadingHistory.user_id == user_id,
                UserReadingHistory.article_id == article_id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"获取阅读记录失败, user_id={user_id}, article_id={article_id}: {str(e)}")
            return None
        
    def update_reading(self, user_id: str, article_id: int, update_data: Dict[str, Any]) -> Optional[UserReadingHistory]:
        """更新用户阅读记录
        
        Args:
            user_id: 用户ID
            article_id: 文章ID
            update_data: 更新数据
            
        Returns:
            更新后的阅读记录对象或None
        """
        try:
            reading = self.db.query(UserReadingHistory).filter(
                UserReadingHistory.user_id == user_id,
                UserReadingHistory.article_id == article_id
            ).first()
            
            if not reading:
                return None
            
            for key, value in update_data.items():
                if hasattr(reading, key):
                    setattr(reading, key, value)
            
            self.db.commit()
            self.db.refresh(reading)
            return reading
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新阅读记录失败, user_id={user_id}, article_id={article_id}: {str(e)}")
            return None
        
    def get_unread_count(self, user_id: str, feed_ids: Optional[List[str]] = None) -> int:
        """获取未读数量"""
        try:
            query = self.db.query(func.count(UserReadingHistory.id)).filter(
                UserReadingHistory.user_id == user_id,
                UserReadingHistory.is_read == False
            )
            if feed_ids:
                query = query.filter(UserReadingHistory.feed_id.in_(feed_ids))
            return query.scalar()
        except SQLAlchemyError as e:
            logger.error(f"获取未读数量失败, user_id={user_id}: {str(e)}")
            return 0
        
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
        
    def get_article_ids_by_status(self, filter_criteria: Dict[str, Any]) -> List[int]:
        """根据指定状态获取文章ID列表
        
        Args:
            filter_criteria: 过滤条件，例如：
                - user_id: 用户ID
                - is_favorite: 是否收藏
                - is_read: 是否已读
        
        Returns:
            符合条件的文章ID列表
        """
        try:
            query = self.db.query(UserReadingHistory.article_id)

            # 应用过滤条件
            if "user_id" in filter_criteria:
                query = query.filter(UserReadingHistory.user_id == filter_criteria["user_id"])

            # 根据传入的键值对进行过滤
            if "is_favorite" in filter_criteria:
                query = query.filter(UserReadingHistory.is_favorite == filter_criteria["is_favorite"])
            if "is_read" in filter_criteria:
                query = query.filter(UserReadingHistory.is_read == filter_criteria["is_read"])
            # 可以根据需要添加其他过滤条件

            article_ids = query.all()
            return [article_id[0] for article_id in article_ids]
        except SQLAlchemyError as e:
            logger.error(f"根据状态获取文章ID失败: {str(e)}")
            return []
        
    def get_read_article_ids_from_list(self, user_id: str, article_ids: List[int]) -> List[int]:
        """从给定的文章ID列表中获取用户已读的文章ID
        
        Args:
            user_id: 用户ID
            article_ids: 要检查的文章ID列表
            
        Returns:
            用户已读的文章ID列表
        """
        try:
            if not article_ids:
                return []
                
            read_ids = self.db.query(UserReadingHistory.article_id).filter(
                UserReadingHistory.user_id == user_id,
                UserReadingHistory.article_id.in_(article_ids),
                UserReadingHistory.is_read == True
            ).all()
            
            return [article_id[0] for article_id in read_ids]
            
        except SQLAlchemyError as e:
            logger.error(f"获取已读文章ID失败, user_id={user_id}: {str(e)}")
            return []
                

    
    def add_reading_record(self, reading_data: Dict[str, Any]) -> Optional[UserReadingHistory]:
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
                user = self.db.query(User).filter(User.id == user_id).first()
                if user:
                    user.reading_count = user.reading_count + 1
            
            self.db.commit()
            self.db.refresh(record)
            
            # 如果标记为已读，更新订阅的已读/未读计数
            if reading_data.get("is_read", False):
                self._update_subscription_read_count(user_id, reading_data.get("feed_id"))
            
            return record
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"添加阅读记录失败: {str(e)}")
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
                return False, False
            
            # 切换收藏状态
            record.is_favorite = not record.is_favorite
            
            # 更新用户收藏计数
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                if record.is_favorite:
                    user.favorite_count = user.favorite_count + 1
                elif user.favorite_count > 0:
                    user.favorite_count = user.favorite_count - 1
            
            self.db.commit()
            return True, record.is_favorite
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
    
    def _update_subscription_read_count(self, user_id: str, feed_id: str) -> None:
        """更新订阅的已读/未读计数
        
        Args:
            user_id: 用户ID
            feed_id: Feed ID
        """
        try:
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
