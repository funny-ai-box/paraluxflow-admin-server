# app/domains/rss/services/crawler_agent_service.py
"""爬虫代理管理服务"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class CrawlerAgentService:
    """爬虫代理管理服务，处理爬虫实例的注册和监控"""
    
    def __init__(self, agent_repo):
        """初始化服务
        
        Args:
            agent_repo: 爬虫代理仓库
        """
        self.agent_repo = agent_repo
    
    def register_agent(self, agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """注册爬虫代理
        
        Args:
            agent_data: 代理信息
            
        Returns:
            注册后的代理信息
            
        Raises:
            Exception: 注册失败时抛出异常
        """
        # 验证必填字段
        if "agent_id" not in agent_data:
            raise Exception("缺少agent_id字段")
        
        # 检查是否已存在
        agent_id = agent_data["agent_id"]
        existing_agent = self.agent_repo.get_by_agent_id(agent_id)
        
        if existing_agent:
            # 更新现有代理
            agent = self.agent_repo.update_agent(agent_id, {
                **agent_data,
                "last_heartbeat": datetime.now(),
                "status": 1  # 活跃状态
            })
        else:
            # 创建新代理
            agent = self.agent_repo.create_agent({
                **agent_data,
                "last_heartbeat": datetime.now(),
                "status": 1,  # 活跃状态
                "total_tasks": 0,
                "success_tasks": 0,
                "failed_tasks": 0
            })
        
        return agent
    
    def heartbeat(self, agent_id: str, status_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """更新代理心跳
        
        Args:
            agent_id: 代理ID
            status_data: 状态数据
            
        Returns:
            更新后的代理信息
            
        Raises:
            Exception: 更新失败时抛出异常
        """
        # 获取代理
        agent = self.agent_repo.get_by_agent_id(agent_id)
        if not agent:
            raise Exception(f"未找到代理ID: {agent_id}")
        
        # 更新心跳时间和状态
        update_data = {
            "last_heartbeat": datetime.now(),
            "status": status_data.get("status", 1) if status_data else 1
        }
        
        # 更新性能指标
        if status_data and "performance" in status_data:
            perf = status_data["performance"]
            if "total_tasks" in perf:
                update_data["total_tasks"] = perf["total_tasks"]
            if "success_tasks" in perf:
                update_data["success_tasks"] = perf["success_tasks"]
            if "failed_tasks" in perf:
                update_data["failed_tasks"] = perf["failed_tasks"]
            if "avg_processing_time" in perf:
                update_data["avg_processing_time"] = perf["avg_processing_time"]
        
        # 更新代理
        return self.agent_repo.update_agent(agent_id, update_data)
    
    def get_agents(self, status: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取代理列表
        
        Args:
            status: 状态筛选，None表示全部
            
        Returns:
            代理列表
        """
        return self.agent_repo.get_agents(status)
    
    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """获取代理详情
        
        Args:
            agent_id: 代理ID
            
        Returns:
            代理详情
            
        Raises:
            Exception: 获取失败时抛出异常
        """
        agent = self.agent_repo.get_by_agent_id(agent_id)
        if not agent:
            raise Exception(f"未找到代理ID: {agent_id}")
        
        return agent
    
    def update_agent_status(self, agent_id: str, status: int) -> Dict[str, Any]:
        """更新代理状态
        
        Args:
            agent_id: 代理ID
            status: 新状态
            
        Returns:
            更新后的代理信息
            
        Raises:
            Exception: 更新失败时抛出异常
        """
        agent = self.agent_repo.get_by_agent_id(agent_id)
        if not agent:
            raise Exception(f"未找到代理ID: {agent_id}")
        
        return self.agent_repo.update_agent(agent_id, {"status": status})