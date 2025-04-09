# app/domains/rss/services/sync_service.py
"""RSS源同步服务"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class SyncService:
    """RSS源同步服务，用于批量同步所有可用源的文章"""
    
    def __init__(self, feed_repo, article_service, sync_log_repo=None):
        """初始化同步服务
        
        Args:
            feed_repo: Feed仓库
            article_service: 文章服务
            sync_log_repo: 同步日志仓库 (可选)
        """
        self.feed_repo = feed_repo
        self.article_service = article_service
        self.sync_log_repo = sync_log_repo
    
    def sync_all_active_feeds(self, triggered_by: str = "schedule") -> Dict[str, Any]:
        """同步所有激活状态的Feed
        
        Args:
            triggered_by: 触发方式，可选值: schedule, manual
            
        Returns:
            同步结果
        """
        print(f"===== 开始同步所有激活状态的RSS源 ({triggered_by}) =====")
        # 生成同步ID
        sync_id = str(uuid.uuid4())
        print(f"同步任务ID: {sync_id}")
        
        # 获取所有激活状态的Feed
        active_feeds = self.feed_repo.get_filtered_feeds({"is_active": True}, page=1, per_page=1000)
        total_feeds = len(active_feeds["list"])
        print(f"获取到 {total_feeds} 个激活状态的RSS源")
        
        # 记录开始时间
        start_time = datetime.now()
        print(f"同步开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 初始化结果
        result = {
            "sync_id": sync_id,
            "start_time": start_time.isoformat(),
            "total_feeds": total_feeds,
            "synced_feeds": 0,
            "failed_feeds": 0,
            "total_articles": 0,
            "details": []
        }
        
        # 创建同步日志记录(进行中状态)
        if self.sync_log_repo:
            print("创建同步日志记录...")
            log_data = {
                "sync_id": sync_id,
                "total_feeds": total_feeds,
                "synced_feeds": 0,
                "failed_feeds": 0,
                "total_articles": 0,
                "status": 0,  # 进行中
                "start_time": start_time,
                "triggered_by": triggered_by,
                "details": {"feeds": []}
            }
            err, log = self.sync_log_repo.create_log(log_data)
            if err:
                print(f"警告: 创建同步日志失败: {err}")
        
        # 循环同步每个Feed
        for index, feed in enumerate(active_feeds["list"]):
            feed_id = feed["id"]
            feed_title = feed["title"]
            print(f"\n[{index+1}/{total_feeds}] 正在同步 Feed: {feed_title} (ID: {feed_id})")
            
            feed_result = {
                "feed_id": feed_id,
                "feed_title": feed_title,
                "status": "success",
                "articles_count": 0,
                "error": None,
                "sync_time": None
            }
            
            try:
                # 记录同步开始时间
                feed_sync_start = datetime.now()
                print(f"Feed同步开始时间: {feed_sync_start.strftime('%Y-%m-%d %H:%M:%S')}")
                
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
                
                print(f"Feed同步成功: 新增 {sync_result.get('total', 0)} 篇文章, 耗时 {sync_duration:.2f} 秒")
                
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
                print(f"Feed同步失败: {str(e)}, 耗时 {sync_duration:.2f} 秒")
                logger.error(f"同步Feed {feed_id} 失败: {str(e)}")
            
            # 添加到详情列表
            result["details"].append(feed_result)
            
            # 实时更新同步日志
            if self.sync_log_repo:
                try:
                    current_progress = {
                        "synced_feeds": result["synced_feeds"],
                        "failed_feeds": result["failed_feeds"],
                        "total_articles": result["total_articles"],
                        "details": {"feeds": result["details"]}
                    }
                    self.sync_log_repo.update_log(sync_id, current_progress)
                except Exception as e:
                    print(f"警告: 更新同步日志进度失败: {str(e)}")
        
        # 记录结束时间和总耗时
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        result["end_time"] = end_time.isoformat()
        result["total_time"] = total_time
        
        print(f"\n===== RSS源同步完成 =====")
        print(f"总计: {total_feeds} 个源, 成功: {result['synced_feeds']}, 失败: {result['failed_feeds']}")
        print(f"新增文章: {result['total_articles']} 篇")
        print(f"总耗时: {total_time:.2f} 秒")
        print(f"同步结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 更新最终的同步日志
        if self.sync_log_repo:
            print("更新最终同步日志...")
            final_status = 1  # 成功
            error_message = None
            
            # 如果有失败的Feed，记录简要错误信息
            if result["failed_feeds"] > 0:
                error_feeds = [f"{feed['feed_title']}({feed['feed_id']}): {feed['error']}" 
                              for feed in result["details"] if feed["status"] == "failed"]
                if error_feeds:
                    error_message = f"以下Feed同步失败: {', '.join(error_feeds[:3])}"
                    if len(error_feeds) > 3:
                        error_message += f" 等{len(error_feeds)}个Feed"
            
            # 更新日志
            try:
                self.sync_log_repo.update_log(sync_id, {
                    "synced_feeds": result["synced_feeds"],
                    "failed_feeds": result["failed_feeds"],
                    "total_articles": result["total_articles"],
                    "status": final_status,
                    "end_time": end_time,
                    "total_time": total_time,
                    "details": {"feeds": result["details"]},
                    "error_message": error_message
                })
            except Exception as e:
                print(f"警告: 更新最终同步日志失败: {str(e)}")
        
        return result