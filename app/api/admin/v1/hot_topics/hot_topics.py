# app/api/admin/v1/hot_topics/hot_topics.py
"""热点话题API控制器"""
import logging
from datetime import datetime
from flask import Blueprint, request, g

from app.api.middleware.auth import auth_required, admin_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.hot_topic_repository import HotTopicTaskRepository, HotTopicRepository, HotTopicLogRepository
from app.domains.hot_topics.services.hot_topic_service import HotTopicService

logger = logging.getLogger(__name__)

# 创建蓝图
hot_topics_bp = Blueprint("hot_topics", __name__)

@hot_topics_bp.route("/latest", methods=["GET"])
@auth_required
def get_latest_hot_topics():
    """获取最新热点话题
    
    查询参数:
    - platform: 平台筛选
    - limit: 返回条数，默认50
    - topic_date: 指定日期，格式：YYYY-MM-DD，不提供则获取最新日期
    
    Returns:
        最新热点话题列表
    """
    try:
        # 获取参数
        platform = request.args.get("platform")
        limit = request.args.get("limit", 50, type=int)
        topic_date_str = request.args.get("topic_date")
        
        # 解析日期参数
        topic_date = None
        if topic_date_str:
            try:
                topic_date = datetime.strptime(topic_date_str, "%Y-%m-%d").date()
            except ValueError:
                return error_response(PARAMETER_ERROR, f"无效的日期格式，应为YYYY-MM-DD")
        
        # 创建会话和存储库
        db_session = get_db_session()
        topic_repo = HotTopicRepository(db_session)
        
        # 创建服务
        hot_topic_service = HotTopicService(None, topic_repo)
        
        # 获取最新热点
        topics = topic_repo.get_latest_hot_topics(platform, limit, topic_date)
        
        return success_response(topics)
    except Exception as e:
        logger.error(f"获取最新热点话题失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取最新热点话题失败: {str(e)}")

@hot_topics_bp.route("/list", methods=["GET"])
@auth_required
def get_hot_topics():
    """获取热点话题列表
    
    查询参数:
    - page: 页码，默认1
    - per_page: 每页条数，默认20
    - platform: 平台筛选
    - keyword: 标题关键词
    - task_id: 任务ID
    - batch_id: 批次ID
    - topic_date: 热点日期筛选，格式：YYYY-MM-DD
    - start_date: 开始日期，格式：YYYY-MM-DD (针对创建时间)
    - end_date: 结束日期，格式：YYYY-MM-DD (针对创建时间)
    
    Returns:
        热点话题列表及分页信息
    """
    try:
        # 获取参数
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        platform = request.args.get("platform")
        keyword = request.args.get("keyword")
        task_id = request.args.get("task_id")
        batch_id = request.args.get("batch_id")
        topic_date = request.args.get("topic_date")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        
        # 构建筛选条件
        filters = {}
        if platform:
            filters["platform"] = platform
        if keyword:
            filters["keyword"] = keyword
        if task_id:
            filters["task_id"] = task_id
        if batch_id:
            filters["batch_id"] = batch_id
        if topic_date:
            filters["topic_date"] = topic_date
        if start_date or end_date:
            filters["date_range"] = (start_date, end_date)
        
        # 创建会话和存储库
        db_session = get_db_session()
        topic_repo = HotTopicRepository(db_session)
        
        # 获取热点列表
        topics = topic_repo.get_topics(filters, page, per_page)
        
        return success_response(topics)
    except Exception as e:
        logger.error(f"获取热点话题列表失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取热点话题列表失败: {str(e)}")

@hot_topics_bp.route("/task/list", methods=["GET"])
@auth_required
def get_task_list():
    """获取热点任务列表
    
    查询参数:
    - page: 页码，默认1
    - per_page: 每页条数，默认20
    - status: 状态筛选
    - trigger_type: 触发类型筛选
    - start_date: 开始日期，格式：YYYY-MM-DD
    - end_date: 结束日期，格式：YYYY-MM-DD
    
    Returns:
        任务列表及分页信息
    """
    try:
        # 获取参数
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        status = request.args.get("status", type=int)
        trigger_type = request.args.get("trigger_type")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        
        # 构建筛选条件
        filters = {}
        if status is not None:
            filters["status"] = status
        if trigger_type:
            filters["trigger_type"] = trigger_type
        if start_date or end_date:
            filters["date_range"] = (start_date, end_date)
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        topic_repo = HotTopicRepository(db_session)
        
        # 创建服务
        hot_topic_service = HotTopicService(task_repo, topic_repo)
        
        # 获取任务列表
        tasks = hot_topic_service.get_tasks(page=page, per_page=per_page, filters=filters)
        
        return success_response(tasks)
    except Exception as e:
        logger.error(f"获取热点任务列表失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取热点任务列表失败: {str(e)}")

