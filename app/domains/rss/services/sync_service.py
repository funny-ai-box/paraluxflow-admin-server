# app/domains/rss/services/sync_service.py
"""RSS源同步服务"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class SyncService:
    """RSS源同步服务，用于批量同步所有可用源的文章"""
    
    def __init__(self, feed_repo, article_service):
        """初始化同步服务
        
        Args:
            feed_repo: Feed仓库
            article_service: 文章服务
        """
        self.feed_repo = feed_repo
        self.article_service = article_service
    
    def sync_all_active_feeds(self) -> Dict[str, Any]:
        """同步所有激活状态的Feed
        
        Returns:
            同步结果
        """
        # 获取所有激活状态的Feed
        active_feeds = self.feed_repo.get_filtered_feeds({"is_active": True}, page=1, per_page=1000)
        
        # 记录开始时间
        start_time = datetime.now()
        
        # 初始化结果
        result = {
            "start_time": start_time.isoformat(),
            "total_feeds": len(active_feeds["list"]),
            "synced_feeds": 0,
            "failed_feeds": 0,
            "total_articles": 0,
            "details": []
        }
        
        # 循环同步每个Feed
        for feed in active_feeds["list"]:
            feed_id = feed["id"]
            feed_result = {
                "feed_id": feed_id,
                "feed_title": feed["title"],
                "status": "success",
                "articles_count": 0,
                "error": None,
                "sync_time": None
            }
            
            try:
                # 记录同步开始时间
                feed_sync_start = datetime.now()
                
                # 同步Feed文章
                sync_result = self.article_service.sync_feed_articles(feed_id)
                
                # 计算同步耗时
                feed_sync_end = datetime.now()
                sync_duration = (feed_sync_end - feed_sync_start).total_seconds()
                
                # 更新Feed结果
                feed_result["status"] = "success"
                feed_result["articles_count"] = sync_result.get("total", 0)
                feed_result["sync_time"] = sync_duration
                
                # 更新总结果
                result["synced_feeds"] += 1
                result["total_articles"] += sync_result.get("total", 0)
                
            except Exception as e:
                # 记录同步结束时间
                feed_sync_end = datetime.now()
                sync_duration = (feed_sync_end - feed_sync_start).total_seconds()
                
                # 更新Feed结果
                feed_result["status"] = "failed"
                feed_result["error"] = str(e)
                feed_result["sync_time"] = sync_duration
                
                # 更新总结果
                result["failed_feeds"] += 1
                
                # 记录错误日志
                logger.error(f"同步Feed {feed_id} 失败: {str(e)}")
            
            # 添加到详情列表
            result["details"].append(feed_result)
        
        # 记录结束时间和总耗时
        end_time = datetime.now()
        result["end_time"] = end_time.isoformat()
        result["total_time"] = (end_time - start_time).total_seconds()
        
        return result