# app/api/jobs/vectorization.py
"""文章向量化任务API接口，供worker调用"""
import logging
import uuid
from datetime import datetime
from flask import Blueprint, request, current_app, jsonify
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, SUCCESS
from app.infrastructure.database.session import get_db_session

# 仓库导入
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss.rss_vectorization_repository import RssFeedArticleVectorizationTaskRepository

# 服务导入
from app.domains.rss.services.vectorization_service import ArticleVectorizationService

logger = logging.getLogger(__name__)

# 创建向量化任务蓝图
vectorization_jobs_bp = Blueprint("vectorization_jobs", __name__)

@vectorization_jobs_bp.route("/pending_vectorization", methods=["POST"])
@app_key_required
def pending_vectorization():
    """获取待向量化的文章
    
    请求参数:
        {
            "limit": 10,           # 获取数量，默认10
            "worker_id": "worker1" # worker标识，可选
        }
        
    返回:
        文章列表
    """
    try:
        # 获取请求参数
        data = request.get_json() or {}
        limit = data.get("limit", 10)
        worker_id = data.get("worker_id", "unknown")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        
        logger.info(f"Worker {worker_id} 请求获取 {limit} 篇待向量化文章")
        
        # 获取待向量化文章
        articles = article_repo.get_articles_for_vectorization(limit)
        
        return success_response({
            "articles": articles,
            "worker_id": worker_id,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取待向量化文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取待向量化文章失败: {str(e)}")

@vectorization_jobs_bp.route("/claim_vectorization_task", methods=["POST"])
@app_key_required
def claim_vectorization_task():
    """认领文章向量化任务
    
    请求参数:
        {
            "article_id": 123,     # 文章ID
            "worker_id": "worker1" # worker标识
        }
        
    返回:
        认领结果
    """
    try:
        # 获取请求数据
        data = request.get_json() or {}
        if not data or "article_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        article_id = data["article_id"]
        worker_id = data.get("worker_id", "unknown")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        
        logger.info(f"Worker {worker_id} 认领文章 {article_id} 进行向量化")
        
        # 标记文章为处理中
        err, article = article_repo.update_article_vectorization_status(
            article_id=article_id,
            status=3  # 处理中
        )
        
        if err:
            return error_response(PARAMETER_ERROR, err)
        
        # 添加认领日志
        task_id = str(uuid.uuid4())
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        try:
            task_repo.create_task({
                "batch_id": task_id,
                "total_articles": 1,
                "processed_articles": 0,
                "success_articles": 0,
                "failed_articles": 0,
                "status": 0,  # 进行中
                "started_at": datetime.now(),
                "embedding_model": data.get("model", "default"),
                "additional_info": {
                    "worker_id": worker_id,
                    "article_id": article_id,
                    "action": "claim",
                    "timestamp": datetime.now().isoformat()
                }
            })
        except Exception as log_err:
            logger.warning(f"创建认领日志失败: {str(log_err)}")
        
        return success_response({
            "article": article,
            "task_id": task_id,
            "worker_id": worker_id,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"认领向量化任务失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"认领向量化任务失败: {str(e)}")
@vectorization_jobs_bp.route("/process_article_vectorization", methods=["POST"])
@app_key_required
def process_article_vectorization():
    """处理单篇文章向量化
    
    请求参数:
        {
            "article_id": 123,        # 文章ID
            "worker_id": "worker1",   # worker标识
            "model": "embedding-model", # 可选，使用的模型
            "provider_type": "openai", # 可选，使用的提供商
            "task_id": "uuid-task"    # 任务ID，可选
        }
        
    返回:
        处理结果
    """
    try:
        # 获取请求数据
        data = request.get_json() or {}
        if not data or "article_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        article_id = data["article_id"]
        worker_id = data.get("worker_id", "unknown")
        task_id = data.get("task_id", str(uuid.uuid4()))
        model = data.get("model")
        provider_type = data.get("provider_type")
        
        # 获取开始时间
        start_time = datetime.now()
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        logger.info(f"Worker {worker_id} 开始处理文章 {article_id} 向量化，任务ID: {task_id}")
        
        # 获取系统指标
        memory_usage = data.get("memory_usage")
        cpu_usage = data.get("cpu_usage")
        worker_host = data.get("worker_host")
        worker_ip = data.get("worker_ip")
        
        # 检查任务是否存在，如果不存在则创建
        task = task_repo.get_task(task_id)
        if not task:
            logger.info(f"任务 {task_id} 不存在，将自动创建任务")
            try:
                # 创建任务 - 单文章记录模式
                task_repo.create_task({
                    "batch_id": task_id,
                    "article_id": article_id,
                    "status": 3,  # 处理中
                    "embedding_model": model,
                    "provider_type": provider_type,
                    "worker_id": worker_id,
                    "started_at": datetime.now(),
                    "memory_usage": memory_usage,
                    "cpu_usage": cpu_usage,
                    "worker_host": worker_host,
                    "worker_ip": worker_ip
                })
                logger.info(f"成功创建任务 {task_id} 用于文章 {article_id} 的向量化")
            except Exception as create_err:
                logger.warning(f"创建任务失败，但将继续处理: {str(create_err)}")
        
        # 创建向量化服务
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo,
            provider_type=provider_type,
            model=model
        )
        
        # 处理单篇文章向量化
        try:
            result = vectorization_service.process_article_vectorization(article_id)
            status = 1  # 成功
            error_message = None
            error_type = None
            
            # 更新任务记录
            try:
                task_repo.update_task(task_id, {
                    "status": 1,  # 完成
                    "ended_at": datetime.now(),
                    "processing_time": (datetime.now() - start_time).total_seconds(),
                    "vector_id": result.get("vector_id")
                })
            except Exception as log_err:
                logger.warning(f"更新任务日志失败: {str(log_err)}")
            
            logger.info(f"Worker {worker_id} 成功处理文章 {article_id} 向量化")
            
        except Exception as e:
            logger.error(f"文章向量化处理失败: {str(e)}")
            status = 2  # 失败
            error_message = str(e)
            error_type = type(e).__name__
            result = {"status": "failed", "message": str(e)}
            
            # 更新任务日志
            try:
                task_repo.update_task(task_id, {
                    "status": 2,  # 失败
                    "ended_at": datetime.now(),
                    "processing_time": (datetime.now() - start_time).total_seconds(),
                    "error_message": error_message,
                    "error_type": error_type
                })
            except Exception as log_err:
                logger.warning(f"更新任务日志失败: {str(log_err)}")
        
        return success_response({
            "result": result,
            "task_id": task_id,
            "worker_id": worker_id,
            "article_id": article_id,
            "status": status,
            "error_message": error_message,
            "processing_time": (datetime.now() - start_time).total_seconds(),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        # 记录详细错误信息
        logger.error(f"处理单篇文章向量化失败: {str(e)}", exc_info=True)
        
        # 返回详细的错误信息和适当的错误代码
        error_msg = str(e)
        
        # 根据错误类型确定错误代码
        error_code = PARAMETER_ERROR
        
        # 返回明确的错误响应
        return error_response(error_code, error_msg)