# app/infrastructure/database/repositories/rss_vectorization_repository.py
"""RSS文章向量化任务仓库"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, or_, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.rss import RssFeedArticleVectorizationTask

logger = logging.getLogger(__name__)

class RssFeedArticleVectorizationTaskRepository:
    """RSS文章向量化任务仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建向量化任务
        
        Args:
            task_data: 任务数据
            
        Returns:
            创建的任务
            
        Raises:
            Exception: 创建失败时抛出异常
        """
        try:
            task = RssFeedArticleVectorizationTask(**task_data)
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            return self._task_to_dict(task)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建向量化任务失败: {str(e)}")
            raise Exception(f"创建向量化任务失败: {str(e)}")

    def update_task(self, batch_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新向量化任务
        
        Args:
            batch_id: 批次ID
            update_data: 更新数据
            
        Returns:
            更新后的任务
            
        Raises:
            Exception: 更新失败时抛出异常
        """
        try:
            task = self.db.query(RssFeedArticleVectorizationTask).filter(
                RssFeedArticleVectorizationTask.batch_id == batch_id
            ).first()
            
            if not task:
                raise Exception(f"未找到批次ID为{batch_id}的向量化任务")
            
            # 更新属性
            for key, value in update_data.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            
            self.db.commit()
            self.db.refresh(task)
            return self._task_to_dict(task)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新向量化任务失败, batch_id={batch_id}: {str(e)}")
            raise Exception(f"更新向量化任务失败: {str(e)}")

    def get_task(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """获取向量化任务
        
        Args:
            batch_id: 批次ID
            
        Returns:
            任务信息
        """
        try:
            task = self.db.query(RssFeedArticleVectorizationTask).filter(
                RssFeedArticleVectorizationTask.batch_id == batch_id
            ).first()
            
            if not task:
                return None
            
            return self._task_to_dict(task)
        except SQLAlchemyError as e:
            logger.error(f"获取向量化任务失败, batch_id={batch_id}: {str(e)}")
            return None

    def get_all_tasks(self, page: int = 1, per_page: int = 20, status: Optional[int] = None) -> Dict[str, Any]:
        """获取向量化任务列表
        
        Args:
            page: 页码
            per_page: 每页数量
            status: 任务状态过滤
            
        Returns:
            任务列表及分页信息
        """
        try:
            query = self.db.query(RssFeedArticleVectorizationTask)
            
            # 应用状态过滤
            if status is not None:
                query = query.filter(RssFeedArticleVectorizationTask.status == status)
            
            # 计算总记录数
            total = query.count()
            
            # 应用排序（按创建时间降序）
            query = query.order_by(desc(RssFeedArticleVectorizationTask.created_at))
            
            # 应用分页
            tasks = query.limit(per_page).offset((page - 1) * per_page).all()
            
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
            logger.error(f"获取向量化任务列表失败: {str(e)}")
            return {
                "list": [],
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "error": str(e)
            }

    def _task_to_dict(self, task: RssFeedArticleVectorizationTask) -> Dict[str, Any]:
        """将任务对象转换为字典
        
        Args:
            task: 任务对象
            
        Returns:
            任务字典
        """
        return {
            "id": task.id,
            "batch_id": task.batch_id,
            "total_articles": task.total_articles,
            "processed_articles": task.processed_articles,
            "success_articles": task.success_articles,
            "failed_articles": task.failed_articles,
            "status": task.status,
            "embedding_model": task.embedding_model,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "ended_at": task.ended_at.isoformat() if task.ended_at else None,
            "total_time": task.total_time,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None
        }