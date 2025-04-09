import logging
import uuid
from datetime import datetime

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

@sync_bp.route("/sync_feed_articles", methods=["POST"])
@auth_required
def sync_feed_articles():
    """同步单个Feed的文章，并记录同步日志"""
    try:
        # 获取请求数据
        data = request.get_json()
        feed_id = data.get("feed_id")
        
        if not feed_id:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        sync_log_repo = RssSyncLogRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 生成同步ID
        sync_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # 获取Feed信息
        err, feed = feed_repo.get_feed_by_id(feed_id)
        if err:
            return error_response(PARAMETER_ERROR, f"获取Feed信息失败: {err}")
        
        # 创建初始同步日志
        log_data = {
            "sync_id": sync_id,
            "total_feeds": 1,
            "synced_feeds": 0,
            "failed_feeds": 0,
            "total_articles": 0,
            "status": 0,  # 进行中
            "start_time": start_time,
            "triggered_by": "manual",
            "details": {
                "feeds": [{
                    "feed_id": feed_id,
                    "feed_title": feed.get("title", "未知Feed"),
                    "status": "pending"
                }]
            }
        }
        
        sync_log_repo.create_log(log_data)
        
        try:
            # 同步文章
            result = article_service.sync_feed_articles(feed_id)
            
            # 计算同步耗时
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            
            # 更新同步日志为成功
            sync_log_repo.update_log(sync_id, {
                "synced_feeds": 1,
                "failed_feeds": 0,
                "total_articles": result.get("total", 0),
                "status": 1,  # 成功
                "end_time": end_time,
                "total_time": total_time,
                "details": {
                    "feeds": [{
                        "feed_id": feed_id,
                        "feed_title": feed.get("title", "未知Feed"),
                        "status": "success",
                        "articles_count": result.get("total", 0),
                        "sync_time": total_time
                    }]
                }
            })
            
            result["sync_id"] = sync_id
            return success_response(result, "同步成功")
            
        except Exception as e:
            # 计算同步耗时
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            
            # 更新同步日志为失败
            sync_log_repo.update_log(sync_id, {
                "synced_feeds": 0,
                "failed_feeds": 1,
                "status": 2,  # 失败
                "end_time": end_time,
                "total_time": total_time,
                "error_message": str(e),
                "details": {
                    "feeds": [{
                        "feed_id": feed_id,
                        "feed_title": feed.get("title", "未知Feed"),
                        "status": "failed",
                        "error": str(e),
                        "sync_time": total_time
                    }]
                }
            })
            
            raise  # 重新抛出异常
            
    except Exception as e:
        logger.error(f"同步Feed文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"同步Feed文章失败: {str(e)}")

@sync_bp.route("/batch_sync_articles", methods=["POST"])
@auth_required
def batch_sync_articles():
    """批量同步多个Feed的文章，并记录同步日志"""
    try:
        # 获取请求数据
        data = request.get_json()

        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        feed_ids = data.get("feed_ids", [])
        
        if not feed_ids:
            return error_response(PARAMETER_ERROR, "缺少feed_ids参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        feed_repo = RssFeedRepository(db_session)
        sync_log_repo = RssSyncLogRepository(db_session)
        
        # 生成同步ID
        sync_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # 获取要同步的Feed列表信息
        feeds_info = []
        for feed_id in feed_ids:
            err, feed = feed_repo.get_feed_by_id(feed_id)
            if not err and feed:
                feeds_info.append({
                    "feed_id": feed_id,
                    "feed_title": feed.get("title", "未知Feed"),
                    "status": "pending"
                })
        
        # 创建初始同步日志
        log_data = {
            "sync_id": sync_id,
            "total_feeds": len(feed_ids),
            "synced_feeds": 0,
            "failed_feeds": 0,
            "total_articles": 0,
            "status": 0,  # 进行中
            "start_time": start_time,
            "triggered_by": "manual",
            "details": {
                "feeds": feeds_info
            }
        }
        
        sync_log_repo.create_log(log_data)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        
        # 批量同步文章
        result = article_service.batch_sync_articles(feed_ids)
        
        # 计算同步耗时
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # 处理结果数据以更新日志
        feed_details = []
        total_articles = 0
        
        for feed_id, details in result.get("details", {}).items():
            feed_title = next((f.get("feed_title") for f in feeds_info if f.get("feed_id") == feed_id), "未知Feed")
            status = details.get("status")
            articles_count = details.get("total", 0) if status == "success" else 0
            total_articles += articles_count
            
            feed_details.append({
                "feed_id": feed_id,
                "feed_title": feed_title,
                "status": status,
                "articles_count": articles_count,
                "error": details.get("message") if status == "failed" else None,
                "sync_time": total_time / len(feed_ids)  # 平均时间，实际上每个Feed的时间可能不同
            })
        
        # 更新同步日志
        sync_log_repo.update_log(sync_id, {
            "synced_feeds": result.get("success", 0),
            "failed_feeds": result.get("failed", 0),
            "total_articles": total_articles,
            "status": 1 if result.get("failed", 0) == 0 else 2,  # 如果有失败则整体标记为失败
            "end_time": end_time,
            "total_time": total_time,
            "error_message": f"{result.get('failed', 0)}个Feed同步失败" if result.get("failed", 0) > 0 else None,
            "details": {
                "feeds": feed_details
            }
        })
        
        # 添加同步ID到返回结果
        result["sync_id"] = sync_id
        result["total_time"] = total_time
        result["total_articles"] = total_articles
        
        return success_response(result, "批量同步完成")
    except Exception as e:
        logger.error(f"批量同步Feed文章失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"批量同步Feed文章失败: {str(e)}")
@sync_bp.route("/sync_log_list", methods=["GET"])
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

@sync_bp.route("/sync_log_detail", methods=["GET"])
@auth_required
def get_sync_log_detail():
    """获取RSS同步日志详情
    
    Args:
        sync_id: 同步任务ID
    
    Returns:
        同步日志详情
    """
 
    try:
        # 创建数据库会话
        db_session = get_db_session()
        sync_id = request.args.get("sync_id")
        if not sync_id:
            return error_response(PARAMETER_ERROR, "缺少sync_id参数")
        print(f"获取同步日志详情: 同步ID={sync_id}")
        
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

@sync_bp.route("/sync_log_stats", methods=["GET"])
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