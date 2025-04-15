# app/api/jobs/rss.py
"""RSS源同步任务API接口"""
import logging
import threading
from app.infrastructure.database.session import get_db_session
from flask import Blueprint, request, current_app
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.extensions import db  # 导入 SQLAlchemy 实例
import uuid

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

def run_sync_task(app_config, triggered_by="schedule"):
    """在单独的线程中运行同步任务
    
    Args:
        app_config: 应用配置
        triggered_by: 触发方式
    """
    print("\n===== 异步RSS同步任务开始 =====")
    
    # 使用独立的数据库会话
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, scoped_session
    
    try:
        # 从配置中获取数据库 URL
        db_url = app_config.get("SQLALCHEMY_DATABASE_URI")
        print(f"创建数据库引擎，URL: {db_url[:20]}...")
        
        # 创建引擎和会话
        engine = create_engine(db_url)
        session_factory = sessionmaker(bind=engine)
        db_session = scoped_session(session_factory)()
        
        print("异步任务数据库会话创建成功")
        
        # 创建仓库
        feed_repo = RssFeedRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        sync_log_repo = RssSyncLogRepository(db_session)
        print("异步任务仓库初始化完成")
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        sync_service = SyncService(feed_repo, article_service, sync_log_repo)
        print("异步任务服务初始化完成")
        
        # 生成同步ID
        sync_id = str(uuid.uuid4())
        
        # 同步所有激活的Feed
        print(f"异步任务开始执行同步，同步ID: {sync_id}")
        result = sync_service.sync_all_active_feeds(triggered_by)
        
        # 记录同步结果
        logger.info(f"异步RSS源同步完成: 成功同步{result['synced_feeds']}个源，失败{result['failed_feeds']}个源，共{result['total_articles']}篇文章，耗时{result['total_time']}秒")
        print(f"异步RSS源同步完成: 成功同步{result['synced_feeds']}个源，失败{result['failed_feeds']}个源，共{result['total_articles']}篇文章，耗时{result['total_time']}秒")
    except Exception as e:
        error_msg = f"异步RSS源同步失败: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        import traceback
        print(traceback.format_exc())  # 打印完整堆栈跟踪
    finally:
        # 确保会话在任务结束时关闭
        if 'db_session' in locals():
            db_session.close()
            print("异步任务数据库会话已关闭")
        print("===== 异步RSS同步任务结束 =====")

@rss_jobs_bp.route("/sync_all", methods=["POST"])
@app_key_required
def sync_all_feeds():
    """异步同步所有激活状态的RSS源文章
    
    该API由定时任务调用，定期同步所有激活的RSS源
    同步任务将在后台线程中执行，API立即返回任务已启动
    
    Returns:
        任务启动结果
    """
    print("\n===== RSS同步任务API触发 =====")
    try:
        # 获取触发方式
        data = request.get_json() or {}
        triggered_by = data.get("triggered_by", "schedule")
        print(f"触发方式: {triggered_by}")
        
        # 创建一个同步ID（实际实现可以记录到数据库中以便查询进度）
        sync_id = str(uuid.uuid4())
        
        # 获取应用程序配置的副本，以便传递给异步任务
        app_config = current_app.config.copy()
        
        # 创建一个线程来执行同步任务
        sync_thread = threading.Thread(
            target=run_sync_task,
            args=(app_config, triggered_by),
            daemon=True  # 设置为守护线程，这样主程序退出时不会被阻塞
        )
        
        # 启动线程
        sync_thread.start()
        print(f"同步任务已在后台启动，线程ID: {sync_thread.ident}")
        
        # 立即返回结果
        return success_response({
            "sync_id": sync_id,
            "status": "started",
            "message": "同步任务已在后台启动",
            "triggered_by": triggered_by
        }, "同步任务已开始")
    except Exception as e:
        error_msg = f"启动RSS源同步任务失败: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        return error_response(PARAMETER_ERROR, error_msg)

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
    # 此函数保持不变
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
        
        return success_response(logs, "获取同步日志成功")
    except Exception as e:
        error_msg = f"获取同步日志失败: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        return error_response(PARAMETER_ERROR, error_msg)