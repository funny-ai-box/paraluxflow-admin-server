# app/infrastructure/database/repositories/rss_crawler_repository.py
"""RSS爬虫日志仓库"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.rss import RssFeedArticleCrawlLog, RssFeedArticleCrawlBatch

logger = logging.getLogger(__name__)

class RssCrawlerRepository:
    """RSS爬虫日志仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def create_batch(self, batch_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建批次记录
        
        Args:
            batch_data: 批次数据
            
        Returns:
            创建的批次
            
        Raises:
            Exception: 创建失败时抛出异常
        """
        try:
            batch = RssFeedArticleCrawlBatch(**batch_data)
            self.db.add(batch)
            self.db.commit()
            self.db.refresh(batch)
            return self._batch_to_dict(batch)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建爬虫批次失败: {str(e)}")
            raise Exception(f"创建爬虫批次失败: {str(e)}")

    def update_batch(self, batch_id: str, batch_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新批次记录
        
        Args:
            batch_id: 批次ID
            batch_data: 更新数据
            
        Returns:
            更新后的批次
            
        Raises:
            Exception: 更新失败时抛出异常
        """
        try:
            batch = self.db.query(RssFeedArticleCrawlBatch).filter(
                RssFeedArticleCrawlBatch.batch_id == batch_id
            ).first()
            
            if not batch:
                raise Exception(f"未找到批次ID: {batch_id}")
            
            # 更新字段
            for key, value in batch_data.items():
                if hasattr(batch, key):
                    setattr(batch, key, value)
            
            self.db.commit()
            self.db.refresh(batch)
            return self._batch_to_dict(batch)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新爬虫批次失败, ID={batch_id}: {str(e)}")
            raise Exception(f"更新爬虫批次失败: {str(e)}")

    def create_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建日志记录
        
        Args:
            log_data: 日志数据
            
        Returns:
            创建的日志
            
        Raises:
            Exception: 创建失败时抛出异常
        """
        try:
            log = RssFeedArticleCrawlLog(**log_data)
            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)
            return self._log_to_dict(log)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建爬虫日志失败: {str(e)}")
            raise Exception(f"创建爬虫日志失败: {str(e)}")

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """获取批次记录
        
        Args:
            batch_id: 批次ID
            
        Returns:
            批次信息
        """
        try:
            batch = self.db.query(RssFeedArticleCrawlBatch).filter(
                RssFeedArticleCrawlBatch.batch_id == batch_id
            ).first()
            
            if not batch:
                return None
            
            return self._batch_to_dict(batch)
        except SQLAlchemyError as e:
            logger.error(f"获取爬虫批次失败, ID={batch_id}: {str(e)}")
            return None

    def get_logs(self, filters: Dict[str, Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """获取日志列表
        
        Args:
            filters: 筛选条件
            page: 页码
            per_page: 每页数量
            
        Returns:
            日志列表及分页信息
        """
        try:
            query = self.db.query(RssFeedArticleCrawlLog)
            
            # 应用筛选条件
            if filters:
                if "article_id" in filters:
                    query = query.filter(RssFeedArticleCrawlLog.article_id == filters["article_id"])
                
                if "batch_id" in filters:
                    query = query.filter(RssFeedArticleCrawlLog.batch_id == filters["batch_id"])
                
                if "crawler_id" in filters:
                    query = query.filter(RssFeedArticleCrawlLog.crawler_id == filters["crawler_id"])
                
                if "status" in filters:
                    query = query.filter(RssFeedArticleCrawlLog.status == filters["status"])
                
                if "date_range" in filters:
                    start_date, end_date = filters["date_range"]
                    if start_date:
                        query = query.filter(RssFeedArticleCrawlLog.created_at >= start_date)
                    if end_date:
                        query = query.filter(RssFeedArticleCrawlLog.created_at <= end_date)
            
            # 计算总记录数
            total = query.count()
            
            # 应用排序
            query = query.order_by(desc(RssFeedArticleCrawlLog.created_at))
            
            # 应用分页
            logs = query.limit(per_page).offset((page - 1) * per_page).all()
            
            # 计算总页数
            pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            return {
                "list": [self._log_to_dict(log) for log in logs],
                "total": total,
                "pages": pages,
                "current_page": page,
                "per_page": per_page,
                "filters_applied": filters or {}
            }
        except SQLAlchemyError as e:
            logger.error(f"获取爬虫日志失败: {str(e)}")
            return {
                "list": [],
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "filters_applied": filters or {},
                "error": str(e)
            }

    def get_stats(self, time_range: Tuple[datetime, datetime]) -> Dict[str, Any]:
        """获取统计信息
        
        Args:
            time_range: (开始时间, 结束时间)
            
        Returns:
            统计信息
        """
        try:
            start_date, end_date = time_range
            
            # 批次总数
            total_batches = self.db.query(func.count(RssFeedArticleCrawlBatch.id)).filter(
                RssFeedArticleCrawlBatch.started_at >= start_date,
                RssFeedArticleCrawlBatch.started_at <= end_date
            ).scalar()
            
            # 成功批次数
            success_batches = self.db.query(func.count(RssFeedArticleCrawlBatch.id)).filter(
                RssFeedArticleCrawlBatch.started_at >= start_date,
                RssFeedArticleCrawlBatch.started_at <= end_date,
                RssFeedArticleCrawlBatch.final_status == 1
            ).scalar()
            
            # 失败批次数
            failed_batches = self.db.query(func.count(RssFeedArticleCrawlBatch.id)).filter(
                RssFeedArticleCrawlBatch.started_at >= start_date,
                RssFeedArticleCrawlBatch.started_at <= end_date,
                RssFeedArticleCrawlBatch.final_status == 2
            ).scalar()
            
            # 平均处理时间
            avg_processing_time = self.db.query(func.avg(RssFeedArticleCrawlBatch.total_processing_time)).filter(
                RssFeedArticleCrawlBatch.started_at >= start_date,
                RssFeedArticleCrawlBatch.started_at <= end_date,
                RssFeedArticleCrawlBatch.final_status == 1
            ).scalar()
            
            # 爬虫分布
            crawler_stats = self.db.query(
                RssFeedArticleCrawlBatch.crawler_id,
                func.count(RssFeedArticleCrawlBatch.id).label("batch_count"),
                func.avg(RssFeedArticleCrawlBatch.total_processing_time).label("avg_time")
            ).filter(
                RssFeedArticleCrawlBatch.started_at >= start_date,
                RssFeedArticleCrawlBatch.started_at <= end_date
            ).group_by(RssFeedArticleCrawlBatch.crawler_id).all()
            
            crawler_distribution = [
                {
                    "crawler_id": stat[0],
                    "batch_count": stat[1],
                    "avg_processing_time": float(stat[2]) if stat[2] else None
                }
                for stat in crawler_stats
            ]
            
            # 错误类型分布
            error_stats = self.db.query(
                RssFeedArticleCrawlBatch.error_type,
                func.count(RssFeedArticleCrawlBatch.id).label("error_count")
            ).filter(
                RssFeedArticleCrawlBatch.started_at >= start_date,
                RssFeedArticleCrawlBatch.started_at <= end_date,
                RssFeedArticleCrawlBatch.final_status == 2,
                RssFeedArticleCrawlBatch.error_type != None
            ).group_by(RssFeedArticleCrawlBatch.error_type).all()
            
            error_distribution = [
                {
                    "error_type": stat[0] or "unknown",
                    "count": stat[1]
                }
                for stat in error_stats
            ]
            
            return {
                "time_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "total_batches": total_batches,
                "success_batches": success_batches,
                "failed_batches": failed_batches,
                "success_rate": (success_batches / total_batches * 100) if total_batches > 0 else 0,
                "avg_processing_time": float(avg_processing_time) if avg_processing_time else None,
                "crawler_distribution": crawler_distribution,
                "error_distribution": error_distribution
            }
        except SQLAlchemyError as e:
            logger.error(f"获取爬虫统计信息失败: {str(e)}")
            return {
                "error": str(e),
                "time_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            }

    def reset_batch(self, batch_id: str) -> bool:
        """重置批次状态
        
        Args:
            batch_id: 批次ID
            
        Returns:
            是否成功
            
        Raises:
            Exception: 重置失败时抛出异常
        """
        try:
            # 查询批次
            batch = self.db.query(RssFeedArticleCrawlBatch).filter(
                RssFeedArticleCrawlBatch.batch_id == batch_id
            ).first()
            
            if not batch:
                raise Exception(f"未找到批次ID: {batch_id}")
            
            # 删除相关日志
            self.db.query(RssFeedArticleCrawlLog).filter(
                RssFeedArticleCrawlLog.batch_id == batch_id
            ).delete()
            
            # 删除批次
            self.db.delete(batch)
            self.db.commit()
            
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"重置批次状态失败, ID={batch_id}: {str(e)}")
            raise Exception(f"重置批次状态失败: {str(e)}")

    def _batch_to_dict(self, batch: RssFeedArticleCrawlBatch) -> Dict[str, Any]:
        """将批次对象转换为字典
        
        Args:
            batch: 批次对象
            
        Returns:
            批次字典
        """
        return {
            "id": batch.id,
            "batch_id": batch.batch_id,
            "crawler_id": batch.crawler_id,
            "article_id": batch.article_id,
            "feed_id": batch.feed_id,
            "article_url": batch.article_url,
            "final_status": batch.final_status,
            "error_stage": batch.error_stage,
            "error_type": batch.error_type,
            "error_message": batch.error_message,
            "retry_count": batch.retry_count,
            "original_html_length": batch.original_html_length,
            "processed_html_length": batch.processed_html_length,
            "processed_text_length": batch.processed_text_length,
            "content_hash": batch.content_hash,
            "started_at": batch.started_at.isoformat() if batch.started_at else None,
            "ended_at": batch.ended_at.isoformat() if batch.ended_at else None,
            "total_processing_time": batch.total_processing_time,
            "max_memory_usage": batch.max_memory_usage,
            "avg_cpu_usage": batch.avg_cpu_usage,
            "image_count": batch.image_count,
            "link_count": batch.link_count,
            "video_count": batch.video_count,
            "crawler_host": batch.crawler_host,
            "crawler_ip": batch.crawler_ip,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "updated_at": batch.updated_at.isoformat() if batch.updated_at else None
        }

    def _log_to_dict(self, log: RssFeedArticleCrawlLog) -> Dict[str, Any]:
        """将日志对象转换为字典
        
        Args:
            log: 日志对象
            
        Returns:
            日志字典
        """
        return {
            "id": log.id,
            "batch_id": log.batch_id,
            "article_id": log.article_id,
            "feed_id": log.feed_id,
            "article_url": log.article_url,
            "crawler_id": log.crawler_id,
            "status": log.status,
            "stage": log.stage,
            "error_type": log.error_type,
            "error_message": log.error_message,
            "retry_count": log.retry_count,
            "request_started_at": log.request_started_at.isoformat() if log.request_started_at else None,
            "request_ended_at": log.request_ended_at.isoformat() if log.request_ended_at else None,
            "request_duration": log.request_duration,
            "http_status_code": log.http_status_code,
            "response_headers": log.response_headers,
            "original_html_length": log.original_html_length,
            "processed_html_length": log.processed_html_length,
            "processed_text_length": log.processed_text_length,
            "content_hash": log.content_hash,
            "image_count": log.image_count,
            "link_count": log.link_count,
            "video_count": log.video_count,
            "browser_version": log.browser_version,
            "user_agent": log.user_agent,
            "memory_usage": log.memory_usage,
            "cpu_usage": log.cpu_usage,
            "processing_started_at": log.processing_started_at.isoformat() if log.processing_started_at else None,
            "processing_ended_at": log.processing_ended_at.isoformat() if log.processing_ended_at else None,
            "total_processing_time": log.total_processing_time,
            "parsing_time": log.parsing_time,
            "crawler_host": log.crawler_host,
            "crawler_ip": log.crawler_ip,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "updated_at": log.updated_at.isoformat() if log.updated_at else None
        }