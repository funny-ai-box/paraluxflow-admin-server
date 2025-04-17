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




# app/api/jobs/vectorization.py 中的 process_single_article 方法修改

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
        model = data.get("model", None)
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo,
            content_repo=content_repo,
            task_repo=task_repo,
            model=model
        )
        
        # 处理单篇文章 - 直接让异常冒泡，不进行捕获
        result = vectorization_service.process_article_vectorization(article_id)
        
        return success_response(result)
    except Exception as e:
        # 记录详细错误信息
        logger.error(f"处理单篇文章向量化失败: {str(e)}")
        
        # 返回详细的错误信息和适当的错误代码
        error_msg = str(e)
        
        # 根据错误类型确定错误代码
        error_code = PARAMETER_ERROR
        
        # 检查是否是数据库结构问题
        if "Unknown column" in error_msg:
            error_msg = f"数据库结构错误: {error_msg}。请确保已执行数据库迁移添加向量化相关字段。"
        
        # 检查是否是服务未初始化问题
        elif "无法初始化服务" in error_msg:
            error_msg = f"服务配置错误: {error_msg}。请检查OpenAI API密钥和Milvus连接配置。"
        
        # 返回明确的错误响应
        return error_response(error_code, error_msg)