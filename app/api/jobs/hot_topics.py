# app/api/jobs/hot_topics.py
"""热点爬取任务API接口"""
from datetime import datetime
import logging
import uuid
from flask import Blueprint, request, current_app
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.domains.hot_topics.services.hot_topic_aggregation_service import HotTopicAggregationService
from app.infrastructure.database.session import get_db_session

# 仓库导入
from app.infrastructure.database.repositories.hot_topic_repository import HotTopicTaskRepository, HotTopicRepository, HotTopicLogRepository, UnifiedHotTopicRepository

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


@hot_topics_jobs_bp.route("/submit_hot_topics_result", methods=["POST"])
@app_key_required
def submit_hot_topics_result():
    """提交热点爬取结果"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "请求数据不能为空")
        
        # 获取必要参数
        task_id = data.get("task_id")
        platform = data.get("platform")
        
        if not task_id or not platform:
            return error_response(PARAMETER_ERROR, "缺少task_id或platform")
        
        status = data.get("status", 2)  # 默认为失败状态
        topics = data.get("topics", [])
        topic_count = data.get("topic_count", 0)
        batch_id = data.get("batch_id", str(uuid.uuid4()))
        
        # 如果是错误状态，直接保存爬取日志
        if status == 2:
            log_data = {
                "task_id": task_id,
                "batch_id": batch_id,
                "platform": platform,
                "status": status,
                "topic_count": 0,
                "error_type": data.get("error_type"),
                "error_stage": data.get("error_stage"),
                "error_message": data.get("error_message"),
                "error_stack_trace": data.get("error_stack_trace"),
                "request_started_at": datetime.fromisoformat(data.get("request_started_at")) if data.get("request_started_at") else None,
                "request_ended_at": datetime.fromisoformat(data.get("request_ended_at")) if data.get("request_ended_at") else None,
                "request_duration": data.get("request_duration"),
                "processing_time": data.get("processing_time"),
                "memory_usage": data.get("memory_usage"),
                "cpu_usage": data.get("cpu_usage"),
                "crawler_id": data.get("crawler_id"),
                "crawler_host": data.get("crawler_host"),
                "crawler_ip": data.get("crawler_ip")
            }
            
            # 创建会话和存储库
            db_session = get_db_session()
            log_repo = HotTopicLogRepository(db_session)
            
            # 保存日志
            log = log_repo.create_log(log_data)
            
            return success_response(log.get("id"), "错误日志已保存")
        
        # 正常状态的处理（status == 1）
        # 1. 保存热点话题和日志
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        topic_repo = HotTopicRepository(db_session)
        log_repo = HotTopicLogRepository(db_session)
        unified_topic_repo = UnifiedHotTopicRepository(db_session)
        
        # 创建服务
        topic_service = HotTopicService(task_repo, topic_repo)
        
        # 保存爬取结果
        result = topic_service.save_crawl_results(task_id, platform, batch_id, topics)
        
        # 保存日志数据
        log_data = {
            "task_id": task_id,
            "batch_id": batch_id,
            "platform": platform,
            "status": 1,  # 成功状态
            "topic_count": topic_count,
            "request_started_at": datetime.fromisoformat(data.get("request_started_at")) if data.get("request_started_at") else None,
            "request_ended_at": datetime.fromisoformat(data.get("request_ended_at")) if data.get("request_ended_at") else None,
            "request_duration": data.get("request_duration"),
            "processing_time": data.get("processing_time"),
            "memory_usage": data.get("memory_usage"),
            "cpu_usage": data.get("cpu_usage"),
            "crawler_id": data.get("crawler_id"),
            "crawler_host": data.get("crawler_host"),
            "crawler_ip": data.get("crawler_ip")
        }
        
        log = log_repo.create_log(log_data)
        
        # 2. 判断是否所有平台的任务都已完成
        task = task_repo.get_task_by_id(task_id)
        if not task:
            logger.error(f"未找到任务: {task_id}")
            return error_response(PARAMETER_ERROR, "未找到任务")
        
        # 获取该任务所有平台的日志
        filters = {"task_id": task_id, "status": 1}  # 只统计成功的
        logs = log_repo.get_logs(filters, page=1, per_page=100)
        completed_platforms = set()
        for log_entry in logs.get("list", []):
            completed_platforms.add(log_entry.get("platform"))
        
        expected_platforms = set(task.get("platforms", []))
        
        # 3. 如果所有平台都已完成，触发聚合和向量化
        if completed_platforms == expected_platforms:
            logger.info(f"任务 {task_id} 的所有平台都已完成，开始进行热点聚合和向量化...")
            
            # 获取今天的所有热点话题
            today = datetime.now().date()
            hot_topics_filters = {
                "topic_date": today.isoformat(),
                "status": 1
            }
            hot_topics = topic_repo.get_topics(hot_topics_filters, page=1, per_page=1000)
            all_hot_topics = hot_topics.get("list", [])
            
            if not all_hot_topics:
                logger.warning(f"今天没有找到任何热点话题")
                return success_response(result, "爬取结果已保存，但没有找到热点话题进行聚合")
            
            # 创建聚合服务实例
            aggregation_service = HotTopicAggregationService(
                db_session=db_session,
                hot_topic_repo=topic_repo,
                unified_topic_repo=unified_topic_repo
            )
            
            # 执行聚合和向量化
            aggregation_result = aggregation_service.aggregate_topics_for_date(today)
            
            if aggregation_result.get("status") == "success":
                logger.info(
                    f"热点聚合和向量化成功，创建了 {aggregation_result.get('unified_topics_created')} 个统一热点话题，"
                    f"成功向量化了 {aggregation_result.get('vectorized_count')} 个话题"
                )
                
                # 更新任务状态为已完成
                task_repo.update_task(task_id, {
                    "status": 2,  # 已完成
                    "last_executed_at": datetime.now()
                })
                
                return success_response({
                    "crawl_result": result,
                    "aggregation_result": aggregation_result
                }, "爬取结果已保存并完成热点聚合和向量化")
            else:
                logger.error(f"热点聚合和向量化失败: {aggregation_result.get('message')}")
                return success_response({
                    "crawl_result": result,
                    "aggregation_error": aggregation_result.get('message')
                }, "爬取结果已保存，但热点聚合和向量化失败")
        else:
            # 还有平台未完成，仅返回当前平台的保存结果
            remaining_platforms = list(expected_platforms - completed_platforms)
            logger.info(f"任务 {task_id} 还有 {len(remaining_platforms)} 个平台未完成: {remaining_platforms}")
            
            return success_response({
                "crawl_result": result,
                "remaining_platforms": remaining_platforms
            }, f"爬取结果已保存，等待其他平台完成")
        
    except Exception as e:
        logger.error(f"提交热点爬取结果失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"提交热点爬取结果失败: {str(e)}")



@hot_topics_jobs_bp.route("/create_task", methods=["POST"])
@app_key_required
def create_hot_topics_task():
    """创建热点爬取任务API"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "请求数据不能为空")
        
        platforms = data.get("platforms", [])
        if not platforms:
            return error_response(PARAMETER_ERROR, "缺少platforms参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        
        # 创建任务
        task_id = str(uuid.uuid4())
        task_data = {
            "task_id": task_id,
            "status": 0,  # 待处理
            "platforms": platforms,
            "scheduled_time": datetime.now(),
            "trigger_type": "manual",
            "triggered_by": "crawler"
        }
        
        err,task = task_repo.create_task(task_data)
        if err:
            logger.error(f"创建热点爬取任务失败: {err}")
            return error_response(PARAMETER_ERROR, f"创建热点爬取任务失败: {err}")
        
        return success_response(task, "任务创建成功")
    except Exception as e:
        logger.error(f"创建热点爬取任务失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"创建热点爬取任务失败: {str(e)}")

@hot_topics_jobs_bp.route("/claim_hot_topics_task", methods=["POST"])
@app_key_required
def claim_hot_topics_task():
    """认领热点爬取任务API"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "请求数据不能为空")
        
        task_id = data.get("task_id")
        if not task_id:
            return error_response(PARAMETER_ERROR, "缺少task_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        
        # 获取任务
        task = task_repo.get_task_by_id(task_id)
        if not task:
            return error_response(PARAMETER_ERROR, "任务不存在")
        
        # 检查任务状态
        if task.get("status") != 0:
            return error_response(PARAMETER_ERROR, "任务已被处理或已完成")
        
        # 更新任务状态
        crawler_id = request.headers.get("X-Crawler-ID", "unknown")
        task_repo.update_task(task_id, {
            "status": 1,  # 处理中
            "crawler_id": crawler_id
        })
        
        # 返回任务信息
        return success_response(task, "任务认领成功")
    except Exception as e:
        logger.error(f"认领热点爬取任务失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"认领热点爬取任务失败: {str(e)}")