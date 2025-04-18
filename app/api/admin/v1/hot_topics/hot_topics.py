# app/api/admin/v1/hot_topics/hot_topics.py
"""热点话题API控制器"""
import json
import logging
from datetime import datetime
from app.core.exceptions import APIException
from app.domains.hot_topics.services.hot_topic_aggregation_service import HotTopicAggregationService
from app.domains.rss.services.vectorization_service import ArticleVectorizationService
from app.infrastructure.database.repositories.llm_repository import LLMProviderRepository
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.llm_providers.factory import LLMProviderFactory
from flask import Blueprint, request, g

from app.api.middleware.auth import auth_required, admin_required
from app.core.responses import success_response, error_response
from app.core.status_codes import EXTERNAL_API_ERROR, PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.hot_topic_repository import HotTopicTaskRepository, HotTopicRepository, HotTopicLogRepository, UnifiedHotTopicRepository
from app.domains.hot_topics.services.hot_topic_service import HotTopicService
from app.infrastructure.database.repositories.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss_vectorization_repository import RssFeedArticleVectorizationTaskRepository
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
@hot_topics_bp.route("/aggregate", methods=["POST"])
@admin_required # 需要管理员权限才能触发
def trigger_hot_topic_aggregation():
    """
    手动触发指定日期的热点话题聚合任务
    
    请求体:
    {
        "topic_date": "2025-04-18",  # 必填，需要聚合的热点日期 (格式: YYYY-MM-DD)
        "model_id": "gpt-4",         # 可选，指定使用的模型ID
        "provider_type": "openai"    # 可选，指定使用的提供商类型
    }
    
    Returns:
        聚合任务的结果
    """
    logger.info("收到请求，开始触发热点话题聚合")
    try:
        # 1. 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "请求体不能为空")

        topic_date_str = data.get("topic_date")
        model_id = data.get("model_id")  # 可选: 覆盖默认LLM模型
        provider_type = data.get("provider_type","volcano")  # 可选: 指定提供商类型

        if not topic_date_str:
            return error_response(PARAMETER_ERROR, "缺少 topic_date 参数 (格式: YYYY-MM-DD)")

        # 2. 创建依赖和服务
        db_session = get_db_session()
        hot_topic_repo = HotTopicRepository(db_session)
        unified_topic_repo = UnifiedHotTopicRepository(db_session)
        
        # 创建聚合服务（不在这里初始化LLM提供商，由服务内部处理）
        aggregation_service = HotTopicAggregationService(
            db_session=db_session,
            hot_topic_repo=hot_topic_repo,
            unified_topic_repo=unified_topic_repo
        )
        
        # 3. 调用服务的触发方法
        logger.info(f"调用聚合服务触发方法，日期: {topic_date_str}")
        result = aggregation_service.trigger_aggregation(
            topic_date_str=topic_date_str,
            model_id=model_id,
            provider_type=provider_type
        )

        # 4. 根据结果返回响应
        status = result.get("status")
        if status == "success":
            return success_response(result, f"日期 {topic_date_str} 的热点聚合成功")
        elif status == "no_topics":
            return success_response(result, f"日期 {topic_date_str} 没有找到需要聚合的热点")
        elif status == "llm_error":
            return error_response(EXTERNAL_API_ERROR, result.get("message", "初始化LLM提供商失败"))
        elif status == "ai_error":
            return error_response(EXTERNAL_API_ERROR, result.get("message", "AI聚合调用失败"))
        elif status == "db_error":
            return error_response(PARAMETER_ERROR, result.get("message", "数据库操作失败"))
        else:
            return error_response(PARAMETER_ERROR, result.get("message", "聚合过程中发生未知错误"))

    except Exception as e:
        logger.error(f"触发热点聚合失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"触发聚合失败: {str(e)}")
    
@hot_topics_bp.route("/unified/list", methods=["GET"])
@auth_required
def get_unified_hot_topics():
    """
    获取指定日期的统一（聚合）热点列表，包含关联的原始热点信息。
    如果不提供 topic_date，则默认获取最新一天的聚合热点。
    """
    logger.info("请求获取统一热点列表...")
    try:
        # 1. Get Parameters
        topic_date_str = request.args.get("topic_date")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        # 2. Determine Target Date
        target_date = None
        db_session = get_db_session() # Get session early for date check
        unified_topic_repo = UnifiedHotTopicRepository(db_session) # Need repo for date check

        if topic_date_str:
            try:
                target_date = datetime.strptime(topic_date_str, "%Y-%m-%d").date()
                logger.info(f"使用指定日期: {target_date.isoformat()}")
            except ValueError:
                return error_response(PARAMETER_ERROR, "无效的日期格式，应为YYYY-MM-DD")
        else:
            # Find the latest date with unified topics
            target_date = unified_topic_repo.get_latest_unified_topic_date()
            if not target_date:
                 logger.info("数据库中没有找到任何统一热点数据")
                 # Return empty list gracefully
                 return success_response({
                     "list": [], "total": 0, "pages": 0, 
                     "current_page": 1, "per_page": per_page, 
                     "topic_date": None
                 })
            logger.info(f"未指定日期，使用最新日期: {target_date.isoformat()}")

        hot_topic_repo = HotTopicRepository(db_session)


        unified_result = unified_topic_repo.get_unified_topics_by_date(target_date, page, per_page)
        unified_topics_list = unified_result.get("list", [])

        if not unified_topics_list:
            logger.info(f"日期 {target_date.isoformat()} 没有找到统一热点数据 (Page: {page})")

            return success_response({
                 "list": [], "total": unified_result.get('total', 0), 
                 "pages": unified_result.get('pages', 0), 
                 "current_page": page, "per_page": per_page, 
                 "topic_date": target_date.isoformat()
             })

        # 5. Collect all related raw topic IDs from the current page
        all_related_ids = set()
        for unified_topic in unified_topics_list:
            related_ids = unified_topic.get("related_topic_ids")
            if isinstance(related_ids, list):
                all_related_ids.update(related_ids)
            elif isinstance(related_ids, str): # Handle if stored as JSON string initially
                 try:
                      parsed_ids = json.loads(related_ids)
                      if isinstance(parsed_ids, list):
                           all_related_ids.update(parsed_ids)
                 except json.JSONDecodeError:
                      logger.warning(f"无法解析 related_topic_ids JSON 字符串: {related_ids}")


        # 6. Fetch related raw topics in one batch
        raw_topics_map = {}
        if all_related_ids:
            logger.info(f"准备获取 {len(all_related_ids)} 条关联的原始热点...")
            raw_topics_list = hot_topic_repo.get_topics_by_ids(list(all_related_ids))
            # Create a map for easy lookup
            raw_topics_map = {topic["id"]: topic for topic in raw_topics_list}
            logger.info(f"成功获取 {len(raw_topics_map)} 条原始热点详情。")


        # 7. Combine data: Add raw topics to each unified topic
        for unified_topic in unified_topics_list:
            related_ids = unified_topic.get("related_topic_ids", [])
            # Ensure related_ids is a list (handle potential JSON string)
            if isinstance(related_ids, str):
                 try:
                      related_ids = json.loads(related_ids)
                 except json.JSONDecodeError:
                      related_ids = [] # Default to empty if parsing fails
            
            unified_topic["related_raw_topics"] = [
                raw_topics_map[raw_id] for raw_id in related_ids if raw_id in raw_topics_map
            ]
            # Sort related raw topics by platform maybe? Optional.
            unified_topic["related_raw_topics"].sort(key=lambda x: x.get('platform', ''))


        # 8. Return the enhanced result
        final_response_data = {
            "list": unified_topics_list,
            "total": unified_result.get('total', 0),
            "pages": unified_result.get('pages', 0),
            "current_page": page,
            "per_page": per_page,
            "topic_date": target_date.isoformat() # Include the date used for the query
        }

        return success_response(final_response_data)

    except Exception as e:
        logger.error(f"获取统一热点列表失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取统一热点列表失败: {str(e)}")

@hot_topics_bp.route("/related_articles", methods=["GET"])
@auth_required
def get_hot_topic_related_articles():
    """获取与热点相关的RSS文章
    
    查询参数:
    - topic_id: 统一热点ID
    - limit: 返回的最大文章数量，默认10
    - days_range: 查找的最大天数范围，默认7
    
    Returns:
        相关文章列表
    """
    try:
        # 获取参数
        topic_id = request.args.get("topic_id")
        limit = request.args.get("limit", 10, type=int)
        days_range = request.args.get("days_range", 7, type=int)
        
        if not topic_id:
            return error_response(PARAMETER_ERROR, "缺少topic_id参数")
        
        # 创建依赖组件
        db_session = get_db_session()
        unified_topic_repo = UnifiedHotTopicRepository(db_session)
        hot_topic_repo = HotTopicRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)
        
        # 创建向量化服务

        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo
        )
        
        # 创建搜索服务
        from app.domains.hot_topics.services.hot_topic_search_service import HotTopicSearchService
        search_service = HotTopicSearchService(
            unified_topic_repo=unified_topic_repo,
            hot_topic_repo=hot_topic_repo,
            article_repo=article_repo,
            vectorization_service=vectorization_service
        )
        
        # 查找相关文章
        result = search_service.find_related_articles(
            unified_topic_id=topic_id,
            limit=limit,
            days_range=days_range
        )
        
        return success_response(result)
    except APIException as e:
        return error_response(e.code, str(e))
    except Exception as e:
        logger.error(f"获取热点相关文章失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取热点相关文章失败: {str(e)}")

