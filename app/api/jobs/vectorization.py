# app/api/jobs/vectorization.py
"""文章向量化任务API接口"""
import logging
import uuid
from flask import Blueprint, request, current_app
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session

# 仓库导入
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss_vectorization_repository import RssFeedArticleVectorizationTaskRepository

# 服务导入
from app.domains.rss.services.vectorization_service import ArticleVectorizationService

logger = logging.getLogger(__name__)

# 创建向量化任务蓝图
vectorization_jobs_bp = Blueprint("vectorization_jobs", __name__)

@vectorization_jobs_bp.route("/pending_vectorization", methods=["GET"])
@app_key_required
def pending_vectorization():
    """获取待向量化的文章"""
    try:
        # 获取请求参数
        limit = request.args.get("limit", 10, type=int)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        
        # 获取待向量化文章
        articles = article_repo.get_articles_for_vectorization(limit)
        
        return success_response(articles)
    except Exception as e:
        logger.error(f"获取待向量化文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取待向量化文章失败: {str(e)}")

@vectorization_jobs_bp.route("/claim_vectorization_task", methods=["POST"])
@app_key_required
def claim_vectorization_task():
    """认领文章向量化任务"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "article_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        article_id = data["article_id"]
        
        # 获取爬虫标识
        crawler_id = request.headers.get("X-Crawler-ID") or "unknown"
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        
        # 标记文章为处理中
        err, article = article_repo.update_article_vectorization_status(
            article_id=article_id,
            status=3  # 处理中
        )
        
        if err:
            return error_response(PARAMETER_ERROR, err)
        
        return success_response(article)
    except Exception as e:
        logger.error(f"认领向量化任务失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"认领向量化任务失败: {str(e)}")

@vectorization_jobs_bp.route("/submit_vectorization_result", methods=["POST"])
@app_key_required
def submit_vectorization_result():
    """提交向量化结果"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "请求数据不能为空")
        
        # 验证必填字段
        required_fields = ["article_id", "status", "vector_id"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return error_response(PARAMETER_ERROR, f"缺少必填字段: {', '.join(missing_fields)}")
        
        article_id = data["article_id"]
        status = data["status"]
        vector_id = data["vector_id"]
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        
        # 更新文章向量化状态
        update_data = {
            "is_vectorized": status == "success",
            "vector_id": vector_id if status == "success" else None,
            "vectorized_at": data.get("vectorized_at"),
            "embedding_model": data.get("embedding_model"),
            "vector_dimension": data.get("vector_dimension"),
            "generated_summary": data.get("generated_summary"),
            "vectorization_status": 1 if status == "success" else 2,  # 1=成功，2=失败
            "vectorization_error": data.get("error") if status != "success" else None
        }
        
        err, updated_article = article_repo.update_article_vectorization(article_id, update_data)
        
        if err:
            return error_response(PARAMETER_ERROR, err)
        
        return success_response({"message": "向量化结果提交成功", "article": updated_article})
    except Exception as e:
        logger.error(f"提交向量化结果失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"提交向量化结果失败: {str(e)}")

@vectorization_jobs_bp.route("/start_vectorization_batch", methods=["POST"])
@app_key_required
def start_vectorization_batch():
    """开始批量向量化任务"""
    try:
        # 获取请求数据
        data = request.get_json() or {}
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 创建向量化服务
        model = data.get("model", "text-embedding-3-small")
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo,
            model=model
        )
        
        # 过滤条件
        filters = {}
        if "feed_id" in data:
            filters["feed_id"] = data["feed_id"]
        if "date_range" in data:
            filters["date_range"] = data["date_range"]
        
        # 确保只处理未向量化的文章
        filters["vectorization_status"] = 0  # 未处理
        
        # 启动向量化任务
        task = vectorization_service.start_vectorization_task(filters)
        
        return success_response({
            "message": "向量化任务已启动",
            "task": task
        })
    except Exception as e:
        logger.error(f"启动向量化任务失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"启动向量化任务失败: {str(e)}")

@vectorization_jobs_bp.route("/vectorization_task_status", methods=["GET"])
@app_key_required
def vectorization_task_status():
    """获取向量化任务状态"""
    try:
        # 获取请求参数
        batch_id = request.args.get("batch_id")
        if not batch_id:
            return error_response(PARAMETER_ERROR, "缺少batch_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 获取任务状态
        task = task_repo.get_task(batch_id)
        if not task:
            return error_response(PARAMETER_ERROR, f"未找到批次ID为{batch_id}的向量化任务")
        
        return success_response(task)
    except Exception as e:
        logger.error(f"获取向量化任务状态失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取向量化任务状态失败: {str(e)}")

@vectorization_jobs_bp.route("/process_single_article", methods=["POST"])
@app_key_required
def process_single_article():
    """处理单篇文章向量化"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "article_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        article_id = data["article_id"]
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 创建向量化服务
        model = data.get("model", "text-embedding-3-small")
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo,
            model=model
        )
        
        # 处理单篇文章
        result = vectorization_service.process_article_vectorization(article_id)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"处理单篇文章向量化失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"处理单篇文章向量化失败: {str(e)}")

@vectorization_jobs_bp.route("/search_similar_articles", methods=["GET"])
@app_key_required
def search_similar_articles():
    """搜索相似文章"""
    try:
        # 获取请求参数
        article_id = request.args.get("article_id", type=int)
        limit = request.args.get("limit", 10, type=int)
        
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
            task_repo=task_repo
        )
        
        # 获取相似文章
        similar_articles = vectorization_service.get_similar_articles(article_id, limit)
        
        return success_response(similar_articles)
    except Exception as e:
        logger.error(f"搜索相似文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"搜索相似文章失败: {str(e)}")

@vectorization_jobs_bp.route("/search_by_text", methods=["POST"])
@app_key_required
def search_by_text():
    """根据文本搜索文章"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "query" not in data:
            return error_response(PARAMETER_ERROR, "缺少query参数")
        
        query = data["query"]
        limit = data.get("limit", 10)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 创建向量化服务
        model = data.get("model", "text-embedding-3-small")
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
        logger.error(f"文本搜索文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"文本搜索文章失败: {str(e)}")

@vectorization_jobs_bp.route("/vectorization_statistics", methods=["GET"])
@app_key_required
def vectorization_statistics():
    """获取向量化统计信息"""
    try:
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 创建向量化服务
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo
        )
        
        # 获取统计信息
        statistics = vectorization_service.get_vectorization_statistics()
        
        # 获取最近任务列表
        tasks = task_repo.get_all_tasks(page=1, per_page=5)
        statistics["recent_tasks"] = tasks["list"]
        
        return success_response(statistics)
    except Exception as e:
        logger.error(f"获取向量化统计信息失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取向量化统计信息失败: {str(e)}")