# app/infrastructure/database/repositories/hot_topic_repository.py
"""热点话题仓库"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.hot_topics import HotTopicTask, HotTopic, HotTopicLog

logger = logging.getLogger(__name__)

class HotTopicTaskRepository:
    """热点任务仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def create_task(self, task_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """创建热点爬取任务
        
        Args:
            task_data: 任务数据
            
        Returns:
            (错误信息, 创建的任务)
        """
        try:
            new_task = HotTopicTask(**task_data)
            self.db.add(new_task)
            self.db.commit()
            self.db.refresh(new_task)
            
            return None, self._task_to_dict(new_task)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建热点爬取任务失败: {str(e)}")
            return str(e), None

    def update_task(self, task_id: str, update_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新热点爬取任务
        
        Args:
            task_id: 任务ID
            update_data: 更新数据
            
        Returns:
            (错误信息, 更新后的任务)
        """
        try:
            task = self.db.query(HotTopicTask).filter(HotTopicTask.task_id == task_id).first()
            if not task:
                return f"未找到任务ID为{task_id}的任务", None
            
            # 更新字段
            for key, value in update_data.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            
            self.db.commit()
            self.db.refresh(task)
            
            return None, self._task_to_dict(task)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新热点爬取任务失败, ID={task_id}: {str(e)}")
            return str(e), None

    def get_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取待爬取的任务
        
        Args:
            limit: 获取数量
            
        Returns:
            待爬取任务列表
        """
        try:
            tasks = self.db.query(HotTopicTask).filter(
                HotTopicTask.status == 0,  # 待爬取
                or_(
                    HotTopicTask.scheduled_time == None,
                    HotTopicTask.scheduled_time <= datetime.now()
                )
            ).order_by(
                HotTopicTask.created_at
            ).limit(limit).all()
            
            return [self._task_to_dict(task) for task in tasks]
        except SQLAlchemyError as e:
            logger.error(f"获取待爬取任务失败: {str(e)}")
            return []

    def claim_task(self, task_id: str, crawler_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """认领任务
        
        Args:
            task_id: 任务ID
            crawler_id: 爬虫标识
            
        Returns:
            (错误信息, 认领的任务)
        """
        try:
            task = self.db.query(HotTopicTask).filter(
                HotTopicTask.task_id == task_id,
                HotTopicTask.status == 0  # 待爬取
            ).first()
            
            if not task:
                return "任务不存在或已被其他爬虫认领", None
            
            # 更新任务状态
            task.status = 1  # 爬取中
            task.crawler_id = crawler_id
            
            self.db.commit()
            self.db.refresh(task)
            
            return None, self._task_to_dict(task)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"认领任务失败, ID={task_id}: {str(e)}")
            return str(e), None

    def get_tasks(self, filters: Dict[str, Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """获取任务列表
        
        Args:
            filters: 筛选条件
            page: 页码
            per_page: 每页数量
            
        Returns:
            分页的任务列表
        """
        try:
            query = self.db.query(HotTopicTask)
            
            # 应用筛选条件
            if filters:
                # 状态筛选
                if "status" in filters:
                    query = query.filter(HotTopicTask.status == filters["status"])
                
                # 平台筛选
                if "platform" in filters:
                    query = query.filter(HotTopicTask.platforms.contains(f'"{filters["platform"]}"'))
                
                # 触发类型筛选
                if "trigger_type" in filters:
                    query = query.filter(HotTopicTask.trigger_type == filters["trigger_type"])
                
                # 日期范围筛选
                if "date_range" in filters and filters["date_range"]:
                    start_date, end_date = filters["date_range"]
                    if start_date:
                        query = query.filter(HotTopicTask.created_at >= start_date)
                    if end_date:
                        query = query.filter(HotTopicTask.created_at <= end_date)
            
            # 计算总记录数
            total = query.count()
            
            # 应用排序和分页
            tasks = query.order_by(desc(HotTopicTask.created_at)).limit(per_page).offset((page - 1) * per_page).all()
            
            # 计算总页数
            pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            return {
                "list": [self._task_to_dict(task) for task in tasks],
                "total": total,
                "pages": pages,
                "current_page": page,
                "per_page": per_page
            }
        except SQLAlchemyError as e:
            logger.error(f"获取任务列表失败: {str(e)}")
            return {
                "list": [],
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "error": str(e)
            }

    def _task_to_dict(self, task: HotTopicTask) -> Dict[str, Any]:
        """将任务对象转换为字典
        
        Args:
            task: 任务对象
            
        Returns:
            任务字典
        """
        return {
            "id": task.task_id,
            "status": task.status,
            "platforms": task.platforms,
            "scheduled_time": task.scheduled_time.isoformat() if task.scheduled_time else None,
            "crawler_id": task.crawler_id,
            "trigger_type": task.trigger_type,
            "triggered_by": task.triggered_by,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None
        }


class HotTopicRepository:
    """热点仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def create_topics(self, topics_data: List[Dict[str, Any]]) -> bool:
        """批量创建热点话题
        
        Args:
            topics_data: 话题数据列表
            
        Returns:
            是否成功
        """
        try:
            # 批量插入热点话题
            for data in topics_data:
                topic = HotTopic(**data)
                self.db.add(topic)
            
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"批量创建热点话题失败: {str(e)}")
            return False

    def get_topics(self, filters: Dict[str, Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """获取热点话题列表
        
        Args:
            filters: 筛选条件
            page: 页码
            per_page: 每页数量
            
        Returns:
            分页的热点话题列表
        """
        try:
            query = self.db.query(HotTopic)
            
            # 应用筛选条件
            if filters:
                # 平台筛选
                if "platform" in filters:
                    query = query.filter(HotTopic.platform == filters["platform"])
                
                # 任务ID筛选
                if "task_id" in filters:
                    query = query.filter(HotTopic.task_id == filters["task_id"])
                
                # 批次ID筛选
                if "batch_id" in filters:
                    query = query.filter(HotTopic.batch_id == filters["batch_id"])
                
                # 标题关键词搜索
                if "keyword" in filters and filters["keyword"]:
                    query = query.filter(HotTopic.topic_title.like(f"%{filters['keyword']}%"))
                
                # 日期范围筛选
                if "date_range" in filters and filters["date_range"]:
                    start_date, end_date = filters["date_range"]
                    if start_date:
                        query = query.filter(HotTopic.created_at >= start_date)
                    if end_date:
                        query = query.filter(HotTopic.created_at <= end_date)
            
            # 计算总记录数
            total = query.count()
            
            # 应用排序和分页
            topics = query.order_by(desc(HotTopic.created_at)).limit(per_page).offset((page - 1) * per_page).all()
            
            # 计算总页数
            pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            return {
                "list": [self._topic_to_dict(topic) for topic in topics],
                "total": total,
                "pages": pages,
                "current_page": page,
                "per_page": per_page
            }
        except SQLAlchemyError as e:
            logger.error(f"获取热点话题列表失败: {str(e)}")
            return {
                "list": [],
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "error": str(e)
            }

    def get_latest_hot_topics(self, platform: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最新热点话题
        
        Args:
            platform: 平台筛选
            limit: 获取数量
            
        Returns:
            最新热点话题列表
        """
        try:
            # 获取最新任务ID
            latest_task_query = self.db.query(
                HotTopicTask.task_id
            ).filter(
                HotTopicTask.status == 2  # 已完成
            ).order_by(
                desc(HotTopicTask.created_at)
            ).limit(1)
            
            latest_task_id = latest_task_query.scalar()
            
            if not latest_task_id:
                return []
            
            # 获取最新热点
            query = self.db.query(HotTopic).filter(
                HotTopic.task_id == latest_task_id,
                HotTopic.status == 1  # 有效
            )
            
            if platform:
                query = query.filter(HotTopic.platform == platform)
            
            topics = query.order_by(
                HotTopic.platform,
                HotTopic.rank if HotTopic.rank is not None else 9999
            ).limit(limit).all()
            
            return [self._topic_to_dict(topic) for topic in topics]
        except SQLAlchemyError as e:
            logger.error(f"获取最新热点话题失败: {str(e)}")
            return []

    def _topic_to_dict(self, topic: HotTopic) -> Dict[str, Any]:
        """将话题对象转换为字典
        
        Args:
            topic: 话题对象
            
        Returns:
            话题字典
        """
        return {
            "id": topic.id,
            "task_id": topic.task_id,
            "batch_id": topic.batch_id,
            "platform": topic.platform,
            "topic_title": topic.topic_title,
            "topic_url": topic.topic_url,
            "hot_value": topic.hot_value,
            "topic_description": topic.topic_description,
            "is_hot": topic.is_hot,
            "is_new": topic.is_new,
            "rank": topic.rank,
            "rank_change": topic.rank_change,
            "heat_level": topic.heat_level,
            "crawler_id": topic.crawler_id,
            "crawl_time": topic.crawl_time.isoformat() if topic.crawl_time else None,
            "status": topic.status,
            "created_at": topic.created_at.isoformat() if topic.created_at else None,
            "updated_at": topic.updated_at.isoformat() if topic.updated_at else None
        }


class HotTopicLogRepository:
    """热点爬取日志仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def create_log(self, log_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """创建爬取日志
        
        Args:
            log_data: 日志数据
            
        Returns:
            (错误信息, 创建的日志)
        """
        try:
            new_log = HotTopicLog(**log_data)
            self.db.add(new_log)
            self.db.commit()
            self.db.refresh(new_log)
            
            return None, self._log_to_dict(new_log)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建热点爬取日志失败: {str(e)}")
            return str(e), None

    def get_logs(self, filters: Dict[str, Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """获取日志列表
        
        Args:
            filters: 筛选条件
            page: 页码
            per_page: 每页数量
            
        Returns:
            分页的日志列表
        """
        try:
            query = self.db.query(HotTopicLog)
            
            # 应用筛选条件
            if filters:
                # 平台筛选
                if "platform" in filters:
                    query = query.filter(HotTopicLog.platform == filters["platform"])
                
                # 任务ID筛选
                if "task_id" in filters:
                    query = query.filter(HotTopicLog.task_id == filters["task_id"])
                
                # 批次ID筛选
                if "batch_id" in filters:
                    query = query.filter(HotTopicLog.batch_id == filters["batch_id"])
                
                # 状态筛选
                if "status" in filters:
                    query = query.filter(HotTopicLog.status == filters["status"])
                
                # 日期范围筛选
                if "date_range" in filters and filters["date_range"]:
                    start_date, end_date = filters["date_range"]
                    if start_date:
                        query = query.filter(HotTopicLog.created_at >= start_date)
                    if end_date:
                        query = query.filter(HotTopicLog.created_at <= end_date)
            
            # 计算总记录数
            total = query.count()
            
            # 应用排序和分页
            logs = query.order_by(desc(HotTopicLog.created_at)).limit(per_page).offset((page - 1) * per_page).all()
            
            # 计算总页数
            pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            return {
                "list": [self._log_to_dict(log) for log in logs],
                "total": total,
                "pages": pages,
                "current_page": page,
                "per_page": per_page
            }
        except SQLAlchemyError as e:
            logger.error(f"获取热点爬取日志列表失败: {str(e)}")
            return {
                "list": [],
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "error": str(e)
            }

    def _log_to_dict(self, log: HotTopicLog) -> Dict[str, Any]:
        """将日志对象转换为字典
        
        Args:
            log: 日志对象
            
        Returns:
            日志字典
        """
        return {
            "id": log.id,
            "task_id": log.task_id,
            "batch_id": log.batch_id,
            "platform": log.platform,
            "status": log.status,
            "topic_count": log.topic_count,
            "error_type": log.error_type,
            "error_stage": log.error_stage,
            "error_message": log.error_message,
            "request_started_at": log.request_started_at.isoformat() if log.request_started_at else None,
            "request_ended_at": log.request_ended_at.isoformat() if log.request_ended_at else None,
            "request_duration": log.request_duration,
            "processing_time": log.processing_time,
            "memory_usage": log.memory_usage,
            "cpu_usage": log.cpu_usage,
            "crawler_id": log.crawler_id,
            "crawler_host": log.crawler_host,
            "crawler_ip": log.crawler_ip,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "updated_at": log.updated_at.isoformat() if log.updated_at else None
        }