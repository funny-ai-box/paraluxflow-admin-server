# app/api/admin/v1/rss/vectorization.py
"""RSS文章向量化管理API - 主要用于向量检索、重新向量化和日志查询"""
import logging
import uuid
from datetime import datetime
from flask import Blueprint, request, g
from app.api.middleware.auth import auth_required, admin_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, SUCCESS
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss.rss_vectorization_repository import RssFeedArticleVectorizationTaskRepository
from app.domains.rss.services.vectorization_service import ArticleVectorizationService
from app.infrastructure.database.session import get_db_session

logger = logging.getLogger(__name__)

vectorization_bp = Blueprint("vectorization", __name__)

@vectorization_bp.route("/retry_vectorization", methods=["POST"])
@auth_required
def retry_article_vectorization():
    """重试向量化文章
    
    请求参数:
        {
            "article_id": 123,        # 文章ID
            "provider_type": "openai", # 可选，提供商类型
            "model": "embedding-model", # 可选，使用的模型
            "reason": "手动重试"       # 可选，重试原因
        }
        
    返回:
        重试结果
    """
    
    # 获取请求参数
    data = request.get_json() or {}
    
    if "article_id" not in data:
        return error_response(PARAMETER_ERROR, "缺少article_id参数")
    
    article_id = data["article_id"]
    provider_type = data.get("provider_type")
    model = data.get("model")
    reason = data.get("reason", "管理员手动重试")
    
    # 创建会话和存储库
    db_session = get_db_session()
    article_repo = RssFeedArticleRepository(db_session)
    content_repo = RssFeedArticleContentRepository(db_session)
    task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
    
    # 重置文章向量化状态
    err, article = article_repo.update_article_vectorization_status(
        article_id=article_id,
        status=0  # 重置为未处理
    )
    
    if err:
        return error_response(PARAMETER_ERROR, err)
    
    # 创建任务ID
    task_id = str(uuid.uuid4())
    
    # 记录开始时间
    start_time = datetime.now()
    
    # 创建向量化服务
    vectorization_service = ArticleVectorizationService(
        article_repo=article_repo,
        content_repo=content_repo,
        task_repo=task_repo,
        provider_type=provider_type,
        model=model
    )
    
    try:
        # 创建任务记录
        task_repo.create_task({
            "batch_id": task_id,
            "total_articles": 1,
            "processed_articles": 0,
            "success_articles": 0,
            "failed_articles": 0,
            "status": 0,  # 进行中
            "started_at": start_time,
            "embedding_model": model,
            "additional_info": {
                "article_id": article_id,
                "action": "retry",
                "reason": reason,
                "admin_user_id": g.user_id,
                "timestamp": start_time.isoformat()
            }
        })
        
        # 处理文章向量化
        result = vectorization_service.process_article_vectorization(article_id)
        
        # 更新任务记录
        task_repo.update_task(task_id, {
            "processed_articles": 1,
            "success_articles": 1,
            "failed_articles": 0,
            "status": 1,  # 完成
            "ended_at": datetime.now(),
            "total_time": (datetime.now() - start_time).total_seconds()
        })
        
        return success_response({
            "message": "文章重新向量化处理完成",
            "result": result,
            "task_id": task_id
        })
    except Exception as e:
        # 更新任务记录
        task_repo.update_task(task_id, {
            "processed_articles": 1,
            "success_articles": 0,
            "failed_articles": 1,
            "status": 1,  # 完成但失败
            "ended_at": datetime.now(),
            "total_time": (datetime.now() - start_time).total_seconds(),
            "error_message": str(e)
        })
        
        logger.error(f"重试文章向量化失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"重试文章向量化失败: {str(e)}")
            
@vectorization_bp.route("/vectorization_logs", methods=["GET"])
@auth_required
def get_vectorization_logs():
    """获取向量化日志
    
    请求参数:
        page: 页码，默认1
        per_page: 每页条数，默认10
        article_id: 可选，按文章ID过滤
        status: 可选，按状态过滤: 0=进行中, 1=已完成, 2=失败
        date_start: 可选，开始日期，格式"2023-01-01"
        date_end: 可选，结束日期，格式"2023-12-31"
        
    返回:
        分页的向量化日志列表
    """
    try:
        # 获取请求参数
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        article_id = request.args.get("article_id", type=int)
        status = request.args.get("status", type=int)
        
        # 处理日期范围
        date_range = None
        date_start = request.args.get("date_start")
        date_end = request.args.get("date_end")
        if date_start or date_end:
            date_range = [date_start, date_end]
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 获取向量化日志
        tasks = task_repo.get_all_tasks(page=page, per_page=per_page, article_id=article_id, status=status, date_range=date_range)
        
        return success_response(tasks)
    except Exception as e:
        logger.error(f"获取向量化日志失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取向量化日志失败: {str(e)}")

@vectorization_bp.route("/log_detail", methods=["GET"])
@auth_required
def get_log_detail():
    """获取向量化日志详情
    
    请求参数:
        task_id: 任务ID
        
    返回:
        向量化日志详情
    """
    try:
        # 获取请求参数
        task_id = request.args.get("task_id")
        
        if not task_id:
            return error_response(PARAMETER_ERROR, "缺少task_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 获取任务详情
        task = task_repo.get_task(task_id)
        if not task:
            return error_response(PARAMETER_ERROR, f"未找到ID为{task_id}的向量化任务")
        
        # 获取任务相关的文章ID
        article_id = None
        if task.get("additional_info") and isinstance(task["additional_info"], dict):
            article_id = task["additional_info"].get("article_id")
        
        # 如果有文章ID，获取文章信息
        if article_id:
            article_repo = RssFeedArticleRepository(db_session)
            err, article = article_repo.get_article_by_id(article_id)
            if not err and article:
                task["article"] = article
        
        return success_response(task)
    except Exception as e:
        logger.error(f"获取向量化日志详情失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取向量化日志详情失败: {str(e)}")

@vectorization_bp.route("/search", methods=["POST"])
@auth_required
def search_articles():
    """搜索文章
    
    请求参数:
        {
            "query": "搜索关键词",  # 查询文本
            "limit": 10,           # 限制返回数量
            "provider_type": "openai", # 可选，提供商类型
            "model": "embedding-model" # 可选，使用的模型
        }
        
    返回:
        搜索结果列表
    """
    try:
        # 获取请求参数
        data = request.get_json() or {}
        
        if "query" not in data:
            return error_response(PARAMETER_ERROR, "缺少query参数")
        
        query = data["query"]
        limit = data.get("limit", 10)
        provider_type = data.get("provider_type")
        model = data.get("model")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 创建向量化服务
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo,
            provider_type=provider_type,
            model=model
        )
        
        # 搜索文章
        result_articles = vectorization_service.search_articles(query, limit)
        
        return success_response({
            "query": query,
            "results": result_articles,
            "total": len(result_articles)
        })
    except Exception as e:
        logger.error(f"搜索文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"搜索文章失败: {str(e)}")

@vectorization_bp.route("/similar_articles", methods=["GET"])
@auth_required
def get_similar_articles():
    """获取相似文章
    
    请求参数:
        article_id: 文章ID
        limit: 限制返回数量，默认10
        provider_type: 可选，提供商类型，默认openai
        model: 可选，使用的模型
        
    返回:
        相似文章列表
    """
    try:
        # 获取请求参数
        article_id = request.args.get("article_id", type=int)
        limit = request.args.get("limit", 10, type=int)
        provider_type = request.args.get("provider_type", "openai")
        model = request.args.get("model")
        
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 创建向量化服务
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo,
            provider_type=provider_type,
            model=model
        )
        
        # 获取相似文章
        similar_articles = vectorization_service.get_similar_articles(article_id, limit)
        
        return success_response({
            "article_id": article_id,
            "similar_articles": similar_articles,
            "total": len(similar_articles)
        })
    except Exception as e:
        logger.error(f"获取相似文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取相似文章失败: {str(e)}")
        
@vectorization_bp.route("/vector_store_info", methods=["GET"])
@auth_required
def get_vector_store_info():
    """获取向量存储信息
    
    请求参数:
        collection_name: 可选，集合名称，默认rss_articles
        
    返回:
        向量存储信息
    """
    try:
        # 获取请求参数
        collection_name = request.args.get("collection_name", "rss_articles")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 创建向量化服务
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo,
            collection_name=collection_name
        )
        
        # 确保向量存储已初始化
        if not vectorization_service.vector_store:
            vectorization_service._init_services()
        
        # 获取向量存储信息
        store_info = {
            "provider_name": vectorization_service.vector_store.get_provider_name(),
            "is_healthy": vectorization_service.vector_store.health_check(),
            "collection_name": collection_name
        }
        
        # 获取集合信息
        if vectorization_service.vector_store.index_exists(collection_name):
            # 获取向量数量
            vector_count = vectorization_service.vector_store.count(collection_name)
            store_info["vector_count"] = vector_count
            store_info["exists"] = True
            
            # 获取集合列表
            try:
                indexes = vectorization_service.vector_store.list_indexes()
                store_info["all_indexes"] = indexes
            except Exception as idx_err:
                logger.warning(f"获取集合列表失败: {str(idx_err)}")
        else:
            store_info["exists"] = False
            store_info["vector_count"] = 0
        
        return success_response(store_info)
    except Exception as e:
        logger.error(f"获取向量存储信息失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取向量存储信息失败: {str(e)}")
        
