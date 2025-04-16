# app/api/jobs/hot_topics.py
"""热点爬取任务API接口"""
import logging
import uuid
from flask import Blueprint, request, current_app
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session

# 仓库导入
from app.infrastructure.database.repositories.hot_topic_repository import HotTopicTaskRepository, HotTopicRepository, HotTopicLogRepository

# 服务导入
from app.domains.hot_topics.services.hot_topic_service import HotTopicService

logger = logging.getLogger(__name__)

# 创建热点任务蓝图
hot_topics_jobs_bp = Blueprint("hot_topics_jobs", __name__)

@hot_topics_jobs_bp.route("/pending_hot_topics", methods=["GET"])
@app_key_required
def pending_hot_topics():
    """获取待爬取的热点任务"""
    try:
        # 获取请求参数
        limit = request.args.get("limit", 1, type=int)
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        
        # 获取待爬取任务
        tasks = task_repo.get_pending_tasks(limit)
        
        return success_response(tasks)
    except Exception as e:
        logger.error(f"获取待爬取热点任务失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取待爬取热点任务失败: {str(e)}")

@hot_topics_jobs_bp.route("/claim_hot_topics_task", methods=["POST"])
@app_key_required
def claim_hot_topics_task():
    """认领热点爬取任务"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "task_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少task_id参数")
        
        task_id = data["task_id"]
        
        # 获取爬虫标识
        crawler_id = request.headers.get("X-Crawler-ID") or "unknown"
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        
        # 认领任务
        err, task = task_repo.claim_task(task_id, crawler_id)
        if err:
            return error_response(PARAMETER_ERROR, err)
        
        return success_response(task)
    except Exception as e:
        logger.error(f"认领热点任务失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"认领热点任务失败: {str(e)}")

@hot_topics_jobs_bp.route("/submit_hot_topics_result", methods=["POST"])
@app_key_required
def submit_hot_topics_result():
    """提交热点爬取结果"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "请求数据不能为空")
        
        # 验证必填字段
        required_fields = ["task_id", "platform", "status"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return error_response(PARAMETER_ERROR, f"缺少必填字段: {', '.join(missing_fields)}")
        
        task_id = data["task_id"]
        platform = data["platform"]
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        topic_repo = HotTopicRepository(db_session)
        log_repo = HotTopicLogRepository(db_session)
        
        # 创建服务
        hot_topic_service = HotTopicService(task_repo, topic_repo, log_repo)
        
        # 处理爬取结果
        success = hot_topic_service.process_task_result(task_id, platform, data)
        
        if success:
            return success_response({"message": "爬取结果提交成功"})
        else:
            return error_response(PARAMETER_ERROR, "爬取结果处理失败")
    except Exception as e:
        logger.error(f"提交热点爬取结果失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"提交热点爬取结果失败: {str(e)}")

