# app/api/jobs/rss.py (Updated version)
"""RSS源同步任务API接口"""
import logging
import threading
from flask import Blueprint, request, current_app
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session

# 仓库导入
from app.infrastructure.database.repositories.rss_feed_repository import RssFeedRepository
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss_sync_log_repository import RssSyncLogRepository

# 服务导入
from app.domains.rss.services.article_service import ArticleService
from app.domains.rss.services.sync_service import SyncService

logger = logging.getLogger(__name__)

# 创建RSS任务蓝图
rss_jobs_bp = Blueprint("rss_jobs", __name__)

def run_sync_task(triggered_by):
    """在后台线程中运行同步任务
    
    Args:
        triggered_by: 触发方式
    """
    print(f"\n===== 开始后台RSS同步任务 (触发方式: {triggered_by}) =====")
    try:
        # 创建数据库会话 (注意: 后台线程需要新的数据库会话)
        db_session = get_db_session()
        print("后台任务数据库会话创建成功")
        
        # 创建仓库
        feed_repo = RssFeedRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        sync_log_repo = RssSyncLogRepository(db_session)
        print("后台任务仓库初始化完成")
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        sync_service = SyncService(feed_repo, article_service, sync_log_repo)
        print("后台任务服务初始化完成")
        
        # 同步所有激活的Feed
        print("开始执行同步...")
        result = sync_service.sync_all_active_feeds(triggered_by)
        
        # 记录同步结果
        logger.info(f"RSS源同步完成: 成功同步{result['synced_feeds']}个源，失败{result['failed_feeds']}个源，共{result['total_articles']}篇文章，耗时{result['total_time']}秒")
        print(f"RSS源同步完成: 成功同步{result['synced_feeds']}个源，失败{result['failed_feeds']}个源，共{result['total_articles']}篇文章，耗时{result['total_time']}秒")
        
        # 关闭数据库会话
        db_session.close()
        print("后台任务数据库会话已关闭")
        
    except Exception as e:
        error_msg = f"后台RSS源同步任务失败: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        
        # 尝试关闭数据库会话
        try:
            if db_session:
                db_session.close()
                print("后台任务数据库会话已关闭")
        except:
            pass

@rss_jobs_bp.route("/sync_all", methods=["POST"])
@app_key_required
def sync_all_feeds():
    """异步触发同步所有激活状态的RSS源文章
    
    该API由定时任务调用，触发后会立即返回并在后台执行同步
    
    Returns:
        触发结果
    """
    print("\n===== RSS同步任务API触发 =====")
    try:
        # 获取触发方式
        data = request.get_json() or {}
        triggered_by = data.get("triggered_by", "schedule")
        print(f"触发方式: {triggered_by}")
        
        # 创建数据库会话，只用于创建初始同步日志
        db_session = get_db_session()
        
        # 创建同步日志仓库
        sync_log_repo = RssSyncLogRepository(db_session)
        
        # 创建初始同步日志（状态为进行中）
        import uuid
        from datetime import datetime
        
        sync_id = str(uuid.uuid4())
        log_data = {
            "sync_id": sync_id,
            "total_feeds": 0,  # 将在后台任务中更新
            "synced_feeds": 0,
            "failed_feeds": 0,
            "total_articles": 0,
            "status": 0,  # 进行中
            "start_time": datetime.now(),
            "triggered_by": triggered_by,
            "details": {"feeds": []}
        }
        
        err, log = sync_log_repo.create_log(log_data)
        if err:
            print(f"警告: 创建同步日志失败: {err}")
            sync_id = None
        
        # 关闭初始数据库会话
        db_session.close()
        
        # 启动后台线程执行同步任务
        sync_thread = threading.Thread(target=run_sync_task, args=(triggered_by,))
        sync_thread.daemon = True  # 设置为守护线程，避免阻塞主程序退出
        sync_thread.start()
        
        # 返回触发成功响应
        response_data = {
            "sync_id": sync_id,
            "triggered_by": triggered_by,
            "start_time": datetime.now().isoformat(),
            "message": "同步任务已在后台启动，可通过sync_id查询进度"
        }
        
        return success_response(response_data, "同步任务已触发")
    except Exception as e:
        error_msg = f"触发RSS源同步失败: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        return error_response(PARAMETER_ERROR, error_msg)

# 其他路由保持不变
@rss_jobs_bp.route("/sync_logs", methods=["GET"])
@app_key_required
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
    print("\n===== 获取RSS同步日志 =====")
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
        
        # 关闭数据库会话
        db_session.close()
        
        return success_response(logs, "获取同步日志成功")
    except Exception as e:
        error_msg = f"获取同步日志失败: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        return error_response(PARAMETER_ERROR, error_msg)
