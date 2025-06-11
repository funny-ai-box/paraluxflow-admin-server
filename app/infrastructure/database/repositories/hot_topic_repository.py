# app/infrastructure/database/repositories/hot_topic_repository.py
"""热点话题仓库"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, asc, or_, desc, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime, date
from app.infrastructure.database.models.hot_topics import HotTopicPlatform, HotTopicTask, HotTopic, HotTopicLog, UnifiedHotTopic

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

    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据任务ID获取任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息
        """
        try:
            task = self.db.query(HotTopicTask).filter(HotTopicTask.task_id == task_id).first()
            return self._task_to_dict(task) if task else None
        except SQLAlchemyError as e:
            logger.error(f"获取热点爬取任务失败, ID={task_id}: {str(e)}")
            return None

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

    def upsert_topics(self, topics_data: List[Dict[str, Any]]) -> bool:
        """批量upsert热点话题，基于稳定哈希避免重复插入，支持更新已有记录
        
        Args:
            topics_data: 话题数据列表，每个包含stable_hash字段
            
        Returns:
            是否操作成功
        """
        try:
            logger.info(f"开始upsert {len(topics_data)} 个热点话题")
            
            success_count = 0
            update_count = 0
            error_count = 0
            
            for data in topics_data:
                stable_hash = data.get("stable_hash")
                topic_date = data.get("topic_date")
                platform = data.get("platform")
                
                if not stable_hash:
                    logger.error(f"话题数据缺少stable_hash: {data.get('topic_title')}")
                    error_count += 1
                    continue
                
                try:
                    # 查找现有记录
                    existing_topic = self.db.query(HotTopic).filter(
                        HotTopic.stable_hash == stable_hash,
                        HotTopic.topic_date == topic_date,
                        HotTopic.platform == platform
                    ).first()
                    
                    if existing_topic:
                        # 更新现有记录
                        for key, value in data.items():
                            if hasattr(existing_topic, key) and key not in ['id', 'created_at']:
                                setattr(existing_topic, key, value)
                        existing_topic.updated_at = datetime.now()
                        update_count += 1
                        logger.debug(f"更新现有话题: {data.get('topic_title')}")
                    else:
                        # 创建新记录
                        topic = HotTopic(**data)
                        self.db.add(topic)
                        success_count += 1
                        logger.debug(f"创建新话题: {data.get('topic_title')}")
                    
                    # 每100条记录提交一次，避免事务过大
                    if (success_count + update_count) % 100 == 0:
                        self.db.flush()
                        
                except Exception as e:
                    logger.error(f"处理话题失败: {data.get('topic_title')}, 错误: {str(e)}")
                    error_count += 1
            
            # 提交所有更改
            self.db.commit()
            logger.info(f"upsert完成 - 新增: {success_count}, 更新: {update_count}, 失败: {error_count}")
            return (success_count + update_count) > 0
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"批量upsert热点话题失败: {str(e)}", exc_info=True)
            return False

    def get_topics_by_hashes(self, stable_hashes: List[str], topic_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """根据稳定哈希列表获取热点话题信息
        
        Args:
            stable_hashes: 稳定哈希列表
            topic_date: 可选的日期筛选
            
        Returns:
            热点话题字典列表
        """
        if not stable_hashes:
            return []
        try:
            query = self.db.query(HotTopic).filter(HotTopic.stable_hash.in_(stable_hashes))
            
            if topic_date:
                query = query.filter(HotTopic.topic_date == topic_date)
            
            topics = query.all()
            return [self._topic_to_dict(topic) for topic in topics]
        except SQLAlchemyError as e:
            logger.error(f"根据哈希列表获取热点话题失败: {str(e)}")
            return []

    def create_topics(self, topics_data: List[Dict[str, Any]]) -> bool:
        """批量创建热点话题，会处理重复数据（保持向后兼容）"""
        # 为了向后兼容，保留原方法，但建议使用upsert_topics
        logger.warning("create_topics方法已废弃，建议使用upsert_topics方法")
        return self.upsert_topics(topics_data)

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
                
                # 日期筛选
                if "topic_date" in filters and filters["topic_date"]:
                    from datetime import datetime
                    try:
                        # 尝试解析日期
                        if isinstance(filters["topic_date"], str):
                            topic_date = datetime.fromisoformat(filters["topic_date"].rstrip('Z')).date()
                            query = query.filter(HotTopic.topic_date == topic_date)
                    except (ValueError, TypeError):
                        pass  # 忽略无效的日期格式
                
                # 日期范围筛选 (创建时间)
                if "date_range" in filters and filters["date_range"]:
                    start_date, end_date = filters["date_range"]
                    if start_date:
                        query = query.filter(HotTopic.created_at >= start_date)
                    if end_date:
                        query = query.filter(HotTopic.created_at <= end_date)
            
            # 计算总记录数
            total = query.count()
            
            # 应用排序和分页
            # 首先按日期降序排序，然后按平台排序，最后按排名排序
            topics = query.order_by(
                desc(HotTopic.topic_date),
                HotTopic.platform,
                HotTopic.rank if HotTopic.rank is not None else 9999
            ).limit(per_page).offset((page - 1) * per_page).all()
            
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

    def get_latest_hot_topics(self, platform: Optional[str] = None, limit: int = 50, topic_date: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
        """获取最新热点话题
        
        Args:
            platform: 平台筛选
            limit: 获取数量
            topic_date: 指定日期，默认为最新日期
            
        Returns:
            最新热点话题列表
        """
        try:
            # 基本查询
            query = self.db.query(HotTopic).filter(HotTopic.status == 1)  # 有效状态
            
            # 应用平台筛选
            if platform:
                query = query.filter(HotTopic.platform == platform)
            
            # 如果指定了日期，按指定日期筛选
            if topic_date:
                query = query.filter(HotTopic.topic_date == topic_date)
            else:
                # 否则获取最新日期
                max_date_subquery = self.db.query(func.max(HotTopic.topic_date)).scalar_subquery()
                query = query.filter(HotTopic.topic_date == max_date_subquery)
            
            # 查询结果
            topics = query.order_by(
                HotTopic.platform,
                HotTopic.rank if HotTopic.rank is not None else 9999
            ).limit(limit).all()
            
            return [self._topic_to_dict(topic) for topic in topics]
        except SQLAlchemyError as e:
            logger.error(f"获取最新热点话题失败: {str(e)}")
            return []
    
    def get_topics_by_ids(self, topic_ids: List[int]) -> List[Dict[str, Any]]:
        """根据ID列表获取热点话题信息（保持向后兼容）
        
        Args:
            topic_ids: 热点话题ID列表
            
        Returns:
            热点话题字典列表
        """
        if not topic_ids:
            return []
        try:
            # 使用 in_() 进行批量查询
            topics = self.db.query(HotTopic).filter(HotTopic.id.in_(topic_ids)).all()
            return [self._topic_to_dict(topic) for topic in topics]
        except SQLAlchemyError as e:
            logger.error(f"根据ID列表获取热点话题失败: {str(e)}")
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
            "topic_date": topic.topic_date.isoformat() if topic.topic_date else None,
            "stable_hash": topic.stable_hash,  # 添加稳定哈希到返回结果
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


class UnifiedHotTopicRepository:
    """统一热点话题仓库"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def create_unified_topic(self, data: Dict[str, Any]) -> Optional[UnifiedHotTopic]:
        """创建单个统一热点"""
        try:
            unified_topic = UnifiedHotTopic(**data)
            self.db.add(unified_topic)
            self.db.commit()
            self.db.refresh(unified_topic)
            logger.info(f"成功创建统一热点: {data.get('unified_title')}")
            return unified_topic
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建统一热点失败: {str(e)}")
            return None
    
    def get_topic_by_id(self, topic_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取统一热点
        
        Args:
            topic_id: 统一热点ID
            
        Returns:
            统一热点信息，如果未找到则返回None
        """
        try:
            topic = self.db.query(UnifiedHotTopic).filter(UnifiedHotTopic.id == topic_id).first()
            
            if not topic:
                logger.warning(f"未找到ID为 {topic_id} 的统一热点")
                return None
            
            return self._topic_to_dict(topic)
        except SQLAlchemyError as e:
            logger.error(f"根据ID获取统一热点失败: {str(e)}")
            return None
    
    def get_latest_unified_topic_date(self) -> Optional[date]:
        """获取存在统一热点的最新日期"""
        try:
            latest_date = self.db.query(func.max(UnifiedHotTopic.topic_date)).scalar()
            return latest_date
        except SQLAlchemyError as e:
            logger.error(f"获取最新统一热点日期失败: {str(e)}")
            return None

    def create_unified_topics_batch(self, topics_data: List[Dict[str, Any]]) -> bool:
        """批量创建统一热点"""
        try:
            new_topics = [UnifiedHotTopic(**data) for data in topics_data]
            self.db.add_all(new_topics)
            self.db.commit()
            logger.info(f"成功批量创建 {len(new_topics)} 个统一热点")
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"批量创建统一热点失败: {str(e)}")
            return False

    def get_unified_topics_by_date(self, topic_date: date, page: int = 1, per_page: int = 20, category: Optional[str] = None) -> Dict[str, Any]:
        """根据日期获取统一热点列表 (分页)
        
        Args:
            topic_date: 热点日期
            page: 页码
            per_page: 每页数量
            category: 分类筛选 (可选)
        """
        try:
            query = self.db.query(UnifiedHotTopic).filter(UnifiedHotTopic.topic_date == topic_date)
            
            # 添加分类筛选
            if category and category != "all":
                query = query.filter(UnifiedHotTopic.category == category)
            
            total = query.count()
            
            items = query.order_by(desc(UnifiedHotTopic.aggregated_hotness_score), desc(UnifiedHotTopic.topic_count))\
                        .limit(per_page)\
                        .offset((page - 1) * per_page)\
                        .all()

            pages = (total + per_page - 1) // per_page if per_page > 0 else 0

            return {
                "list": [self._topic_to_dict(topic) for topic in items],
                "total": total,
                "pages": pages,
                "current_page": page,
                "per_page": per_page
            }
        except SQLAlchemyError as e:
            logger.error(f"按日期获取统一热点失败: {str(e)}")
            return {"list": [], "total": 0, "pages": 0, "current_page": page, "per_page": per_page, "error": str(e)}

    def get_categories_stats(self, topic_date: Optional[date] = None) -> Dict[str, int]:
        """获取分类统计信息
        
        Args:
            topic_date: 可选的日期筛选
            
        Returns:
            各分类的数量统计
        """
        try:
            query = self.db.query(UnifiedHotTopic.category, func.count(UnifiedHotTopic.id).label('count'))
            
            if topic_date:
                query = query.filter(UnifiedHotTopic.topic_date == topic_date)
            
            results = query.group_by(UnifiedHotTopic.category).all()
            
            # 转换为字典格式
            stats = {}
            for category, count in results:
                stats[category] = count
                
            return stats
        except SQLAlchemyError as e:
            logger.error(f"获取分类统计失败: {str(e)}")
            return {}


    def delete_by_date(self, topic_date: date) -> bool:
        """删除指定日期的所有统一热点 (用于重新生成)"""
        try:
            deleted_count = self.db.query(UnifiedHotTopic).filter(UnifiedHotTopic.topic_date == topic_date).delete()
            self.db.commit()
            logger.info(f"成功删除日期 {topic_date} 的 {deleted_count} 条统一热点")
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"删除日期 {topic_date} 的统一热点失败: {str(e)}")
            return False
            
    def _topic_to_dict(self, topic: UnifiedHotTopic) -> Dict[str, Any]:
        """将统一热点对象转换为字典"""
        return {
            "id": topic.id,
            "topic_date": topic.topic_date.isoformat() if topic.topic_date else None,
            "unified_title": topic.unified_title,
            "unified_summary": topic.unified_summary,
            "representative_url": topic.representative_url,
            "keywords": topic.keywords,
            "category": topic.category,  # 添加分类字段
            "related_topic_hashes": topic.related_topic_hashes,
            "related_topic_ids": topic.related_topic_ids,
            "source_platforms": topic.source_platforms,
            "aggregated_hotness_score": topic.aggregated_hotness_score,
            "topic_count": topic.topic_count,
            "ai_model_used": topic.ai_model_used,
            "ai_processing_time": topic.ai_processing_time,
            "created_at": topic.created_at.isoformat() if topic.created_at else None,
            "updated_at": topic.updated_at.isoformat() if topic.updated_at else None
        }