@hot_topics_bp.route("/unified_topic_detail", methods=["GET"])
@auth_required
def get_unified_topic_detail():
    """获取统一热点详情
    
    查询参数:
    - topic_id: 统一热点ID
    
    Returns:
        统一热点详情
    """
    try:
        # 获取参数
        topic_id = request.args.get("topic_id")
        
        if not topic_id:
            return error_response(PARAMETER_ERROR, "缺少topic_id参数")
        
        # 创建依赖组件
        db_session = get_db_session()
        unified_topic_repo = UnifiedHotTopicRepository(db_session)
        hot_topic_repo = HotTopicRepository(db_session)
        
        # 创建搜索服务
        from app.domains.hot_topics.services.hot_topic_search_service import HotTopicSearchService
        search_service = HotTopicSearchService(
            unified_topic_repo=unified_topic_repo,
            hot_topic_repo=hot_topic_repo,
            article_repo=None,  # 不需要文章仓库
            vectorization_service=None  # 不需要向量化服务
        )
        
        # 获取统一热点详情
        result = search_service.get_topic_by_id(topic_id)
        
        return success_response(result)
    except APIException as e:
        return error_response(e.code, str(e))
    except Exception as e:
        logger.error(f"获取统一热点详情失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取统一热点详情失败: {str(e)}")