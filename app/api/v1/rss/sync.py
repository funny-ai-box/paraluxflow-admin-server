import logging

from app.core.status_codes import PARAMETER_ERROR
from app.domains.rss.services.sync_service import SyncService
from app.infrastructure.database.repositories.rss_sync_log_repository import RssSyncLogRepository
from flask import Blueprint, request, Response
from urllib.parse import unquote

from app.api.middleware.auth import auth_required
from app.core.responses import error_response, success_response
from app.infrastructure.database.session import get_db_session

from app.infrastructure.database.repositories.rss_feed_repository import RssFeedRepository
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss_article_content_repository import RssFeedArticleContentRepository
from app.domains.rss.services.article_service import ArticleService

logger = logging.getLogger(__name__)
sync_bp = Blueprint("sync", __name__)

@sync_bp.route("/sync", methods=["POST"])
@auth_required
def sync_feed_articles():
    try:
        # 获取请求数据
        data = request.get_json()
        feed_id = data.get("feed_id")
        
        if not feed_id:
            return success_response(None, "缺少feed_id参数", 60001)
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 同步文章
        result = article_service.sync_feed_articles(feed_id)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"同步Feed文章失败: {str(e)}")
        return error_response(60001, f"同步Feed文章失败: {str(e)}")

@sync_bp.route("/batch_sync", methods=["POST"])
@auth_required
def batch_sync_articles():
    try:
        # 获取请求数据
        data = request.get_json()

        if not data:
            return error_response(60001, "未提供数据")
        feed_ids = data.get("feed_ids", [])
        
        if not feed_ids:
            return error_response(60001, "缺少feed_ids参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 批量同步文章
        result = article_service.batch_sync_articles(feed_ids)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"批量同步Feed文章失败: {str(e)}")
        return error_response(60001, f"批量同步Feed文章失败: {str(e)}")
    
@sync_bp.route("/list", methods=["GET"])
@auth_required
def get_sync_logs():
    """获取RSS同步日志列表
    
    Args:
        page: 页码，默认1
        per_page: 每页数量，默认20
        status: 状态筛选，可选值: 0(进行中), 1(已完成), 2(失败)
        triggered_by: 触发方式筛选，可选值: schedule, manual
        start_date: 开始日期筛选，格式: YYYY-MM-DD
        end_date: 结束日期筛选，格式: YYYY-MM-DD
    
    Returns:
        同步日志列表
    """
    print("\n===== 获取RSS同步日志列表 =====")
    try:
        # 获取分页参数
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        print(f"分页参数: page={page}, per_page={per_page}")
        
        # 获取筛选参数
        status = request.args.get("status", type=int)
        triggered_by = request.args.get("triggered_by")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        
        # 构建筛选条件
        filters = {}
        if status is not None:
            filters["status"] = status
        if triggered_by:
            filters["triggered_by"] = triggered_by
        if start_date or end_date:
            filters["date_range"] = (start_date, end_date)
        
        print(f"筛选条件: {filters}")
        
        # 创建数据库会话
        db_session = get_db_session()
        
        # 创建仓库
        sync_log_repo = RssSyncLogRepository(db_session)
        
        # 获取日志列表
        logs = sync_log_repo.get_logs(page, per_page, filters)
        print(f"获取到 {len(logs['list'])} 条日志记录，总计 {logs['total']} 条")
        
        return success_response(logs, "获取同步日志成功")
    except Exception as e:
        error_msg = f"获取同步日志失败: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        return error_response(PARAMETER_ERROR, error_msg)

