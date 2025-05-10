# app/domains/hot_topics/services/hot_topic_platform_service.py
"""热点平台服务实现"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional


from app.infrastructure.database.repositories.hot_topic_repository import HotTopicPlatformRepository, HotTopicRepository

logger = logging.getLogger(__name__)

class HotTopicPlatformService:
    """热点平台服务"""
    
    def __init__(self, platform_repo: HotTopicPlatformRepository, topic_repo: HotTopicRepository):
        """初始化服务
        
        Args:
            platform_repo: 平台仓库
            topic_repo: 热点仓库
        """
        self.platform_repo = platform_repo
        self.topic_repo = topic_repo
    
    def get_platforms(self, only_active: bool = True) -> List[Dict[str, Any]]:
        """获取热点平台列表
        
        Args:
            only_active: 是否只返回激活的平台
            
        Returns:
            平台列表
        """
        return self.platform_repo.get_all_platforms(only_active)
    
    def get_platform_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """根据标识码获取平台详情
        
        Args:
            code: 平台标识码
            
        Returns:
            平台详情
        """
        return self.platform_repo.get_platform_by_code(code)
    
    def get_platform_topics(self, platform_code: str, limit: int = 50, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取指定平台的热点话题
        
        Args:
            platform_code: 平台标识码
            limit: 返回数量限制
            date_str: 指定日期 (YYYY-MM-DD), 不指定则获取最新
            
        Returns:
            该平台的热点话题列表
            
        Raises:
            Exception: 平台不存在或其他错误时抛出
        """
        # 检查平台是否存在
        platform = self.platform_repo.get_platform_by_code(platform_code)
        if not platform:
            raise Exception(f"平台 {platform_code} 不存在")
        
        # 解析日期
        topic_date = None
        if date_str:
            try:
                topic_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise Exception("无效的日期格式，应为YYYY-MM-DD")
                
        # 获取热点
        topics = self.topic_repo.get_latest_hot_topics(platform_code, limit, topic_date)
        
        # 补充平台名称
        for topic in topics:
            topic["platform_name"] = platform.get("name", "未知平台")
            topic["platform_icon"] = platform.get("icon", "")
            
        return topics
    
    def get_all_platforms_topics(self, limit_per_platform: int = 10) -> Dict[str, Any]:
        """获取所有平台的热点话题
        
        Args:
            limit_per_platform: 每个平台返回的话题数量
            
        Returns:
            所有平台的热点话题 { platform_code: [...topics] }
        """
        # 获取激活平台
        platforms = self.platform_repo.get_all_platforms(only_active=True)
        
        result = {}
        for platform in platforms:
            platform_code = platform.get("code")
            try:
                topics = self.get_platform_topics(platform_code, limit_per_platform)
                result[platform_code] = {
                    "platform": platform,
                    "topics": topics
                }
            except Exception as e:
                logger.error(f"获取平台 {platform_code} 的热点失败: {str(e)}")
                result[platform_code] = {
                    "platform": platform,
                    "topics": [],
                    "error": str(e)
                }
                
        return result