# app/api/v1/rss/article.py
"""RSS文章API控制器"""
from datetime import datetime
import logging
import time

from flask import Blueprint, g, request, Response
from urllib.parse import unquote

from app.api.middleware.auth import auth_required
from app.core.responses import error_response, success_response
from app.core.status_codes import PARAMETER_ERROR
from app.domains.rss.services.vectorization_service import ArticleVectorizationService
from app.infrastructure.database.repositories.rss.rss_vectorization_repository import RssFeedArticleVectorizationTaskRepository
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss.rss_feed_repository import RssFeedRepository
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss.rss_article_content_repository import RssFeedArticleContentRepository
from app.domains.rss.services.article_service import ArticleService

logger = logging.getLogger(__name__)

# 创建蓝图
article_bp = Blueprint("article", __name__)

@article_bp.route("/list", methods=["GET"])
@auth_required
def get_articles():
    """获取文章列表
    
    请求参数:
        {
            "page": 1,              # 页码，默认1
            "per_page": 10,         # 每页条数，默认10
            "feed_id": "feed-id",   # 可选，按Feed过滤
            "status": 1,            # 可选，按状态过滤
            "title": "关键词",       # 可选，按标题搜索
            "date_range": ["2023-01-01", "2023-12-31"], # 可选，按日期范围过滤
            "vectorization_status": 1  # 可选，按向量化状态过滤: 0=未处理, 1=成功, 2=失败, 3=处理中
        }
        
    返回:
        分页的文章列表
    """
    try:
        # 获取请求参数
        data = request.args
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        
        # 构建过滤条件
        filters = {}
        if "feed_id" in data:
            filters["feed_id"] = data["feed_id"]
        if "status" in data:
            filters["status"] = data["status"]
        if "title" in data and data["title"]:
            filters["title"] = data["title"]
        if "date_range" in data and len(data["date_range"]) == 2:
            filters["date_range"] = data["date_range"]
        if "vectorization_status" in data:
            filters["vectorization_status"] = data["vectorization_status"]
        
        # 创建会话和服务
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        
        # 获取文章列表
        result = article_repo.get_articles(page, per_page, filters)
        
        # 添加向量化状态统计
        if not filters.get("vectorization_status"):
            # 如果没有按向量化状态筛选，添加统计数据
            total_articles = result["total"]
            
            # 统计各状态数量
            vectorized_count = article_repo.get_articles(
                page=1, per_page=1, 
                filters={"vectorization_status": 1}
            )["total"]
            
            failed_count = article_repo.get_articles(
                page=1, per_page=1, 
                filters={"vectorization_status": 2}
            )["total"]
            
            processing_count = article_repo.get_articles(
                page=1, per_page=1, 
                filters={"vectorization_status": 3}
            )["total"]
            
            pending_count = total_articles - vectorized_count - failed_count - processing_count
            
            # 添加统计数据
            result["vectorization_stats"] = {
                "vectorized": vectorized_count,
                "failed": failed_count,
                "processing": processing_count,
                "pending": pending_count,
                "vectorization_rate": round(vectorized_count / total_articles * 100, 2) if total_articles > 0 else 0
            }
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取文章列表失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取文章列表失败: {str(e)}")

@article_bp.route("/detail", methods=["GET"])
@auth_required
def get_article_detail():
    """获取文章详情
    
    请求参数:
        {
            "article_id": 123  # 文章ID
        }
        
    返回:
        文章详情
    """
    try:
        # 获取请求参数
        data = request.args
        
        if "article_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        article_id = data["article_id"]
        
        # 创建会话和服务
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        article_service = ArticleService(
            article_repo=RssFeedArticleRepository(db_session),
            content_repo=content_repo,
            feed_repo=feed_repo
        )
        
        # 获取文章详情
        article = article_service.get_article(article_id)
        
        # 增加向量化信息查询
        try:
            # 获取向量化日志
            task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
            
            # 查询与该文章相关的向量化任务
            tasks = task_repo.get_all_tasks(page=1, per_page=5, article_id=article_id)
            
            # 添加向量化日志
            article["vectorization_logs"] = tasks.get("list", [])
            
            # 如果文章已向量化，获取相似文章
            if article.get("is_vectorized") and article.get("vector_id"):
                # 可选：获取相似文章
                try:
                    vectorization_service = ArticleVectorizationService(
                        article_repo=RssFeedArticleRepository(db_session),
                        content_repo=content_repo,
                        task_repo=task_repo
                    )
                    
                    # 获取最多5篇相似文章
                    similar_articles = vectorization_service.get_similar_articles(article_id, limit=5)
                    
                    # 添加相似文章
                    article["similar_articles"] = similar_articles
                except Exception as sim_err:
                    logger.warning(f"获取相似文章失败: {str(sim_err)}")
                    article["similar_articles"] = []
        except Exception as vec_err:
            logger.warning(f"获取向量化信息失败: {str(vec_err)}")
        
        return success_response(article)
    except Exception as e:
        logger.error(f"获取文章详情失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取文章详情失败: {str(e)}")