class HotTopicPlatformRepository:
    """热点平台仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_all_platforms(self, only_active: bool = True) -> List[Dict[str, Any]]:
        """获取所有平台
        
        Args:
            only_active: 是否只获取激活状态的平台
            
        Returns:
            平台列表
        """
        try:
            query = self.db.query(HotTopicPlatform)
            
            if only_active:
                query = query.filter(HotTopicPlatform.is_active == True)
                
            platforms = query.order_by(asc(HotTopicPlatform.display_order)).all()
            return [self._platform_to_dict(platform) for platform in platforms]
        except SQLAlchemyError as e:
            logger.error(f"获取平台列表失败: {str(e)}")
            return []

    def get_platform_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """根据标识码获取平台
        
        Args:
            code: 平台标识码
            
        Returns:
            平台信息或None
        """
        try:
            platform = self.db.query(HotTopicPlatform).filter(
                HotTopicPlatform.code == code
            ).first()
            
            if not platform:
                return None
                
            return self._platform_to_dict(platform)
        except SQLAlchemyError as e:
            logger.error(f"获取平台失败, code={code}: {str(e)}")
            return None

    def create_platform(self, platform_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """创建平台
        
        Args:
            platform_data: 平台数据
            
        Returns:
            创建的平台或None
        """
        try:
            platform = HotTopicPlatform(**platform_data)
            self.db.add(platform)
            self.db.commit()
            self.db.refresh(platform)
            
            return self._platform_to_dict(platform)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建平台失败: {str(e)}")
            return None

    def update_platform(self, code: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新平台
        
        Args:
            code: 平台标识码
            update_data: 更新数据
            
        Returns:
            更新后的平台或None
        """
        try:
            platform = self.db.query(HotTopicPlatform).filter(
                HotTopicPlatform.code == code
            ).first()
            
            if not platform:
                return None
                
            for key, value in update_data.items():
                if hasattr(platform, key):
                    setattr(platform, key, value)
                    
            self.db.commit()
            self.db.refresh(platform)
            
            return self._platform_to_dict(platform)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新平台失败, code={code}: {str(e)}")
            return None

    def _platform_to_dict(self, platform: HotTopicPlatform) -> Dict[str, Any]:
        """将平台对象转换为字典
        
        Args:
            platform: 平台对象
            
        Returns:
            平台字典
        """
        return {
            "id": platform.id,
            "code": platform.code,
            "name": platform.name,
            "icon": platform.icon,
            "description": platform.description,
            "url": platform.url,
            "crawl_config": platform.crawl_config,
            "is_active": platform.is_active,
            "last_crawl_at": platform.last_crawl_at.isoformat() if platform.last_crawl_at else None,
            "display_order": platform.display_order,
            "created_at": platform.created_at.isoformat() if platform.created_at else None,
            "updated_at": platform.updated_at.isoformat() if platform.updated_at else None
        }