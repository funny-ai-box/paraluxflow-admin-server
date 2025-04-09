# app/infrastructure/database/repositories/rss_crawler_repository.py
"""RSS爬虫日志仓库"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, or_, desc, func,cast, Date, case
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
    def analyze_crawler_performance(self, filters: Dict[str, Any], group_by: str = "feed") -> Dict[str, Any]:
        """分析爬虫性能和成功/失败情况
        
        Args:
            filters: 筛选条件
            group_by: 分组方式，可选值：feed(按源分组)、date(按日期分组)、crawler(按爬虫分组)
            
        Returns:
            分析结果
        """
        try:

            
            # 基础查询：批次数据
            base_query = self.db.query(RssFeedArticleCrawlBatch)
            
            # 应用筛选条件
            if filters:
                if "feed_id" in filters:
                    base_query = base_query.filter(
                        RssFeedArticleCrawlBatch.feed_id == filters["feed_id"]
                    )
                
                if "date_range" in filters:
                    start_date, end_date = filters["date_range"]
                    if start_date:
                        base_query = base_query.filter(
                            RssFeedArticleCrawlBatch.started_at >= start_date
                        )
                    if end_date:
                        base_query = base_query.filter(
                            RssFeedArticleCrawlBatch.started_at <= end_date
                        )
            
            # 总批次数
            total_batches = base_query.count()
            
            # 成功批次数
            success_batches = base_query.filter(
                RssFeedArticleCrawlBatch.final_status == 1
            ).count()
            
            # 失败批次数
            failed_batches = base_query.filter(
                RssFeedArticleCrawlBatch.final_status == 2
            ).count()
            
            # 平均处理时间
            avg_processing_time = self.db.query(
                func.avg(RssFeedArticleCrawlBatch.total_processing_time)
            ).select_from(RssFeedArticleCrawlBatch).scalar()
            
            # 根据分组方式获取详细分析
            items = []
            
            if group_by == "feed":
                # 按源分组分析
                group_stats = self.db.query(
                    RssFeedArticleCrawlBatch.feed_id,
                    func.count(RssFeedArticleCrawlBatch.id).label("total"),
                    func.sum(
                        case([(RssFeedArticleCrawlBatch.final_status == 1, 1)], else_=0)
                    ).label("success"),
                    func.sum(
                        case([(RssFeedArticleCrawlBatch.final_status == 2, 1)], else_=0)
                    ).label("failed"),
                    func.avg(RssFeedArticleCrawlBatch.total_processing_time).label("avg_time")
                ).group_by(
                    RssFeedArticleCrawlBatch.feed_id
                ).all()
                
                for stat in group_stats:
                    success_rate = (stat.success / stat.total * 100) if stat.total > 0 else 0
                    items.append({
                        "feed_id": stat.feed_id,
                        "total_batches": stat.total,
                        "success_batches": stat.success,
                        "failed_batches": stat.failed,
                        "success_rate": round(success_rate, 2),
                        "avg_processing_time": float(stat.avg_time) if stat.avg_time else None
                    })
            
            elif group_by == "date":
                # 按日期分组分析
                group_stats = self.db.query(
                    cast(RssFeedArticleCrawlBatch.started_at, Date).label("date"),
                    func.count(RssFeedArticleCrawlBatch.id).label("total"),
                    func.sum(
                        case([(RssFeedArticleCrawlBatch.final_status == 1, 1)], else_=0)
                    ).label("success"),
                    func.sum(
                        case([(RssFeedArticleCrawlBatch.final_status == 2, 1)], else_=0)
                    ).label("failed"),
                    func.avg(RssFeedArticleCrawlBatch.total_processing_time).label("avg_time")
                ).group_by(
                    cast(RssFeedArticleCrawlBatch.started_at, Date)
                ).order_by(
                    cast(RssFeedArticleCrawlBatch.started_at, Date).desc()
                ).all()
                
                for stat in group_stats:
                    success_rate = (stat.success / stat.total * 100) if stat.total > 0 else 0
                    items.append({
                        "date": stat.date.isoformat() if stat.date else None,
                        "total_batches": stat.total,
                        "success_batches": stat.success,
                        "failed_batches": stat.failed,
                        "success_rate": round(success_rate, 2),
                        "avg_processing_time": float(stat.avg_time) if stat.avg_time else None
                    })
            
            elif group_by == "crawler":
                # 按爬虫分组分析
                group_stats = self.db.query(
                    RssFeedArticleCrawlBatch.crawler_id,
                    func.count(RssFeedArticleCrawlBatch.id).label("total"),
                    func.sum(
                        case([(RssFeedArticleCrawlBatch.final_status == 1, 1)], else_=0)
                    ).label("success"),
                    func.sum(
                        case([(RssFeedArticleCrawlBatch.final_status == 2, 1)], else_=0)
                    ).label("failed"),
                    func.avg(RssFeedArticleCrawlBatch.total_processing_time).label("avg_time")
                ).group_by(
                    RssFeedArticleCrawlBatch.crawler_id
                ).all()
                
                for stat in group_stats:
                    success_rate = (stat.success / stat.total * 100) if stat.total > 0 else 0
                    items.append({
                        "crawler_id": stat.crawler_id,
                        "total_batches": stat.total,
                        "success_batches": stat.success,
                        "failed_batches": stat.failed,
                        "success_rate": round(success_rate, 2),
                        "avg_processing_time": float(stat.avg_time) if stat.avg_time else None
                    })
            
            # 按成功率排序
            items.sort(key=lambda x: x.get("success_rate", 0), reverse=True)
            
            return {
                "total_batches": total_batches,
                "success_batches": success_batches,
                "failed_batches": failed_batches,
                "overall_success_rate": round((success_batches / total_batches * 100) if total_batches > 0 else 0, 2),
                "avg_processing_time": float(avg_processing_time) if avg_processing_time else None,
                "group_by": group_by,
                "items": items
            }
        except SQLAlchemyError as e:
            logger.error(f"分析爬虫性能失败: {str(e)}")
            return {
                "error": str(e),
                "total_batches": 0,
                "success_batches": 0,
                "failed_batches": 0,
                "overall_success_rate": 0,
                "items": []
            }

    def analyze_crawler_errors(self, filters: Dict[str, Any], limit: int = 10) -> Dict[str, Any]:
        """分析爬虫错误类型和分布
        
        Args:
            filters: 筛选条件
            limit: 返回的错误类型数量限制
            
        Returns:
            错误分析结果
        """
        try:
            from sqlalchemy import func, and_, distinct
            
            # 基础查询：错误日志
            base_query = self.db.query(RssFeedArticleCrawlBatch).filter(
                RssFeedArticleCrawlBatch.final_status == 2,  # 只分析失败的批次
                RssFeedArticleCrawlBatch.error_message != None  # 确保有错误信息
            )
            
            # 应用筛选条件
            if filters:
                if "feed_id" in filters:
                    base_query = base_query.filter(
                        RssFeedArticleCrawlBatch.feed_id == filters["feed_id"]
                    )
                
                if "date_range" in filters:
                    start_date, end_date = filters["date_range"]
                    if start_date:
                        base_query = base_query.filter(
                            RssFeedArticleCrawlBatch.started_at >= start_date
                        )
                    if end_date:
                        base_query = base_query.filter(
                            RssFeedArticleCrawlBatch.started_at <= end_date
                        )
            
            # 获取总失败次数
            total_errors = base_query.count()
            
            # 按错误类型分组统计
            error_type_stats = self.db.query(
                RssFeedArticleCrawlBatch.error_type,
                func.count(RssFeedArticleCrawlBatch.id).label("count")
            ).filter(
                RssFeedArticleCrawlBatch.final_status == 2,
                RssFeedArticleCrawlBatch.error_type != None
            ).group_by(
                RssFeedArticleCrawlBatch.error_type
            ).order_by(
                func.count(RssFeedArticleCrawlBatch.id).desc()
            ).limit(limit).all()
            
            error_types = []
            for stat in error_type_stats:
                percentage = (stat.count / total_errors * 100) if total_errors > 0 else 0
                error_types.append({
                    "error_type": stat.error_type or "未知错误类型",
                    "count": stat.count,
                    "percentage": round(percentage, 2)
                })
            
            # 按错误阶段分组统计
            error_stage_stats = self.db.query(
                RssFeedArticleCrawlBatch.error_stage,
                func.count(RssFeedArticleCrawlBatch.id).label("count")
            ).filter(
                RssFeedArticleCrawlBatch.final_status == 2,
                RssFeedArticleCrawlBatch.error_stage != None
            ).group_by(
                RssFeedArticleCrawlBatch.error_stage
            ).order_by(
                func.count(RssFeedArticleCrawlBatch.id).desc()
            ).all()
            
            error_stages = []
            for stat in error_stage_stats:
                percentage = (stat.count / total_errors * 100) if total_errors > 0 else 0
                error_stages.append({
                    "error_stage": stat.error_stage or "未知错误阶段",
                    "count": stat.count,
                    "percentage": round(percentage, 2)
                })
            
            # 获取失败频率最高的源
            feed_error_stats = self.db.query(
                RssFeedArticleCrawlBatch.feed_id,
                func.count(RssFeedArticleCrawlBatch.id).label("error_count")
            ).filter(
                RssFeedArticleCrawlBatch.final_status == 2
            ).group_by(
                RssFeedArticleCrawlBatch.feed_id
            ).order_by(
                func.count(RssFeedArticleCrawlBatch.id).desc()
            ).limit(5).all()
            
            top_error_feeds = []
            for stat in feed_error_stats:
                percentage = (stat.error_count / total_errors * 100) if total_errors > 0 else 0
                top_error_feeds.append({
                    "feed_id": stat.feed_id,
                    "error_count": stat.error_count,
                    "percentage": round(percentage, 2)
                })
            
            # 获取常见错误消息样本
            common_errors = self.db.query(
                RssFeedArticleCrawlBatch.error_message,
                func.count(RssFeedArticleCrawlBatch.id).label("count")
            ).filter(
                RssFeedArticleCrawlBatch.final_status == 2,
                RssFeedArticleCrawlBatch.error_message != None
            ).group_by(
                RssFeedArticleCrawlBatch.error_message
            ).order_by(
                func.count(RssFeedArticleCrawlBatch.id).desc()
            ).limit(5).all()
            
            error_messages = []
            for err in common_errors:
                percentage = (err.count / total_errors * 100) if total_errors > 0 else 0
                # 截断过长的错误消息
                error_message = err.error_message
                if error_message and len(error_message) > 100:
                    error_message = error_message[:100] + "..."
                    
                error_messages.append({
                    "error_message": error_message,
                    "count": err.count,
                    "percentage": round(percentage, 2)
                })
            
            return {
                "total_errors": total_errors,
                "error_types": error_types,
                "error_stages": error_stages,
                "top_error_feeds": top_error_feeds,
                "common_error_messages": error_messages
            }
        except SQLAlchemyError as e:
            logger.error(f"分析爬虫错误失败: {str(e)}")
            return {
                "error": str(e),
                "total_errors": 0,
                "error_types": [],
                "error_stages": [],
                "top_error_feeds": [],
                "common_error_messages": []
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