@vectorization_bp.route("/batch_retry", methods=["POST"])
@auth_required
def batch_retry_vectorization():
    """批量重试向量化失败的文章
    
    请求参数:
        {
            "feed_id": "feed-id",      # 可选，按Feed过滤
            "limit": 10,               # 最大处理数量
            "provider_type": "openai", # 可选，提供商类型
            "model": "embedding-model", # 可选，使用的模型
            "reason": "批量重试"        # 可选，重试原因
        }
        
    返回:
        批量重试结果
    """
    try:
        # 获取请求参数
        data = request.get_json() or {}
        feed_id = data.get("feed_id")
        limit = data.get("limit", 10)
        provider_type = data.get("provider_type", "openai")
        model = data.get("model")
        reason = data.get("reason", "管理员批量重试")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        
        # 构建过滤条件
        filters = {"vectorization_status": 2}  # 失败的文章
        if feed_id:
            filters["feed_id"] = feed_id
        
        # 获取失败的文章
        articles_result = article_repo.get_articles(page=1, per_page=limit, filters=filters)
        articles = articles_result["list"]
        
        if not articles:
            return success_response({
                "message": "没有需要重试的文章",
                "count": 0
            })
        
        # 批量重置文章状态
        reset_count = 0
        reset_ids = []
        
        for article in articles:
            try:
                err, _ = article_repo.update_article_vectorization_status(
                    article_id=article["id"],
                    status=0  # 重置为未处理
                )
                
                if not err:
                    reset_count += 1
                    reset_ids.append(article["id"])
            except Exception as reset_err:
                logger.warning(f"重置文章 {article['id']} 状态失败: {str(reset_err)}")
        
        # 创建批量重试日志
        try:
            task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
            task_repo.create_task({
                "batch_id": f"batch-retry-{int(datetime.now().timestamp())}",
                "total_articles": reset_count,
                "processed_articles": reset_count,
                "success_articles": reset_count,
                "failed_articles": 0,
                "status": 1,  # 完成
                "started_at": datetime.now(),
                "ended_at": datetime.now(),
                "total_time": 0,
                "additional_info": {
                    "action": "batch_reset",
                    "reason": reason,
                    "admin_user_id": g.user_id,
                    "reset_ids": reset_ids,
                    "feed_id": feed_id,
                    "timestamp": datetime.now().isoformat()
                }
            })
        except Exception as log_err:
            logger.warning(f"创建批量重试日志失败: {str(log_err)}")
        
        return success_response({
            "message": f"成功重置 {reset_count} 篇文章状态，等待worker处理",
            "count": reset_count,
            "reset_ids": reset_ids
        })
    except Exception as e:
        logger.error(f"批量重试文章向量化失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"批量重试文章向量化失败: {str(e)}")