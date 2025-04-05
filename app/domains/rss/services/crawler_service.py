# app/domains/rss/services/crawler_service.py
"""爬虫管理服务实现"""
import uuid
import logging
import socket
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

class CrawlerService:
    """爬虫管理服务，处理RSS文章内容的分布式抓取"""
    
    def __init__(self, article_repo, content_repo, crawler_repo, script_repo):
        """初始化爬虫服务
        
        Args:
            article_repo: 文章仓库
            content_repo: 内容仓库
            crawler_repo: 爬虫日志仓库
            script_repo: 脚本仓库
        """
        self.article_repo = article_repo
        self.content_repo = content_repo
        self.crawler_repo = crawler_repo
        self.script_repo = script_repo
    
    def get_pending_articles(self, limit: int = 10, crawler_id: str = None) -> List[Dict[str, Any]]:
        """获取待抓取的文章
        
        Args:
            limit: 获取数量
            crawler_id: 爬虫标识
            
        Returns:
            待抓取文章列表
        """
        # 获取待抓取文章
        articles = self.article_repo.get_pending_articles(limit)
        
        # 获取Feed对应的脚本
        feed_scripts = {}
        for article in articles:
            feed_id = article["feed_id"]
            if feed_id not in feed_scripts:
                err, script = self.script_repo.get_feed_published_script(feed_id)
                if not err and script:
                    feed_scripts[feed_id] = script["script"]
                else:
                    feed_scripts[feed_id] = None
            
            # 添加脚本到文章
            article["script"] = feed_scripts.get(feed_id)
        
        return articles
    
    def claim_article(self, article_id: int, crawler_id: str) -> Dict[str, Any]:
        """认领(锁定)文章进行抓取
        
        Args:
            article_id: 文章ID
            crawler_id: 爬虫标识
            
        Returns:
            认领结果
            
        Raises:
            Exception: 认领失败时抛出异常
        """
        # 锁定文章
        err, article = self.article_repo.lock_article(article_id, crawler_id)
        if err:
            raise Exception(f"锁定文章失败: {err}")
        
        # 获取文章的Feed对应的脚本
        feed_id = article["feed_id"]
        err, script = self.script_repo.get_feed_published_script(feed_id)
        
        # 添加脚本到认领结果
        article["script"] = script["script"] if not err and script else None
        
        return article
    
    def submit_crawl_result(self, article_id: int, crawler_id: str, batch_id: str, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """提交抓取结果
        
        Args:
            article_id: 文章ID
            crawler_id: 爬虫标识
            batch_id: 批次ID
            result_data: 结果数据
            
        Returns:
            提交结果
            
        Raises:
            Exception: 提交失败时抛出异常
        """
        # 检验必要字段
        if "status" not in result_data:
            raise Exception("缺少status字段")
        
        status = result_data["status"]
        
        # 获取文章信息
        err, article = self.article_repo.get_article_by_id(article_id)
        if err:
            raise Exception(f"获取文章失败: {err}")
        
        # 检查是否由正确的爬虫提交
        if article["crawler_id"] != crawler_id:
            raise Exception(f"文章被其他爬虫锁定: {article['crawler_id']}")
        
        # 处理成功结果
        content_id = None
        if status == 1:  # 成功
            # 确保包含内容
            if "html_content" not in result_data or "text_content" not in result_data:
                raise Exception("成功状态必须提供html_content和text_content")
            
            # 保存内容
            err, content = self.content_repo.insert_article_content({
                "html_content": result_data["html_content"],
                "text_content": result_data["text_content"]
            })
            
            if err:
                raise Exception(f"保存文章内容失败: {err}")
            
            content_id = content["id"]
        
        # 更新文章状态
        err, updated_article = self.article_repo.update_article_status(
            article_id=article_id,
            status=1 if status == 1 else 2,  # 1=成功, 2=失败
            content_id=content_id,
            error_message=result_data.get("error_message")
        )
        
        if err:
            raise Exception(f"更新文章状态失败: {err}")
        
        # 记录日志
        current_time = datetime.now()
        
        # 构建批次数据
        batch_data = {
            "batch_id": batch_id,
            "crawler_id": crawler_id,
            "article_id": article_id,
            "feed_id": article["feed_id"],
            "article_url": article["link"],
            "final_status": status,
            "started_at": current_time - timedelta(seconds=result_data.get("processing_time", 0)),
            "ended_at": current_time,
            "total_processing_time": result_data.get("processing_time"),
            "error_message": result_data.get("error_message"),
            "error_type": result_data.get("error_type"),
            "error_stage": result_data.get("error_stage"),
            "original_html_length": len(result_data.get("html_content", "")) if status == 1 else None,
            "processed_html_length": len(result_data.get("html_content", "")) if status == 1 else None,
            "processed_text_length": len(result_data.get("text_content", "")) if status == 1 else None,
            "content_hash": None,  # 可以添加内容哈希值
            "image_count": result_data.get("image_count"),
            "link_count": result_data.get("link_count"),
            "video_count": result_data.get("video_count"),
            "crawler_host": result_data.get("crawler_host", socket.gethostname()),
            "crawler_ip": result_data.get("crawler_ip"),
            "max_memory_usage": result_data.get("memory_usage"),
            "avg_cpu_usage": result_data.get("cpu_usage")
        }
        
        # 创建批次记录
        batch = self.crawler_repo.create_batch(batch_data)
        
        # 构建日志数据
        log_data = {
            "batch_id": batch_id,
            "article_id": article_id,
            "feed_id": article["feed_id"],
            "article_url": article["link"],
            "crawler_id": crawler_id,
            "status": status,
            "stage": result_data.get("stage", "complete"),
            "error_type": result_data.get("error_type"),
            "error_message": result_data.get("error_message"),
            "retry_count": article["retry_count"],
            "request_started_at": current_time - timedelta(seconds=result_data.get("request_time", 0)),
            "request_ended_at": current_time,
            "request_duration": result_data.get("request_time"),
            "http_status_code": result_data.get("http_status"),
            "response_headers": result_data.get("response_headers"),
            "original_html_length": len(result_data.get("html_content", "")) if status == 1 else None,
            "processed_html_length": len(result_data.get("html_content", "")) if status == 1 else None,
            "processed_text_length": len(result_data.get("text_content", "")) if status == 1 else None,
            "content_hash": None,  # 可以添加内容哈希值
            "image_count": result_data.get("image_count"),
            "link_count": result_data.get("link_count"),
            "video_count": result_data.get("video_count"),
            "browser_version": result_data.get("browser_version"),
            "user_agent": result_data.get("user_agent"),
            "memory_usage": result_data.get("memory_usage"),
            "cpu_usage": result_data.get("cpu_usage"),
            "processing_started_at": current_time - timedelta(seconds=result_data.get("processing_time", 0)),
            "processing_ended_at": current_time,
            "total_processing_time": result_data.get("processing_time"),
            "parsing_time": result_data.get("parsing_time"),
            "crawler_host": result_data.get("crawler_host", socket.gethostname()),
            "crawler_ip": result_data.get("crawler_ip"),
            "script_version": result_data.get("script_version"),
            "network_type": result_data.get("network_type"),
            "content_encoding": result_data.get("content_encoding"),
            "script_execution_time": result_data.get("script_execution_time"),
            "error_stack_trace": result_data.get("error_stack_trace"),
            "crawler_version": result_data.get("crawler_version")
        }
        
        # 创建日志记录
        log = self.crawler_repo.create_log(log_data)
        
        return {
            "message": "提交成功",
            "status": status,
            "content_id": content_id,
            "batch_id": batch_id
        }
    
    def get_crawl_logs(self, filters: Dict[str, Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """获取抓取日志
        
        Args:
            filters: 筛选条件
            page: 页码
            per_page: 每页数量
            
        Returns:
            日志列表及分页信息
        """
        return self.crawler_repo.get_logs(filters, page, per_page)
    
    def get_crawler_stats(self, time_range: str = "today") -> Dict[str, Any]:
        """获取爬虫统计信息
        
        Args:
            time_range: 时间范围，可选：today, yesterday, last7days, last30days
            
        Returns:
            统计信息
        """
        # 转换时间范围为开始和结束时间
        now = datetime.now()
        if time_range == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif time_range == "yesterday":
            start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == "last7days":
            start_date = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif time_range == "last30days":
            start_date = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        else:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        
        return self.crawler_repo.get_stats((start_date, end_date))
    
    def reset_batch(self, batch_id: str) -> Dict[str, Any]:
        """重置批次状态
        
        Args:
            batch_id: 批次ID
            
        Returns:
            重置结果
            
        Raises:
            Exception: 重置失败时抛出异常
        """
        # 获取批次信息
        batch = self.crawler_repo.get_batch(batch_id)
        if not batch:
            raise Exception(f"未找到批次ID: {batch_id}")
        
        # 重置批次和相关文章
        self.crawler_repo.reset_batch(batch_id)
        
        # 重置文章状态
        err, article = self.article_repo.reset_article(batch["article_id"])
        if err:
            raise Exception(f"重置文章状态失败: {err}")
        
        return {
            "message": "重置成功",
            "batch_id": batch_id,
            "article_id": batch["article_id"]
        }