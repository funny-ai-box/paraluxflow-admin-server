# app/domains/user/services/profile_service.py
"""用户资料服务实现"""
import logging
from typing import Dict, Any, Optional

from app.infrastructure.database.repositories.user_repository import UserRepository
from app.infrastructure.database.repositories.user_repository import UserReadingHistoryRepository
from app.infrastructure.database.repositories.user_repository import UserSubscriptionRepository

logger = logging.getLogger(__name__)

class ProfileService:
    """用户资料服务"""
    
    def __init__(
        self,
        user_repo: UserRepository,
        reading_history_repo: Optional[UserReadingHistoryRepository] = None,
        subscription_repo: Optional[UserSubscriptionRepository] = None
    ):
        """初始化服务
        
        Args:
            user_repo: 用户仓库
            reading_history_repo: 阅读历史仓库，可选
            subscription_repo: 订阅仓库，可选
        """
        self.user_repo = user_repo
        self.reading_history_repo = reading_history_repo
        self.subscription_repo = subscription_repo
    
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """获取用户资料
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户资料
            
        Raises:
            Exception: 获取失败时抛出异常
        """
        # 获取用户信息
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise Exception("用户不存在")
        
        # 获取统计信息
        stats = {
            "subscription_count": user.subscription_count,
            "reading_count": user.reading_count,
            "favorite_count": user.favorite_count
        }
        
        # 构建结果
        result = {
            "user": self.user_repo.user_to_dict(user),
            "stats": stats
        }
        
        return result
    
    def update_user_profile(self, user_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新用户资料
        
        Args:
            user_id: 用户ID
            update_data: 更新数据
            
        Returns:
            更新后的用户资料
            
        Raises:
            Exception: 更新失败时抛出异常
        """
        # 允许更新的字段
        allowed_fields = ["username", "avatar_url", "preferences"]
        
        # 过滤数据
        filtered_data = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        if not filtered_data:
            raise Exception("没有可更新的字段")
        
        # 更新用户
        user = self.user_repo.update_user(user_id, filtered_data)
        if not user:
            raise Exception("更新用户资料失败")
        
        return self.user_repo.user_to_dict(user)
    
    def get_reading_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户阅读统计
        
        Args:
            user_id: 用户ID
            
        Returns:
            阅读统计
        """
        if not self.reading_history_repo:
            return {}
        
        # 获取用户信息
        user = self.user_repo.find_by_id(user_id)
        if not user:
            return {}
        
        # 构建统计信息
        stats = {
            "total_read": user.reading_count,
            "favorites": user.favorite_count
            # 可以添加更多统计信息
        }
        
        return stats