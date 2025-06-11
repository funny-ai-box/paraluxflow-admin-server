# app/api/jobs/daily_summary.py
"""RSS每日摘要任务API接口，供外部定时调用"""
import logging
import uuid
from datetime import datetime, date, timedelta
from flask import Blueprint, request, current_app, jsonify
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, SUCCESS
from app.infrastructure.database.session import get_db_session

# 仓库导入
from app.infrastructure.database.repositories.rss.rss_daily_summary_repository import RssFeedDailySummaryRepository
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss.rss_feed_repository import RssFeedRepository

# 服务导入
from app.domains.rss.services.daily_summary_service import DailySummaryService

logger = logging.getLogger(__name__)

# 创建每日摘要任务蓝图
daily_summary_jobs_bp = Blueprint("daily_summary_jobs", __name__)

@daily_summary_jobs_bp.route("/get_feeds_needing_summary", methods=["GET"])
@app_key_required
def get_feeds_needing_summary():
    """获取需要生成摘要的Feed列表
    
    请求参数:
        target_date: 目标日期，可选，默认昨天 (YYYY-MM-DD格式)
        language: 语言，可选，默认中文 (zh/en)
        worker_id: worker标识，可选
        
    返回:
        需要生成摘要的Feed列表
    """
    try:
        # 获取请求参数
        target_date_str = request.args.get("target_date")
        language = request.args.get("language", "zh")
        worker_id = request.args.get("worker_id", "unknown")
        
        # 解析日期
        if target_date_str:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        else:
            target_date = date.today() - timedelta(days=1)
        
        # 创建会话和存储库
        db_session = get_db_session()
        summary_repo = RssFeedDailySummaryRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        logger.info(f"Worker {worker_id} 请求获取 {target_date} {language} 待生成摘要的Feed列表")
        
        # 获取需要生成摘要的Feed列表
        feed_ids = summary_repo.get_feeds_needing_summary(target_date, language)
        
        # 获取Feed详细信息
        feeds_info = []
        for feed_id in feed_ids:
            err, feed = feed_repo.get_feed_by_id(feed_id)
            if not err and feed:
                feeds_info.append({
                    "feed_id": feed_id,
                    "title": feed.get("title"),
                    "description": feed.get("description"),
                    "logo": feed.get("logo")
                })
        
        return success_response({
            "target_date": target_date.isoformat(),
            "language": language,
            "feeds": feeds_info,
            "total_count": len(feeds_info),
            "worker_id": worker_id,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"获取待生成摘要Feed列表失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取待生成摘要Feed列表失败: {str(e)}")

@daily_summary_jobs_bp.route("/process_feed_summary", methods=["GET"])
def process_feed_summary():
    """处理单个Feed的摘要生成
    
    请求参数:
        feed_id: Feed ID (必填)
        target_date: 目标日期，可选，默认昨天 (YYYY-MM-DD格式)
        language: 语言，可选，默认中文 (zh/en)
        worker_id: worker标识，可选
        provider_type: LLM提供商，可选
        model: 使用的模型，可选
        
    返回:
        处理结果
    """
    try:
        # 获取请求数据
        feed_id = request.args.get("feed_id")
        if not feed_id:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        target_date_str = request.args.get("target_date")
        language = request.args.get("language", "zh")
        worker_id = request.args.get("worker_id", "unknown")

        
        # 解析日期
        if target_date_str:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        else:
            target_date = date.today() - timedelta(days=1)
        
        # 获取开始时间
        start_time = datetime.now()
        task_id = str(uuid.uuid4())
        
        # 创建会话和存储库
        db_session = get_db_session()
        summary_repo = RssFeedDailySummaryRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        logger.info(f"Worker {worker_id} 开始处理Feed {feed_id} 的 {target_date} {language} 摘要生成，任务ID: {task_id}")
        
        # 检查是否已存在摘要
        existing_summary = summary_repo.get_feed_summary(feed_id, target_date, language)
        if existing_summary:
            logger.warning(f"Feed {feed_id} 在 {target_date} 的 {language} 摘要已存在")
            return success_response({
                "result": existing_summary,
                "task_id": task_id,
                "worker_id": worker_id,
                "feed_id": feed_id,
                "target_date": target_date.isoformat(),
                "language": language,
                "status": 1,  # 成功
                "message": "摘要已存在",
                "processing_time": 0,
                "timestamp": datetime.now().isoformat()
            })
        
        # 创建摘要生成服务
        summary_service = DailySummaryService(summary_repo, article_repo, feed_repo)
        
        # 处理单个Feed摘要生成
        try:
            result = summary_service._generate_feed_summary(feed_id, target_date, language)
            status = 1  # 成功
            error_message = None
            error_type = None
            
            logger.info(f"Worker {worker_id} 成功处理Feed {feed_id} 的 {language} 摘要生成")
            
        except Exception as e:
            logger.error(f"Feed摘要生成处理失败: {str(e)}")
            status = 2  # 失败
            error_message = str(e)
            error_type = type(e).__name__
            result = {"status": "failed", "message": str(e)}
        
        # 计算处理时间
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return success_response({
            "result": result,
            "task_id": task_id,
            "worker_id": worker_id,
            "feed_id": feed_id,
            "target_date": target_date.isoformat(),
            "language": language,
            "status": status,
            "error_message": error_message,
            "error_type": error_type,
            "processing_time": processing_time,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        # 记录详细错误信息
        logger.error(f"处理Feed摘要生成失败: {str(e)}", exc_info=True)
        
        # 返回详细的错误信息
        error_msg = str(e)
        error_code = PARAMETER_ERROR
        
        return error_response(error_code, error_msg)