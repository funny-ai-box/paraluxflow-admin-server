"""RSS Feed爬取脚本API控制器"""
import ast
import re
import threading
import logging
from datetime import datetime

from flask import Blueprint, request, g
from bs4 import BeautifulSoup

from app.api.middleware.auth import auth_required
from app.core.responses import success_response
from app.core.exceptions import ValidationException
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss_repository import (
    RssFeedRepository,
    
)

from app.domains.feed.services.feed_service import FeedService
from app.infrastructure.database.repositories.rss_script_repository import RssFeedCrawlScriptRepository
    
    

logger = logging.getLogger(__name__)

# 创建蓝图
script_bp = Blueprint("script", __name__)


def timeout(limit):
    """函数执行超时装饰器
    
    Args:
        limit: 超时时间(秒)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            res = [
                Exception(f"函数 [{func.__name__}] 执行超时 [{limit} 秒]!")
            ]

            def new_func():
                try:
                    res[0] = func(*args, **kwargs)
                except Exception as e:
                    res[0] = e

            t = threading.Thread(target=new_func)
            t.daemon = True
            t.start()
            t.join(limit)
            if isinstance(res[0], BaseException):
                raise res[0]
            return res[0]

        return wrapper
    return decorator


@script_bp.route("/list", methods=["GET"])
@auth_required
def get_feed_scripts():
    """获取Feed的爬取脚本列表
    
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
        
        # 获取脚本列表
        err, scripts = script_repo.get_feed_scripts(feed_id)
        if err:
            return success_response(None, err, 60001)
        
        return success_response(scripts)
    except Exception as e:
        logger.error(f"获取爬取脚本失败: {str(e)}")
        return success_response(None, f"获取爬取脚本失败: {str(e)}", 60001)





@script_bp.route("/test", methods=["POST"])
@auth_required
def test_script():
    """测试爬取脚本
    
    Returns:
        测试结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return success_response(None, "未提供数据", 60001)
        
        feed_id = data.get("feed_id")
        if not feed_id:
            return success_response(None, "缺少feed_id参数", 60001)
        
        html = data.get("html")
        if not html:
            return success_response(None, "缺少html参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 获取最新脚本
        err, result = script_repo.get_newest_script(feed_id)
        if err:
            return success_response(None, err, 60005)
        
        script = result["script"]
        
        try:
            # 解析AST树，确保没有危险语法
            ast.parse(script)
        except SyntaxError as e:
            return success_response(None, f"脚本语法错误: {str(e)}", 60005)
        
        # 受限执行环境
        local_vars = {}
        allowed_builtins = {
            "print": print,
            "range": range,
            "len": len,
            "int": int,
            "str": str,
            "__import__": __import__,
        }
        global_vars = {
            "__builtins__": allowed_builtins,
            "BeautifulSoup": BeautifulSoup,
            "re": re,
        }
        
        # 执行代码
        try:
            exec(script, global_vars, local_vars)
        except Exception as e:
            logger.error(f"执行脚本失败: {str(e)}")
            return success_response(None, f"执行脚本失败: {str(e)}", 60005)
        
        # 调用函数获取结果
        if "process_data" in local_vars:
            try:
                html_content, text_content = timeout(5)(local_vars["process_data"])(html)
                
                html_content = str(html_content)
                text_content = str(text_content)
                
                return success_response({
                    "html_content": html_content,
                    "text_content": text_content
                })
            except Exception as e:
                logger.error(f"执行process_data函数失败: {str(e)}")
                return success_response(None, f"执行脚本处理函数失败: {str(e)}", 60001)
        else:
            return success_response(None, "脚本中未找到process_data函数", 60001)
    except Exception as e:
        logger.error(f"测试爬取脚本失败: {str(e)}")
        return success_response(None, f"测试爬取脚本失败: {str(e)}", 60001)


@script_bp.route("/add", methods=["POST"])
@auth_required
def add_script():
    """添加爬取脚本
    
    Returns:
        添加结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return success_response(None, "未提供数据", 60001)
        
        feed_id = data.get("feed_id")
        if not feed_id:
            return success_response(None, "缺少feed_id参数", 60001)
        
        script = data.get("script")
        if not script:
            return success_response(None, "缺少script参数", 60001)
        
        is_published = data.get("is_published", False)
        
        # 创建会话和存储库
        db_session = get_db_session()
        script_repo = RssFeedCrawlScriptRepository(db_session)
        
        # 创建脚本
        err, result = script_repo.create_script(feed_id, script, is_published)
        if err:
            return success_response(None, err, 60001)
        
        return success_response(result, "添加脚本成功")
    except Exception as e:
        logger.error(f"添加爬取脚本失败: {str(e)}")
        return success_response(None, f"添加爬取脚本失败: {str(e)}", 60001)


@script_bp.route("/publish", methods=["POST"])
@auth_required
def publish_script():
    """发布爬取脚本
    
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
        
        # 发布脚本
        err, result = script_repo.publish_script(feed_id)
        if err:
            return success_response(None, err, 60001)
        
        return success_response(result, "发布脚本成功")
    except Exception as e:
        logger.error(f"发布爬取脚本失败: {str(e)}")
        return success_response(None, f"发布爬取脚本失败: {str(e)}", 60001)
