# app/api/v1/rss/agent.py
"""RSS爬虫代理API控制器"""
import logging
from app.utils.swagger_utils import document_api
from flask import Blueprint, request, g
import socket

from app.api.middleware.app_key_auth import app_key_required
from app.api.middleware.auth import auth_required
from app.core.responses import success_response
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss_agent_repository import RssCrawlerAgentRepository
from app.domains.rss.services.crawler_agent_service import CrawlerAgentService

logger = logging.getLogger(__name__)

# 创建蓝图
agent_bp = Blueprint("agent", __name__)

@agent_bp.route("/register", methods=["POST"])
@document_api('agent.yml', path="/register")
@app_key_required
def register_agent():
    """注册爬虫代理
    
    请求体:
    {
        "agent_id": "唯一标识",
        "hostname": "主机名",
        "ip_address": "IP地址",
        "version": "爬虫版本",
        "capabilities": "{"js_rendering": true, "proxy_support": true}"
    }
    
    Returns:
        注册结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return success_response(None, "未提供数据", 60001)
        
        # 如果未提供agent_id，使用主机名
        if "agent_id" not in data:
            data["agent_id"] = data.get("hostname", socket.gethostname())
        
        # 创建会话和存储库
        db_session = get_db_session()
        agent_repo = RssCrawlerAgentRepository(db_session)
        
        # 创建服务
        agent_service = CrawlerAgentService(agent_repo)
        
        # 注册代理
        agent = agent_service.register_agent(data)
        
        return success_response(agent, "代理注册成功")
    except Exception as e:
        logger.error(f"注册爬虫代理失败: {str(e)}")
        return success_response(None, f"注册爬虫代理失败: {str(e)}", 60001)

@agent_bp.route("/heartbeat", methods=["POST"])
@document_api('agent.yml', path="/heartbeat")
@app_key_required
def agent_heartbeat():
    """更新代理心跳
    
    请求体:
    {
        "agent_id": "唯一标识",
        "status": 1,
        "performance": {
            "total_tasks": 100,
            "success_tasks": 90,
            "failed_tasks": 10,
            "avg_processing_time": 2.5
        }
    }
    
    Returns:
        心跳结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "agent_id" not in data:
            return success_response(None, "缺少agent_id参数", 60001)
        
        agent_id = data["agent_id"]
        
        # 创建会话和存储库
        db_session = get_db_session()
        agent_repo = RssCrawlerAgentRepository(db_session)
        
        # 创建服务
        agent_service = CrawlerAgentService(agent_repo)
        
        # 更新心跳
        agent = agent_service.heartbeat(agent_id, data)
        
        return success_response(agent, "心跳更新成功")
    except Exception as e:
        logger.error(f"更新爬虫代理心跳失败: {str(e)}")
        return success_response(None, f"更新爬虫代理心跳失败: {str(e)}", 60001)

@agent_bp.route("/list", methods=["GET"])
@document_api('agent.yml', path="/list")
@auth_required
def get_agents():
    """获取代理列表
    
    查询参数:
    - status: 状态筛选
    
    Returns:
        代理列表
    """
    try:
        # 获取状态筛选
        status = request.args.get("status", type=int)
        
        # 创建会话和存储库
        db_session = get_db_session()
        agent_repo = RssCrawlerAgentRepository(db_session)
        
        # 创建服务
        agent_service = CrawlerAgentService(agent_repo)
        
        # 获取代理列表
        agents = agent_service.get_agents(status)
        
        return success_response(agents)
    except Exception as e:
        logger.error(f"获取爬虫代理列表失败: {str(e)}")
        return success_response(None, f"获取爬虫代理列表失败: {str(e)}", 60001)

@agent_bp.route("/detail", methods=["GET"])
@document_api('agent.yml', path="/detail")
@auth_required
def get_agent():
    """获取代理详情
    
    查询参数:
    - agent_id: 代理ID
    
    Returns:
        代理详情
    """
    try:
        # 获取代理ID
        agent_id = request.args.get("agent_id")
        if not agent_id:
            return success_response(None, "缺少agent_id参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        agent_repo = RssCrawlerAgentRepository(db_session)
        
        # 创建服务
        agent_service = CrawlerAgentService(agent_repo)
        
        # 获取代理详情
        agent = agent_service.get_agent(agent_id)
        
        return success_response(agent)
    except Exception as e:
        logger.error(f"获取爬虫代理详情失败: {str(e)}")
        return success_response(None, f"获取爬虫代理详情失败: {str(e)}", 60001)

@agent_bp.route("/update_status", methods=["POST"])
@document_api('agent.yml', path="/update_status")
@auth_required
def update_agent_status():
    """更新代理状态
    
    请求体:
    {
        "agent_id": "唯一标识",
        "status": 2  # 1=活跃, 2=闲置, 3=离线
    }
    
    Returns:
        更新结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "agent_id" not in data or "status" not in data:
            return success_response(None, "缺少必要参数", 60001)
        
        agent_id = data["agent_id"]
        status = data["status"]
        
        # 创建会话和存储库
        db_session = get_db_session()
        agent_repo = RssCrawlerAgentRepository(db_session)
        
        # 创建服务
        agent_service = CrawlerAgentService(agent_repo)
        
        # 更新状态
        agent = agent_service.update_agent_status(agent_id, status)
        
        return success_response(agent, "更新状态成功")
    except Exception as e:
        logger.error(f"更新爬虫代理状态失败: {str(e)}")
        return success_response(None, f"更新爬虫代理状态失败: {str(e)}", 60001)