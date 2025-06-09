# app/infrastructure/database/repositories/rss_sync_log_repository.py
"""RSS同步日志仓库"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.rss import RssSyncLog

logger = logging.getLogger(__name__)

class RssSyncLogRepository:
    """RSS同步日志仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def create_log(self, log_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """创建同步日志
        
        Args:
            log_data: 日志数据
            
        Returns:
            (错误信息, 创建的日志)
        """
        try:
            new_log = RssSyncLog(**log_data)
            self.db.add(new_log)
            self.db.commit()
            self.db.refresh(new_log)
            
            return None, self._log_to_dict(new_log)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建同步日志失败: {str(e)}")
            return str(e), None

    def update_log(self, sync_id: str, log_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新同步日志
        
        Args:
            sync_id: 同步ID
            log_data: 更新数据
            
        Returns:
            (错误信息, 更新后的日志)
        """
        try:
            log = self.db.query(RssSyncLog).filter(RssSyncLog.sync_id == sync_id).first()
            if not log:
                return f"未找到同步ID为{sync_id}的日志", None
            
            # 更新字段
            for key, value in log_data.items():
                if hasattr(log, key):
                    setattr(log, key, value)
            
            self.db.commit()
            self.db.refresh(log)
            
            return None, self._log_to_dict(log)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新同步日志失败, ID={sync_id}: {str(e)}")
            return str(e), None

    def get_log_by_id(self, log_id: int) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """根据ID获取日志
        
        Args:
            log_id: 日志ID
            
        Returns:
            (错误信息, 日志信息)
        """
        try:
            log = self.db.query(RssSyncLog).filter(RssSyncLog.id == log_id).first()
            if not log:
                return f"未找到ID为{log_id}的同步日志", None
            
            return None, self._log_to_dict(log)
        except SQLAlchemyError as e:
            logger.error(f"获取同步日志失败, ID={log_id}: {str(e)}")
            return str(e), None

    def get_log_by_sync_id(self, sync_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """根据同步ID获取日志
        
        Args:
            sync_id: 同步ID
            
        Returns:
            (错误信息, 日志信息)
        """
        try:
            log = self.db.query(RssSyncLog).filter(RssSyncLog.sync_id == sync_id).first()
            if not log:
                return f"未找到同步ID为{sync_id}的日志", None
            
            return None, self._log_to_dict(log)
        except SQLAlchemyError as e:
            logger.error(f"获取同步日志失败, 同步ID={sync_id}: {str(e)}")
            return str(e), None

    def get_logs(self, page: int = 1, per_page: int = 20, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取日志列表
        
        Args:
            page: 页码
            per_page: 每页数量
            filters: 筛选条件
            
        Returns:
            分页的日志列表
        """
        try:
            query = self.db.query(RssSyncLog)
            
            if filters:
                # 应用状态筛选
                if "status" in filters:
                    query = query.filter(RssSyncLog.status == filters["status"])
                
                # 应用触发方式筛选
                if "triggered_by" in filters:
                    query = query.filter(RssSyncLog.triggered_by == filters["triggered_by"])
                
                # 应用日期范围筛选
                if "date_range" in filters and filters["date_range"]:
                    start_date, end_date = filters["date_range"]
                    if start_date:
                        query = query.filter(RssSyncLog.start_time >= start_date)
                    if end_date:
                        query = query.filter(RssSyncLog.start_time <= end_date)
            
            # 按创建时间降序排序
            query = query.order_by(desc(RssSyncLog.created_at))
            
            # 计算总记录数
            total = query.count()
            
            # 应用分页
            logs = query.limit(per_page).offset((page - 1) * per_page).all()
            logs_dict = [self._log_to_dict(log) for log in logs]
            
            # 计算总页数
            pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            return {
                "list": logs_dict,
                "total": total,
                "pages": pages,
                "current_page": page,
                "per_page": per_page,
                "filters_applied": filters or {}
            }
        except SQLAlchemyError as e:
            logger.error(f"获取同步日志列表失败: {str(e)}")
            return {
                "list": [],
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "filters_applied": filters or {},
                "error": str(e)
            }
        
    def create_single_feed_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建单个Feed的同步日志记录
        
        Args:
            log_data: 日志数据
            
        Returns:
            创建的日志记录
        """
        try:
            # 创建日志记录
            log = RssSyncLog(
                sync_id=log_data["sync_id"],
                total_feeds=1,  # 单个Feed
                synced_feeds=1 if log_data["status"] == 1 else 0,
                failed_feeds=1 if log_data["status"] == 2 else 0,
                total_articles=log_data.get("new_articles", 0),
                status=log_data["status"],
                start_time=log_data["started_at"],
                end_time=log_data["ended_at"],
                total_time=log_data.get("total_time"),
                triggered_by=log_data.get("triggered_by", "crawler"),
                error_message=log_data.get("error_message"),
                details={
                    "type": "single_feed",
                    "feed_id": log_data["feed_id"],
                    "crawler_id": log_data["crawler_id"],
                    "feed_url": log_data.get("feed_url"),
                    "response_status": log_data.get("response_status"),
                    "content_length": log_data.get("content_length"),
                    "entries_found": log_data.get("entries_found"),
                    "fetch_time": log_data.get("fetch_time"),
                    "parse_time": log_data.get("parse_time"),
                    "performance": log_data.get("details", {})
                }
            )
            
            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)
            
            return self._log_to_dict(log)
        except Exception as e:
            logger.error(f"创建Feed同步日志失败: {str(e)}")
            self.db.rollback()
            return {}

    def count_recent_successful_syncs(self, hours: int = 24) -> int:
        """统计最近成功的同步数量
        
        Args:
            hours: 时间范围（小时）
            
        Returns:
            成功同步数量
        """
        try:
            since_time = datetime.now() - timedelta(hours=hours)
            return self.db.query(RssSyncLog).filter(
                RssSyncLog.status == 1,
                RssSyncLog.start_time >= since_time
            ).count()
        except Exception as e:
            logger.error(f"统计成功同步数量失败: {str(e)}")
            return 0

    def count_recent_failed_syncs(self, hours: int = 24) -> int:
        """统计最近失败的同步数量
        
        Args:
            hours: 时间范围（小时）
            
        Returns:
            失败同步数量
        """
        try:
            since_time = datetime.now() - timedelta(hours=hours)
            return self.db.query(RssSyncLog).filter(
                RssSyncLog.status == 2,
                RssSyncLog.start_time >= since_time
            ).count()
        except Exception as e:
            logger.error(f"统计失败同步数量失败: {str(e)}")
            return 0

    def get_feed_sync_history(self, feed_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取特定Feed的同步历史
        
        Args:
            feed_id: Feed ID
            limit: 返回数量限制
            
        Returns:
            同步历史列表
        """
        try:
            logs = self.db.query(RssSyncLog).filter(
                RssSyncLog.details.contains(f'"feed_id": "{feed_id}"')
            ).order_by(
                RssSyncLog.start_time.desc()
            ).limit(limit).all()
            
            return [self._log_to_dict(log) for log in logs]
        except Exception as e:
            logger.error(f"获取Feed同步历史失败: {str(e)}")
            return []

    def _log_to_dict(self, log: RssSyncLog) -> Dict[str, Any]:
        """将日志对象转换为字典
        
        Args:
            log: 日志对象
            
        Returns:
            日志字典
        """
        return {
            "id": log.id,
            "sync_id": log.sync_id,
            "total_feeds": log.total_feeds,
            "synced_feeds": log.synced_feeds,
            "failed_feeds": log.failed_feeds,
            "total_articles": log.total_articles,
            "status": log.status,
            "start_time": log.start_time.isoformat() if log.start_time else None,
            "end_time": log.end_time.isoformat() if log.end_time else None,
            "total_time": log.total_time,
            "details": log.details,
            "error_message": log.error_message,
            "triggered_by": log.triggered_by,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "updated_at": log.updated_at.isoformat() if log.updated_at else None
        }