@article_bp.route("/reset", methods=["POST"])
@auth_required
def reset_failed_article():
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return success_response(None, "未提供数据", 60001)
        
        article_id = data.get("article_id")
        if not article_id:
            return success_response(None, "缺少article_id参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 重置文章状态
        result = article_service.reset_article(int(article_id))
        
        return success_response(result, "重置文章成功")
    except Exception as e:
        logger.error(f"重置文章失败: {str(e)}")
        return success_response(None, f"重置文章失败: {str(e)}", 60001)

@article_bp.route("/proxy-image", methods=["GET"])
def proxy_image():
    try:
        # 获取并解码图片URL
        image_url = unquote(request.args.get("url", ""))
        if not image_url:
            return "未提供URL", 400
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 获取图片
        image_content, mime_type, error = article_service.proxy_image(image_url)
        if error:
            return f"获取图片失败: {error}", 404
        
        # 返回图片内容
        return Response(
            image_content,
            mimetype=mime_type,
            headers={
                "Cache-Control": "public, max-age=31536000",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except Exception as e:
        logger.error(f"代理获取图片失败: {str(e)}")
        return str(e), 404

@article_bp.route("/get_content_from_url", methods=["GET"])
@auth_required
def get_content_from_url():
    try:
        # 获取URL
        url = request.args.get("url")
        if not url:
            return error_response(60001, "未提供URL")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 获取内容
        content, error = article_service.get_content_from_url(url)
        if error:
            return error_response(60001, f"获取内容失败: {error}")
        
        return success_response(content)
    except Exception as e:
        logger.error(f"从URL获取文章内容失败: {str(e)}")
        return error_response(60001, f"从URL获取文章内容失败: {str(e)}")
    

@article_bp.route("/vectorization_status", methods=["POST"])
@auth_required
def get_vectorization_status():
    """获取文章向量化状态
    
    请求参数:
        {
            "article_ids": [123, 456]  # 文章ID列表
        }
        
    返回:
        文章向量化状态列表
    """
    try:
        # 获取请求参数
        data = request.get_json() or {}
        
        if "article_ids" not in data or not isinstance(data["article_ids"], list):
            return error_response(PARAMETER_ERROR, "缺少article_ids参数或格式不正确")
        
        article_ids = data["article_ids"]
        
        # 创建会话和仓库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        
        # 获取文章状态
        result = []
        for article_id in article_ids:
            err, article = article_repo.get_article_by_id(article_id)
            if not err and article:
                result.append({
                    "article_id": article_id,
                    "is_vectorized": article.get("is_vectorized", False),
                    "vector_id": article.get("vector_id"),
                    "vectorized_at": article.get("vectorized_at"),
                    "embedding_model": article.get("embedding_model"),
                    "vector_dimension": article.get("vector_dimension"),
                    "vectorization_status": article.get("vectorization_status", 0),
                    "vectorization_error": article.get("vectorization_error")
                })
            else:
                result.append({
                    "article_id": article_id,
                    "error": err or "文章不存在"
                })
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取文章向量化状态失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取文章向量化状态失败: {str(e)}")

@article_bp.route("/reset_vectorization", methods=["POST"])
@auth_required
def reset_vectorization():
    """重置文章向量化状态
    
    请求参数:
        {
            "article_id": 123,     # 文章ID
            "reason": "手动重置"   # 可选，重置原因
        }
        
    返回:
        重置结果
    """
    try:
        # 获取请求参数
        data = request.get_json() or {}
        
        if "article_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        article_id = data["article_id"]
        reason = data.get("reason", "管理员手动重置")
        
        # 创建会话和仓库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        
        # 重置向量化状态
        err, result = article_repo.update_article_vectorization_status(
            article_id=article_id,
            status=0,  # 重置为未处理
            error_message=None
        )
        
        if err:
            return error_response(PARAMETER_ERROR, err)
        
        # 记录操作日志
        try:
            task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
            task_repo.create_task({
                "batch_id": f"reset-{article_id}-{int(time.time())}",
                "total_articles": 1,
                "processed_articles": 1,
                "success_articles": 0,
                "failed_articles": 0,
                "status": 1,  # 完成
                "started_at": datetime.now(),
                "ended_at": datetime.now(),
                "total_time": 0,
                "additional_info": {
                    "article_id": article_id,
                    "action": "reset",
                    "reason": reason,
                    "admin_user_id": g.user_id,
                    "timestamp": datetime.now().isoformat()
                }
            })
        except Exception as log_err:
            logger.warning(f"记录重置日志失败: {str(log_err)}")
        
        return success_response({
            "message": "文章向量化状态已重置",
            "article_id": article_id,
            "result": result
        })
    except Exception as e:
        logger.error(f"重置文章向量化状态失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"重置文章向量化状态失败: {str(e)}")

@article_bp.route("/vectorization_statistics", methods=["POST"])
@auth_required
def get_vectorization_statistics():
    """获取向量化统计信息
    
    请求参数:
        {
            "feed_id": "feed-id"  # 可选，按Feed过滤
        }
        
    返回:
        向量化统计信息
    """
    try:
        # 获取请求参数
        data = request.get_json() or {}
        feed_id = data.get("feed_id")
        
        # 创建会话和仓库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session)
        
        # 构建过滤条件
        filters = {}
        if feed_id:
            filters["feed_id"] = feed_id
        
        # 获取全部文章数量
        all_articles = article_repo.get_articles(page=1, per_page=1, filters=filters)["total"]
        
        # 添加向量化状态条件获取各状态文章数量
        vectorization_filters = dict(filters)
        
        # 已向量化
        vectorization_filters["vectorization_status"] = 1
        vectorized_articles = article_repo.get_articles(page=1, per_page=1, filters=vectorization_filters)["total"]
        
        # 失败
        vectorization_filters["vectorization_status"] = 2
        failed_articles = article_repo.get_articles(page=1, per_page=1, filters=vectorization_filters)["total"]
        
        # 处理中
        vectorization_filters["vectorization_status"] = 3
        processing_articles = article_repo.get_articles(page=1, per_page=1, filters=vectorization_filters)["total"]
        
        # 计算待处理数量
        pending_articles = all_articles - vectorized_articles - failed_articles - processing_articles
        
        # 计算向量化比例
        vectorization_rate = (vectorized_articles / all_articles * 100) if all_articles > 0 else 0
        
        # 获取最近5个向量化任务
        recent_tasks = task_repo.get_all_tasks(page=1, per_page=5)["list"]
        
        # 构建统计结果
        statistics = {
            "total_articles": all_articles,
            "vectorized_articles": vectorized_articles,
            "failed_articles": failed_articles,
            "processing_articles": processing_articles,
            "pending_articles": pending_articles,
            "vectorization_rate": round(vectorization_rate, 2),
            "recent_tasks": recent_tasks,
            "feed_id": feed_id
        }
        
        # 获取向量存储信息（可选）
        try:
            vectorization_service = ArticleVectorizationService(
                article_repo=article_repo,
                content_repo=content_repo,
                task_repo=task_repo
            )
            
            # 获取向量存储信息
            vector_store_info = vectorization_service.get_vectorization_statistics()
            
            # 添加向量存储信息
            statistics["vector_store"] = vector_store_info
        except Exception as store_err:
            logger.warning(f"获取向量存储信息失败: {str(store_err)}")
        
        return success_response(statistics)
    except Exception as e:
        logger.error(f"获取向量化统计信息失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取向量化统计信息失败: {str(e)}")