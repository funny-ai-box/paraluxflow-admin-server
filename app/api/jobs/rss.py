# app/api/jobs/rss.py
"""RSS源同步任务API接口"""
import logging
from flask import Blueprint, request, current_app
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session

# 仓库导入
from app.infrastructure.database.repositories.rss_feed_repository import RssFeedRepository
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss_article_content_repository import RssFeedArticleContentRepository

# 服务导入
from app.domains.rss.services.article_service import ArticleService
from app.domains.rss.services.sync_service import SyncService

logger = logging.getLogger(__name__)

# 创建RSS任务蓝图
rss_jobs_bp = Blueprint("rss_jobs", __name__)

@rss_jobs_bp.route("/sync_all", methods=["POST"])
@app_key_required
def sync_all_feeds():
    """同步所有激活状态的RSS源文章
    
    该API由定时任务调用，定期同步所有激活的RSS源
    
    Returns:
        同步结果
    """
    try:
        # 创建数据库会话
        db_session = get_db_session()
        
        # 创建仓库
        feed_repo = RssFeedRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        
        # 创建服务
        article_service = ArticleService(article_repo, content_repo, feed_repo)
        sync_service = SyncService(feed_repo, article_service)
        
        # 同步所有激活的Feed
        result = sync_service.sync_all_active_feeds()
        
        # 记录同步结果
        logger.info(f"RSS源同步完成: 成功同步{result['synced_feeds']}个源，失败{result['failed_feeds']}个源，共{result['total_articles']}篇文章，耗时{result['total_time']}秒")
        
        return success_response(result, "同步完成")
    except Exception as e:
        logger.error(f"RSS源同步失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"同步失败: {str(e)}")