# app/api/admin/v1/rss/vectorization.py
"""RSS文章向量化管理API"""
import logging
from flask import Blueprint, request, g
from app.api.middleware.auth import auth_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, SUCCESS
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss_vectorization_repository import RssFeedArticleVectorizationTaskRepository
from app.domains.rss.services.vectorization_service import ArticleVectorizationService

logger = logging.getLogger(__name__)

vectorization_bp = Blueprint("vectorization", __name__)

@vectorization_bp.route("/start_task", methods=["POST"])
@auth_required
def start_vectorization_task():
    """启动向量化任务"""
    try:
        data = request.get_json() or {}
        db_session = g.db_session
        
        # 初始化存储库
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 初始化向量化服务
        model = data.get("model", None)
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo,
            model=model
        )
        
        # 创建过滤条件
        filters = {}
        if "feed_id" in data:
            filters["feed_id"] = data["feed_id"]
        if "date_range" in data:
            filters["date_range"] = data["date_range"]
        if "status" in data:
            filters["status"] = data["status"]
        
        # 向量化状态过滤
        if "vectorization_status" in data:
            filters["vectorization_status"] = data["vectorization_status"]
        else:
            # 默认处理未向量化的文章
            filters["vectorization_status"] = 0
        
        # 启动任务
        task = vectorization_service.start_vectorization_task(filters)
        
        return success_response({
            "message": "向量化任务已启动",
            "task": task
        })
    except Exception as e:
        logger.error(f"启动向量化任务失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"启动向量化任务失败: {str(e)}")

@vectorization_bp.route("/tasks", methods=["GET"])
@auth_required
def get_vectorization_tasks():
    """获取向量化任务列表"""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        status = request.args.get("status", type=int)  # 可选的状态过滤
        
        db_session = g.db_session
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        tasks = task_repo.get_all_tasks(page, per_page, status)
        
        return success_response(tasks)
    except Exception as e:
        logger.error(f"获取向量化任务列表失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取向量化任务列表失败: {str(e)}")

@vectorization_bp.route("/task/<batch_id>", methods=["GET"])
@auth_required
def get_vectorization_task(batch_id):
    """获取向量化任务详情"""
    try:
        db_session = g.db_session
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        task = task_repo.get_task(batch_id)
        if not task:
            return error_response(PARAMETER_ERROR, f"未找到批次ID为{batch_id}的向量化任务")
        
        return success_response(task)
    except Exception as e:
        logger.error(f"获取向量化任务详情失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取向量化任务详情失败: {str(e)}")

@vectorization_bp.route("/vectorized_articles", methods=["GET"])
@auth_required
def get_vectorized_articles():
    """获取已向量化的文章列表"""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        
        db_session = g.db_session
        article_repo = RssFeedArticleRepository(db_session)
        
        # 查询已向量化的文章
        filters = {"vectorization_status": 1}  # 1=成功
        
        # 其他可选过滤条件
        if "feed_id" in request.args:
            filters["feed_id"] = request.args.get("feed_id")
        if "title" in request.args:
            filters["title"] = request.args.get("title")
        
        articles = article_repo.get_articles(page, per_page, filters)
        
        return success_response(articles)
    except Exception as e:
        logger.error(f"获取已向量化文章列表失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取已向量化文章列表失败: {str(e)}")

@vectorization_bp.route("/failed_articles", methods=["GET"])
@auth_required
def get_failed_articles():
    """获取向量化失败的文章列表"""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        
        db_session = g.db_session
        article_repo = RssFeedArticleRepository(db_session)
        
        # 查询向量化失败的文章
        filters = {"vectorization_status": 2}  # 2=失败
        
        # 其他可选过滤条件
        if "feed_id" in request.args:
            filters["feed_id"] = request.args.get("feed_id")
        if "title" in request.args:
            filters["title"] = request.args.get("title")
        
        articles = article_repo.get_articles(page, per_page, filters)
        
        return success_response(articles)
    except Exception as e:
        logger.error(f"获取向量化失败的文章列表失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取向量化失败的文章列表失败: {str(e)}")

@vectorization_bp.route("/retry_article/<int:article_id>", methods=["POST"])
@auth_required
def retry_article_vectorization(article_id):
    """重试向量化失败的文章"""
    try:
        db_session = g.db_session
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
        
        # 初始化向量化服务
        data = request.get_json() or {}
        model = data.get("model", None)
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo,
            model=model
        )
        
        # 处理文章
        result = vectorization_service.process_article_vectorization(article_id)
        
        return success_response({
            "message": "文章重新向量化处理完成",
            "result": result
        })
    except Exception as e:
        logger.error(f"重试文章向量化失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"重试文章向量化失败: {str(e)}")

@vectorization_bp.route("/statistics", methods=["GET"])
@auth_required
def get_vectorization_statistics():
    """获取向量化统计信息"""
    try:
        db_session = g.db_session
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo
        )
        
        # 获取统计信息
        statistics = vectorization_service.get_vectorization_statistics()
        
        # 获取最近任务
        tasks = task_repo.get_all_tasks(page=1, per_page=5)
        statistics["recent_tasks"] = tasks["list"]
        
        return success_response(statistics)
    except Exception as e:
        logger.error(f"获取向量化统计信息失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取向量化统计信息失败: {str(e)}")

@vectorization_bp.route("/similar_articles/<int:article_id>", methods=["GET"])
@auth_required
def get_similar_articles(article_id):
    """获取相似文章"""
    try:
        limit = request.args.get("limit", 10, type=int)
        
        db_session = g.db_session
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo
        )
        
        # 获取相似文章
        similar_articles = vectorization_service.get_similar_articles(article_id, limit)
        
        return success_response(similar_articles)
    except Exception as e:
        logger.error(f"获取相似文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取相似文章失败: {str(e)}")

@vectorization_bp.route("/search", methods=["POST"])
@auth_required
def search_articles():
    """搜索文章"""
    try:
        data = request.get_json()
        if not data or "query" not in data:
            return error_response(PARAMETER_ERROR, "缺少query参数")
        
        query = data["query"]
        limit = data.get("limit", 10)
        
        db_session = g.db_session
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        model = data.get("model",None)
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo,
            model=model
        )
        
        # 搜索文章
        result_articles = vectorization_service.search_articles(query, limit)
        
        return success_response(result_articles)
    except Exception as e:
        logger.error(f"搜索文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"搜索文章失败: {str(e)}")