# app/infrastructure/database/repositories/rss_agent_repository.py
"""RSS爬虫代理仓库"""
import logging
from typing import Dict, List, Optional, Any

from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.rss import RssCrawlerAgent

logger = logging.getLogger(__name__)

class RssCrawlerAgentRepository:
    """爬虫代理仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def create_agent(self, agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建代理
        
        Args:
            agent_data: 代理数据
            
        Returns:
            创建的代理
            
        Raises:
            SQLAlchemyError: 数据库错误
        """
        try:
            agent = RssCrawlerAgent(**agent_data)
            self.db.add(agent)
            self.db.commit()
            self.db.refresh(agent)
            return self._agent_to_dict(agent)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建爬虫代理失败: {str(e)}")
            raise

    def update_agent(self, agent_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新代理
        
        Args:
            agent_id: 代理ID
            update_data: 更新数据
            
        Returns:
            更新后的代理
            
        Raises:
            SQLAlchemyError: 数据库错误
        """
        try:
            agent = self.db.query(RssCrawlerAgent).filter(
                RssCrawlerAgent.agent_id == agent_id
            ).first()
            
            if not agent:
                raise ValueError(f"未找到代理ID: {agent_id}")
            
            # 更新字段
            for key, value in update_data.items():
                if hasattr(agent, key):
                    setattr(agent, key, value)
            
            self.db.commit()
            self.db.refresh(agent)
            return self._agent_to_dict(agent)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新爬虫代理失败, ID={agent_id}: {str(e)}")
            raise

    def get_by_agent_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """根据代理ID获取代理
        
        Args:
            agent_id: 代理ID
            
        Returns:
            代理信息
        """
        try:
            agent = self.db.query(RssCrawlerAgent).filter(
                RssCrawlerAgent.agent_id == agent_id
            ).first()
            
            if not agent:
                return None
            
            return self._agent_to_dict(agent)
        except SQLAlchemyError as e:
            logger.error(f"获取爬虫代理失败, ID={agent_id}: {str(e)}")
            return None

    def get_agents(self, status: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取代理列表
        
        Args:
            status: 状态筛选，None表示全部
            
        Returns:
            代理列表
        """
        try:
            query = self.db.query(RssCrawlerAgent)
            
            if status is not None:
                query = query.filter(RssCrawlerAgent.status == status)
            
            query = query.order_by(desc(RssCrawlerAgent.last_heartbeat))
            agents = query.all()
            
            return [self._agent_to_dict(agent) for agent in agents]
        except SQLAlchemyError as e:
            logger.error(f"获取爬虫代理列表失败: {str(e)}")
            return []

    def _agent_to_dict(self, agent: RssCrawlerAgent) -> Dict[str, Any]:
        """将代理对象转换为字典
        
        Args:
            agent: 代理对象
            
        Returns:
            代理字典
        """
        return {
            "id": agent.id,
            "agent_id": agent.agent_id,
            "hostname": agent.hostname,
            "ip_address": agent.ip_address,
            "version": agent.version,
            "capabilities": agent.capabilities,
            "status": agent.status,
            "last_heartbeat": agent.last_heartbeat.isoformat() if agent.last_heartbeat else None,
            "total_tasks": agent.total_tasks,
            "success_tasks": agent.success_tasks,
            "failed_tasks": agent.failed_tasks,
            "avg_processing_time": agent.avg_processing_time,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None
        }