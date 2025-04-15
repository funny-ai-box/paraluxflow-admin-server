# app/domains/subscription/services/subscription_service.py
"""订阅管理服务实现"""
import logging
from typing import Dict, List, Any, Optional, Tuple

from app.infrastructure.database.repositories.user_repository import UserSubscriptionRepository, UserFeedGroupRepository
from app.infrastructure.database.repositories.rss_feed_repository import RssFeedRepository

logger = logging.getLogger(__name__)

class SubscriptionService:
    """订阅管理服务"""
    
    def __init__(
        self,
        subscription_repo: UserSubscriptionRepository,
        feed_repo: RssFeedRepository,
        group_repo: Optional[UserFeedGroupRepository] = None
    ):
        """初始化服务
        
        Args:
            subscription_repo: 订阅仓库
            feed_repo: Feed仓库
            group_repo: 分组仓库，可选
        """
        self.subscription_repo = subscription_repo
        self.feed_repo = feed_repo
        self.group_repo = group_repo
    
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
        
        # 获取用户的所有分组
        groups = []
        if self.group_repo:
            groups = self.group_repo.get_user_groups(user_id)
        
        # 按分组组织订阅
        grouped_subscriptions = {}
        
        # 初始化分组
        grouped_subscriptions["无分组"] = []
        for group in groups:
            grouped_subscriptions[group["name"]] = []
        
        # 将订阅分配到相应的分组
        for sub in subscriptions:
            feed_id = sub["feed_id"]
            if feed_id not in feeds:
                continue
            
            # 合并Feed信息
            sub_with_feed = {
                **sub,
                "feed": feeds[feed_id]
            }
            
            # 根据分组ID分配
            group_id = sub["group_id"]
            if group_id is None:
                grouped_subscriptions["无分组"].append(sub_with_feed)
            else:
                # 找到对应的分组名称
                group_name = "无分组"
                for group in groups:
                    if group["id"] == group_id:
                        group_name = group["name"]
                        break
                
                grouped_subscriptions[group_name].append(sub_with_feed)
        
        # 构建结果
        result = {
            "subscriptions": subscriptions,
            "groups": groups,
            "grouped_subscriptions": grouped_subscriptions,
            "feeds": feeds
        }
        
        return result
    
    def add_subscription(self, user_id: str, feed_id: str, group_id: Optional[int] = None) -> Dict[str, Any]:
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
            "group_id": group_id,
            "custom_title": feed.get("title")
        }
        
        # 添加订阅
        subscription = self.subscription_repo.add_subscription(subscription_data)
        if not subscription:
            raise Exception("添加订阅失败")
        
        # 更新分组的Feed计数
        if group_id and self.group_repo:
            group = self.group_repo.update_group(
                group_id,
                user_id,
                {"feed_count": lambda count: count + 1}
            )
        
        return {
            "subscription": subscription,
            "feed": feed
        }
    
    def update_subscription(self, user_id: str, feed_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新订阅
        
        Args:
            user_id: 用户ID
            feed_id: Feed ID
            update_data: 更新数据
            
        Returns:
            更新结果
            
        Raises:
            Exception: 更新失败时抛出异常
        """
        # 如果更新了分组
        old_group_id = None
        new_group_id = None
        
        if "group_id" in update_data and self.group_repo:
            # 获取当前订阅
            current_subscriptions = self.subscription_repo.get_user_subscriptions(user_id)
            for sub in current_subscriptions:
                if sub["feed_id"] == feed_id:
                    old_group_id = sub["group_id"]
                    break
            
            new_group_id = update_data["group_id"]
        
        # 更新订阅
        subscription = self.subscription_repo.update_subscription(user_id, feed_id, update_data)
        if not subscription:
            raise Exception("更新订阅失败")
        
        # 更新分组的Feed计数
        if old_group_id != new_group_id and self.group_repo:
            # 减少旧分组的计数
            if old_group_id:
                self.group_repo.update_group(
                    old_group_id,
                    user_id,
                    {"feed_count": lambda count: max(0, count - 1)}
                )
            
            # 增加新分组的计数
            if new_group_id:
                self.group_repo.update_group(
                    new_group_id,
                    user_id,
                    {"feed_count": lambda count: count + 1}
                )
        
        # 获取Feed详情
        err, feed = self.feed_repo.get_feed_by_id(feed_id)
        
        return {
            "subscription": subscription,
            "feed": feed if not err else None
        }
    
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
        # 获取当前订阅的分组信息
        group_id = None
        if self.group_repo:
            current_subscriptions = self.subscription_repo.get_user_subscriptions(user_id)
            for sub in current_subscriptions:
                if sub["feed_id"] == feed_id:
                    group_id = sub["group_id"]
                    break
        
        # 移除订阅
        success = self.subscription_repo.remove_subscription(user_id, feed_id)
        if not success:
            raise Exception("移除订阅失败")
        
        # 更新分组的Feed计数
        if group_id and self.group_repo:
            self.group_repo.update_group(
                group_id,
                user_id,
                {"feed_count": lambda count: max(0, count - 1)}
            )
        
        return {"success": True}
    
    def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的分组
        
        Args:
            user_id: 用户ID
            
        Returns:
            分组列表
        """
        if not self.group_repo:
            return []
        
        return self.group_repo.get_user_groups(user_id)
    
    def add_group(self, user_id: str, name: str) -> Dict[str, Any]:
        """添加分组
        
        Args:
            user_id: 用户ID
            name: 分组名称
            
        Returns:
            添加结果
            
        Raises:
            Exception: 添加失败时抛出异常
        """
        if not self.group_repo:
            raise Exception("分组功能未启用")
        
        group_data = {
            "user_id": user_id,
            "name": name
        }
        
        group = self.group_repo.add_group(group_data)
        if not group:
            raise Exception("添加分组失败")
        
        return group
    
    def update_group(self, user_id: str, group_id: int, name: str) -> Dict[str, Any]:
        """更新分组
        
        Args:
            user_id: 用户ID
            group_id: 分组ID
            name: 新名称
            
        Returns:
            更新结果
            
        Raises:
            Exception: 更新失败时抛出异常
        """
        if not self.group_repo:
            raise Exception("分组功能未启用")
        
        group = self.group_repo.update_group(group_id, user_id, {"name": name})
        if not group:
            raise Exception("更新分组失败")
        
        return group
    
    def delete_group(self, user_id: str, group_id: int) -> Dict[str, Any]:
        """删除分组
        
        Args:
            user_id: 用户ID
            group_id: 分组ID
            
        Returns:
            删除结果
            
        Raises:
            Exception: 删除失败时抛出异常
        """
        if not self.group_repo:
            raise Exception("分组功能未启用")
        
        success = self.group_repo.delete_group(group_id, user_id)
        if not success:
            raise Exception("删除分组失败")
        
        return {"success": True}