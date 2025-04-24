# app/domains/subscription/services/subscription_service.py
"""订阅管理服务实现"""
import logging
from typing import Dict, List, Any, Optional, Tuple

from app.infrastructure.database.repositories.user_repository import UserSubscriptionRepository
from app.infrastructure.database.repositories.rss.rss_feed_repository import RssFeedRepository

logger = logging.getLogger(__name__)

class SubscriptionService:
    """订阅管理服务"""
    
    def __init__(
        self,
        subscription_repo: UserSubscriptionRepository,
        feed_repo: RssFeedRepository,

    ):
        """初始化服务
        
        Args:
            subscription_repo: 订阅仓库
            feed_repo: Feed仓库
            group_repo: 分组仓库，可选
        """
        self.subscription_repo = subscription_repo
        self.feed_repo = feed_repo
      
    def get_user_subscriptions(self, user_id: str) -> Dict[str, Any]:
        """获取用户的所有订阅，包括Feed详情和分组信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            订阅数据
        """
        # 获取用户的所有订阅
        subscriptions = self.subscription_repo.get_user_subscriptions(user_id)
        
        # 获取所有相关的Feed ID
        feed_ids = [sub["feed_id"] for sub in subscriptions]
        
        # 获取Feed详情
        feeds = {}
        for feed_id in feed_ids:
            err, feed = self.feed_repo.get_feed_by_id(feed_id)
            if not err and feed:
                feeds[feed_id] = feed
        
   
      

        
        # 构建结果
        result = {
            "subscriptions": subscriptions,

            "feeds": feeds
        }
        
        return result
    
    def add_subscription(self, user_id: str, feed_id: str) -> Dict[str, Any]:
        """添加订阅
        
        Args:
            user_id: 用户ID
            feed_id: Feed ID
            group_id: 分组ID，可选
            
        Returns:
            添加结果
            
        Raises:
            Exception: 添加失败时抛出异常
        """
        # 检查Feed是否存在
        err, feed = self.feed_repo.get_feed_by_id(feed_id)
        if err:
            raise Exception(f"获取Feed失败: {err}")
        
        # 构建订阅数据
        subscription_data = {
            "user_id": user_id,
            "feed_id": feed_id,

            "custom_title": feed.get("title")
        }
        
        # 添加订阅
        subscription = self.subscription_repo.add_subscription(subscription_data)
        if not subscription:
            raise Exception("添加订阅失败")
        

        return subscription
    
    
    
    def remove_subscription(self, user_id: str, feed_id: str) -> Dict[str, Any]:
        """移除订阅
        
        Args:
            user_id: 用户ID
            feed_id: Feed ID
            
        Returns:
            移除结果
            
        Raises:
            Exception: 移除失败时抛出异常
        """
      
        
        # 移除订阅
        success = self.subscription_repo.remove_subscription(user_id, feed_id)
        if not success:
            raise Exception("移除订阅失败")
     
        return {"success": True}