@hot_topics_bp.route("/task/detail", methods=["GET"])
@auth_required
def get_task_detail():
    """获取热点任务详情
    
    查询参数:
    - task_id: 任务ID
    
    Returns:
        任务详情
    """
    try:
        # 获取参数
        task_id = request.args.get("task_id")
        if not task_id:
            return error_response(PARAMETER_ERROR, "缺少task_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        topic_repo = HotTopicRepository(db_session)
        
        # 创建服务
        hot_topic_service = HotTopicService(task_repo, topic_repo)
        
        # 获取任务详情
        task = hot_topic_service.get_task_detail(task_id)
        
        return success_response(task)
    except Exception as e:
        logger.error(f"获取热点任务详情失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取热点任务详情失败: {str(e)}")

@hot_topics_bp.route("/task/create", methods=["POST"])
@auth_required
def create_task():
    """创建热点爬取任务
    
    请求体:
    {
        "platforms": ["weibo", "zhihu", "baidu", "toutiao", "douyin"],
        "schedule_time": "2025-04-17T08:00:00" // 可选，不提供则立即执行
    }
    
    Returns:
        创建的任务
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "请求数据不能为空")
        
        # 验证必填字段
        if "platforms" not in data or not data["platforms"]:
            return error_response(PARAMETER_ERROR, "缺少platforms字段或为空")
        
        platforms = data["platforms"]
        schedule_time = data.get("schedule_time")
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        topic_repo = HotTopicRepository(db_session)
        
        # 创建服务
        hot_topic_service = HotTopicService(task_repo, topic_repo)
        
        # 创建任务
        task = hot_topic_service.create_task(user_id, platforms, schedule_time)
        
        return success_response(task, "任务创建成功")
    except ValueError as e:
        return error_response(PARAMETER_ERROR, str(e))
    except Exception as e:
        logger.error(f"创建热点爬取任务失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"创建热点爬取任务失败: {str(e)}")

@hot_topics_bp.route("/task/schedule", methods=["POST"])
@auth_required
def schedule_task():
    """创建定时热点爬取任务
    
    请求体:
    {
        "platforms": ["weibo", "zhihu", "baidu", "toutiao", "douyin"],
        "schedule_time": "2025-04-17T08:00:00", // 必填，指定执行时间
        "recurrence": "daily" // 可选，重复类型: daily, weekly, monthly, none(默认)
    }
    
    Returns:
        创建的定时任务
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "请求数据不能为空")
        
        # 验证必填字段
        if "platforms" not in data or not data["platforms"]:
            return error_response(PARAMETER_ERROR, "缺少platforms字段或为空")
        
        if "schedule_time" not in data:
            return error_response(PARAMETER_ERROR, "缺少schedule_time字段")
        
        platforms = data["platforms"]
        schedule_time = data["schedule_time"]
        recurrence = data.get("recurrence")
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        topic_repo = HotTopicRepository(db_session)
        
        # 创建服务
        hot_topic_service = HotTopicService(task_repo, topic_repo)
        
        # 创建定时任务
        task = hot_topic_service.schedule_task(user_id, platforms, schedule_time, recurrence)
        
        return success_response(task, "定时任务创建成功")
    except ValueError as e:
        return error_response(PARAMETER_ERROR, str(e))
    except Exception as e:
        logger.error(f"创建定时热点爬取任务失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"创建定时热点爬取任务失败: {str(e)}")

@hot_topics_bp.route("/logs", methods=["GET"])
@auth_required
def get_logs():
    """获取热点爬取日志
    
    查询参数:
    - page: 页码，默认1
    - per_page: 每页条数，默认20
    - task_id: 任务ID
    - platform: 平台
    - status: 状态
    - start_date: 开始日期，格式：YYYY-MM-DD
    - end_date: 结束日期，格式：YYYY-MM-DD
    
    Returns:
        日志列表及分页信息
    """
    try:
        # 获取参数
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        task_id = request.args.get("task_id")
        platform = request.args.get("platform")
        status = request.args.get("status", type=int)
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        
        # 构建筛选条件
        filters = {}
        if task_id:
            filters["task_id"] = task_id
        if platform:
            filters["platform"] = platform
        if status is not None:
            filters["status"] = status
        if start_date or end_date:
            filters["date_range"] = (start_date, end_date)
        
        # 创建会话和存储库
        db_session = get_db_session()
        log_repo = HotTopicLogRepository(db_session)
        
        # 获取日志列表
        logs = log_repo.get_logs(filters, page, per_page)
        
        return success_response(logs)
    except Exception as e:
        logger.error(f"获取热点爬取日志失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取热点爬取日志失败: {str(e)}")

@hot_topics_bp.route("/stats", methods=["GET"])
@auth_required
def get_stats():
    """获取热点话题统计信息
    
    Returns:
        统计信息
    """
    try:
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        topic_repo = HotTopicRepository(db_session)
        
        # 创建服务
        hot_topic_service = HotTopicService(task_repo, topic_repo)
        
        # 获取统计信息
        stats = hot_topic_service.get_hot_topic_stats()
        
        return success_response(stats)
    except Exception as e:
        logger.error(f"获取热点话题统计信息失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取热点话题统计信息失败: {str(e)}")