@sync_bp.route("/detail/<string:sync_id>", methods=["GET"])
@auth_required
def get_sync_log_detail(sync_id):
    """获取RSS同步日志详情
    
    Args:
        sync_id: 同步任务ID
    
    Returns:
        同步日志详情
    """
    print(f"\n===== 获取RSS同步日志详情 [ID: {sync_id}] =====")
    try:
        # 创建数据库会话
        db_session = get_db_session()
        
        # 创建仓库
        sync_log_repo = RssSyncLogRepository(db_session)
        
        # 获取日志详情
        err, log = sync_log_repo.get_log_by_sync_id(sync_id)
        if err:
            print(f"获取日志详情失败: {err}")
            return error_response(PARAMETER_ERROR, err)
        
        print(f"获取日志详情成功: 同步ID={log['sync_id']}, 状态={log['status']}")
        
        return success_response(log, "获取同步日志详情成功")
    except Exception as e:
        error_msg = f"获取同步日志详情失败: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        return error_response(PARAMETER_ERROR, error_msg)

@sync_bp.route("/stats", methods=["GET"])
@auth_required
def get_sync_logs_stats():
    """获取RSS同步统计信息
    
    Returns:
        同步统计信息
    """
    print("\n===== 获取RSS同步统计信息 =====")
    try:
        # 创建数据库会话
        db_session = get_db_session()
        
        # 创建仓库
        sync_log_repo = RssSyncLogRepository(db_session)
        
        # 获取最近10次同步记录(不包含详情)
        logs_result = sync_log_repo.get_logs(page=1, per_page=10)
        recent_logs = logs_result.get("list", [])
        
        # 计算统计信息
        total_syncs = logs_result.get("total", 0)
        
        # 计算平均指标
        total_articles = 0
        total_time = 0
        successful_syncs = 0
        failed_syncs = 0
        ongoing_syncs = 0
        
        for log in recent_logs:
            status = log.get("status")
            if status == 0:  # 进行中
                ongoing_syncs += 1
            elif status == 1:  # 成功
                successful_syncs += 1
                total_articles += log.get("total_articles", 0)
                total_time += log.get("total_time", 0)
            elif status == 2:  # 失败
                failed_syncs += 1
        
        avg_articles = total_articles / successful_syncs if successful_syncs > 0 else 0
        avg_time = total_time / successful_syncs if successful_syncs > 0 else 0
        
        stats = {
            "total_syncs": total_syncs,
            "successful_syncs": successful_syncs,
            "failed_syncs": failed_syncs,
            "ongoing_syncs": ongoing_syncs,
            "avg_articles_per_sync": round(avg_articles, 2),
            "avg_time_per_sync": round(avg_time, 2),
            "recent_logs": recent_logs[:5]  # 只返回最近5条记录
        }
        
        print(f"统计信息: 总同步次数={total_syncs}, 成功={successful_syncs}, 失败={failed_syncs}, 进行中={ongoing_syncs}")
        
        return success_response(stats, "获取同步统计信息成功")
    except Exception as e:
        error_msg = f"获取同步统计信息失败: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        return error_response(PARAMETER_ERROR, error_msg)

@sync_bp.route("/trigger", methods=["POST"])
@auth_required
def trigger_sync():
    """手动触发RSS同步
    
    Returns:
        触发结果
    """
    print("\n===== 手动触发RSS同步 =====")
    try:
        # 创建数据库会话
        db_session = get_db_session()
        

        
        # 创建仓库
        feed_repo = RssFeedRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        sync_log_repo = RssSyncLogRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        sync_service = SyncService(feed_repo, article_service, sync_log_repo)
        
        # 触发同步(手动模式)
        result = sync_service.sync_all_active_feeds(triggered_by="manual")
        
        print(f"手动触发RSS同步完成: 同步ID={result['sync_id']}")
        
        return success_response({
            "sync_id": result["sync_id"],
            "total_feeds": result["total_feeds"],
            "synced_feeds": result["synced_feeds"],
            "failed_feeds": result["failed_feeds"],
            "total_articles": result["total_articles"],
            "total_time": result["total_time"]
        }, "同步触发成功")
    except Exception as e:
        error_msg = f"触发同步失败: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        return error_response(PARAMETER_ERROR, error_msg)