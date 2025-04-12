# app/api/v1/rss/script.py
"""RSS爬取脚本API控制器"""
import logging
from flask import Blueprint, request, g

from app.api.middleware.auth import auth_required
from app.core.responses import success_response
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss_script_repository import RssFeedCrawlScriptRepository
from app.domains.rss.services.script_service import ScriptService

logger = logging.getLogger(__name__)

# 创建蓝图
script_bp = Blueprint("script", __name__)

@script_bp.route("/list", methods=["GET"])
@auth_required
def get_feed_scripts():
    """获取Feed的爬取脚本列表
    
    查询参数:
    - feed_id: Feed ID
    
    Returns:
        脚本列表
    """
    try:
        # 获取Feed ID
        feed_id = request.args.get("feed_id")
        if not feed_id:
            return success_response(None, "缺少feed_id参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        script_service = ScriptService(script_repo)
        
        # 获取脚本列表
        scripts = script_service.get_scripts(feed_id)
        
        return success_response(scripts)
    except Exception as e:
        logger.error(f"获取爬取脚本列表失败: {str(e)}")
        return success_response(None, f"获取爬取脚本列表失败: {str(e)}", 60001)

@script_bp.route("/detail", methods=["GET"])
@auth_required
def get_script_detail():
    """获取脚本详情
    
    查询参数:
    - script_id: 脚本ID
    
    Returns:
        脚本详情
    """
    try:
        # 获取脚本ID
        script_id = request.args.get("script_id", type=int)
        if not script_id:
            return success_response(None, "缺少script_id参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        script_service = ScriptService(script_repo)
        
        # 获取脚本详情
        script = script_service.get_script(script_id)
        
        return success_response(script)
    except Exception as e:
        logger.error(f"获取脚本详情失败: {str(e)}")
        return success_response(None, f"获取脚本详情失败: {str(e)}", 60001)

@script_bp.route("/add", methods=["POST"])
@auth_required
def add_script():
    """添加爬取脚本
    
    请求体:
    {
        "feed_id": "Feed ID",
        "script": "脚本内容",
        "is_published": false  # 可选，是否发布
    }
    
    Returns:
        添加结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return success_response(None, "未提供数据", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        script_service = ScriptService(script_repo)
        
        # 添加脚本
        script = script_service.add_script(data)
        
        return success_response(script, "添加脚本成功")
    except Exception as e:
        logger.error(f"添加爬取脚本失败: {str(e)}")
        return success_response(None, f"添加爬取脚本失败: {str(e)}", 60001)

@script_bp.route("/update", methods=["POST"])
@auth_required
def update_script():
    """更新爬取脚本
    
    请求体:
    {
        "script_id": 1,
        "script": "更新的脚本内容",
        "is_published": true  # 可选
    }
    
    Returns:
        更新结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return success_response(None, "未提供数据", 60001)
        
        # 检查必需参数
        if "script_id" not in data:
            return success_response(None, "缺少script_id参数", 60001)
        
        script_id = data.pop("script_id")
        
        # 创建会话和存储库
        db_session = get_db_session()
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        script_service = ScriptService(script_repo)
        
        # 更新脚本
        script = script_service.update_script(script_id, data)
        
        return success_response(script, "更新脚本成功")
    except Exception as e:
        logger.error(f"更新爬取脚本失败: {str(e)}")
        return success_response(None, f"更新爬取脚本失败: {str(e)}", 60001)

@script_bp.route("/publish", methods=["POST"])
@auth_required
def publish_script():
    """发布爬取脚本
    
    请求体:
    {
        "feed_id": "Feed ID"
    }
    
    Returns:
        发布结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return success_response(None, "未提供数据", 60001)
        
        feed_id = data.get("feed_id")
        if not feed_id:
            return success_response(None, "缺少feed_id参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        script_service = ScriptService(script_repo)
        
        # 发布脚本
        script = script_service.publish_script(feed_id)
        
        return success_response(script, "发布脚本成功")
    except Exception as e:
        logger.error(f"发布爬取脚本失败: {str(e)}")
        return success_response(None, f"发布爬取脚本失败: {str(e)}", 60001)

@script_bp.route("/test", methods=["POST"])
@auth_required
def test_script():
    """测试爬取脚本
    
    请求体:
    {
        "feed_id": "Feed ID",  # 可选，使用已有脚本
        "script": "脚本内容",  # 可选，提供新脚本
        "html": "HTML内容"    # 必需，待处理的HTML
    }
    
    Returns:
        测试结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return success_response(None, "未提供数据", 60001)
        
        html = data.get("html")
        if not html:
            return success_response(None, "缺少html参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建服务
        script_service = ScriptService(script_repo)
        
        # 确定使用的脚本内容
        script_content = None
        if "script" in data:
            # 使用提供的脚本
            script_content = data["script"]
        elif "feed_id" in data:
            # 获取Feed的最新脚本
            feed_id = data["feed_id"]
            scripts = script_service.get_scripts(feed_id)
            if scripts:
                script_content = scripts[0]["script"]
        
        if not script_content:
            return success_response(None, "未提供脚本内容且未找到Feed对应的脚本", 60001)
        
        # 测试脚本
        result = script_service.test_script(script_content, html)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"测试爬取脚本失败: {str(e)}")
        return success_response(None, f"测试爬取脚本失败: {str(e)}", 60001)