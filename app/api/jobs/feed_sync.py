# app/api/jobs/feed_sync.py
"""Feed同步任务API接口"""
import logging
import uuid
import socket
from datetime import datetime, timedelta
from flask import Blueprint, request, current_app
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session

# 仓库导入
from app.infrastructure.database.repositories.rss.rss_feed_repository import RssFeedRepository
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss.rss_sync_log_repository import RssSyncLogRepository

logger = logging.getLogger(__name__)

# 创建Feed同步任务蓝图
feed_sync_jobs_bp = Blueprint("feed_sync_jobs", __name__)

@feed_sync_jobs_bp.route("/pending_feeds", methods=["GET"])
@app_key_required
def pending_feeds():
    """获取待同步的Feed列表
    
    改进逻辑:
    1. 30分钟内成功过的不再获取
    2. 连续失败20次的源自动关闭
    3. 失败次数越少的优先级越高
    
    Args:
        limit: 获取数量，默认1
        crawler_id: 爬虫标识，可选
        skip_recent_success: 是否跳过最近成功的，默认True
        success_interval_minutes: 成功间隔分钟数，默认30
    
    Returns:
        待同步Feed列表
    """
    try:
        # 获取请求参数
        limit = request.args.get("limit", 1, type=int)
        skip_recent_success = request.args.get("skip_recent_success", True, type=bool)
        success_interval_minutes = request.args.get("success_interval_minutes", 30, type=int)
        
        # 获取爬虫标识
        crawler_id = request.headers.get("X-Crawler-ID") or socket.gethostname()
        
        print(f"[Feed同步] 获取待同步Feed，limit={limit}, crawler_id={crawler_id}, skip_recent_success={skip_recent_success}")
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        
        # 首先处理连续失败过多的Feed（自动关闭）
        disabled_feeds = feed_repo.auto_disable_failed_feeds(max_failures=20)
        if disabled_feeds:
            print(f"[Feed同步] 自动关闭了 {len(disabled_feeds)} 个连续失败的Feed")
            logger.info(f"自动关闭了 {len(disabled_feeds)} 个连续失败的Feed: {[f['id'] for f in disabled_feeds]}")
        
        # 获取待同步的Feed（按改进的逻辑筛选）
        feeds = feed_repo.get_feeds_for_sync_improved(
            limit=limit,
            skip_recent_success=skip_recent_success,
            success_interval_minutes=success_interval_minutes
        )
        
        print(f"[Feed同步] 找到 {len(feeds)} 个待同步Feed")
        
        # 为每个Feed添加优先级信息
        for feed in feeds:
            print(f"[Feed同步] Feed {feed['id']}: 连续失败{feed.get('consecutive_failures', 0)}次, "
                  f"优先级{feed.get('sync_priority', 0)}, "
                  f"最后成功: {feed.get('last_successful_sync_at', '从未')}")
        
        return success_response({
            "feeds": feeds,
            "crawler_id": crawler_id,
            "disabled_feeds_count": len(disabled_feeds) if disabled_feeds else 0,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取待同步Feed失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取待同步Feed失败: {str(e)}")

@feed_sync_jobs_bp.route("/claim_feed", methods=["POST"])
@app_key_required
def claim_feed():
    """认领Feed进行同步
    
    请求参数:
        {
            "feed_id": "feed123",
            "crawler_id": "crawler_xxx"
        }
    
    Returns:
        认领结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "feed_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        feed_id = data["feed_id"]
        
        # 获取爬虫标识
        crawler_id = request.headers.get("X-Crawler-ID") or data.get("crawler_id") or socket.gethostname()
        
        print(f"[Feed同步] 认领Feed: {feed_id}, crawler_id: {crawler_id}")
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        
        # 获取Feed详情
        err, feed = feed_repo.get_feed_by_id(feed_id)
        if err:
            return error_response(PARAMETER_ERROR, f"获取Feed失败: {err}")
        
        if not feed:
            return error_response(PARAMETER_ERROR, "Feed不存在")
        
        # 检查Feed状态
        if not feed.get("is_active", False):
            return error_response(PARAMETER_ERROR, "Feed未激活")
        
        # 检查是否被连续失败过多次关闭
        consecutive_failures = feed.get("consecutive_failures", 0)
        if consecutive_failures >= 20:
            # 自动关闭该Feed
            feed_repo.update_feed_status(feed_id, False)
            logger.warning(f"Feed {feed_id} 连续失败{consecutive_failures}次，已自动关闭")
            return error_response(PARAMETER_ERROR, f"Feed连续失败{consecutive_failures}次，已被自动关闭")
        
        # 标记Feed正在同步（更新last_sync_started_at字段）
        update_result = feed_repo.mark_feed_syncing(feed_id, crawler_id)
        if not update_result:
            return error_response(PARAMETER_ERROR, "标记Feed同步状态失败，可能已被其他爬虫认领")
        
        print(f"[Feed同步] 成功认领Feed: {feed_id}")
        
        return success_response({
            "feed": feed,
            "crawler_id": crawler_id,
            "consecutive_failures": consecutive_failures,
            "claimed_at": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"认领Feed失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"认领Feed失败: {str(e)}")

@feed_sync_jobs_bp.route("/submit_feed_result", methods=["POST"])
@app_key_required
def submit_feed_result():
    """提交Feed同步结果
    
    请求参数:
        {
            "feed_id": "feed123",
            "status": 1,  // 1=成功, 2=失败
            "articles": [  // 成功时的文章列表
                {
                    "title": "文章标题",
                    "link": "文章链接",
                    "summary": "文章摘要",
                    "published_date": "2024-01-01T12:00:00",
                    "thumbnail_url": "缩略图URL"
                }
            ],
            "error_message": "错误信息",  // 失败时的错误信息
            "error_type": "network_error", // 错误类型
            "fetch_time": 5.2,  // 获取耗时
            "parse_time": 1.1,   // 解析耗时
            "total_time": 6.3,   // 总耗时
            "feed_url": "RSS地址",
            "response_status": 200,  // HTTP状态码
            "content_length": 12345, // 响应内容长度
            "entries_found": 10,     // 发现的条目数
            "new_articles": 5        // 新增文章数
        }
    
    Returns:
        提交结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or "feed_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        feed_id = data["feed_id"]
        status = data.get("status", 2)  # 默认失败
        
        # 获取爬虫标识
        crawler_id = request.headers.get("X-Crawler-ID") or data.get("crawler_id") or socket.gethostname()
        
        print(f"[Feed同步] 提交Feed同步结果: {feed_id}, status: {status}")
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)
        sync_log_repo = RssSyncLogRepository(db_session)
        
        # 生成同步ID
        sync_id = str(uuid.uuid4())
        
        try:
            # 如果同步成功，处理文章数据
            new_articles_count = 0
            if status == 1 and data.get("articles"):
                articles = data["articles"]
                print(f"[Feed同步] 处理 {len(articles)} 篇文章")
                
                # 准备文章数据
                articles_to_insert = []
                for article_data in articles:
                    try:
                        # 处理发布日期
                        published_date = article_data.get("published_date")
                        if isinstance(published_date, str):
                            published_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
                        elif not published_date:
                            published_date = datetime.now()
                        
                        # 获取Feed信息
                        err, feed = feed_repo.get_feed_by_id(feed_id)
                        if err:
                            continue
                        
                        # 构建文章数据
                        article = {
                            "feed_id": feed_id,
                            "feed_logo": feed.get("logo"),
                            "feed_title": feed.get("title"),
                            "link": article_data.get("link"),
                            "title": article_data.get("title"),
                            "summary": article_data.get("summary", ""),
                            "thumbnail_url": article_data.get("thumbnail_url"),
                            "status": 0,  # 待抓取
                            "published_date": published_date,
                        }
                        articles_to_insert.append(article)
                    except Exception as e:
                        logger.error(f"处理文章数据失败: {str(e)}")
                        continue
                
                # 批量插入文章
                if articles_to_insert:
                    success = article_repo.insert_articles(articles_to_insert)
                    if success:
                        new_articles_count = len(articles_to_insert)
                        print(f"[Feed同步] 成功插入 {new_articles_count} 篇新文章")
                    else:
                        print(f"[Feed同步] 插入文章失败")
                        status = 2  # 标记为失败
            
            # 更新Feed同步状态（改进的逻辑）
            feed_update_data = {
                "last_sync_status": status,
                "last_sync_at": datetime.now(),
                "last_sync_crawler_id": None  # 清除爬虫锁定
            }
            
            if status == 1:
                # 成功时
                feed_update_data.update({
                    "last_successful_sync_at": datetime.now(),
                    "consecutive_failures": 0,  # 重置连续失败次数
                    "last_sync_error": None,
                    "sync_success_count": data.get("new_articles", new_articles_count),
                    "total_sync_success": 1  # 增加成功次数（在仓库中处理）
                })
            else:
                # 失败时
                error_message = data.get("error_message", "同步失败")
                error_type = data.get("error_type", "unknown")
                
                feed_update_data.update({
                    "last_sync_error": error_message,
                    "error_type": error_type,
                    "consecutive_failures_increment": 1,  # 增加连续失败次数（在仓库中处理）
                    "total_sync_failures": 1  # 增加失败次数（在仓库中处理）
                })
            
            # 执行更新
            feed_repo.update_feed_sync_status_improved(feed_id, feed_update_data)
            
            # 获取更新后的Feed信息，用于日志记录
            err, updated_feed = feed_repo.get_feed_by_id(feed_id)
            consecutive_failures = updated_feed.get("consecutive_failures", 0) if not err else 0
            
            # 检查是否需要自动关闭Feed
            auto_disabled = False
            if status == 2 and consecutive_failures >= 20:
                feed_repo.update_feed_status(feed_id, False)
                auto_disabled = True
                logger.warning(f"Feed {feed_id} 连续失败{consecutive_failures}次，已自动关闭")
            
            # 记录同步日志
            log_data = {
                "sync_id": sync_id,
                "feed_id": feed_id,
                "crawler_id": crawler_id,
                "status": status,
                "started_at": datetime.now() - timedelta(seconds=data.get("total_time", 0)),
                "ended_at": datetime.now(),
                "total_time": data.get("total_time"),
                "fetch_time": data.get("fetch_time"),
                "parse_time": data.get("parse_time"),
                "feed_url": data.get("feed_url"),
                "response_status": data.get("response_status"),
                "content_length": data.get("content_length"),
                "entries_found": data.get("entries_found"),
                "new_articles": new_articles_count,
                "error_message": data.get("error_message"),
                "triggered_by": "crawler",
                "details": {
                    "crawler_host": data.get("crawler_host"),
                    "crawler_ip": data.get("crawler_ip"),
                    "user_agent": data.get("user_agent"),
                    "memory_usage": data.get("memory_usage"),
                    "cpu_usage": data.get("cpu_usage"),
                    "error_type": data.get("error_type"),
                    "consecutive_failures": consecutive_failures,
                    "auto_disabled": auto_disabled
                }
            }
            
            # 创建日志记录
            sync_log_repo.create_single_feed_log(log_data)
            
            result_message = "同步完成"
            if status == 1:
                result_message = f"同步成功，新增 {new_articles_count} 篇文章"
            elif auto_disabled:
                result_message = f"同步失败，连续失败{consecutive_failures}次，Feed已被自动关闭"
            else:
                result_message = f"同步失败，连续失败{consecutive_failures}次"
            
            print(f"[Feed同步] Feed {feed_id} {result_message}")
            
            return success_response({
                "sync_id": sync_id,
                "feed_id": feed_id,
                "status": status,
                "new_articles": new_articles_count,
                "consecutive_failures": consecutive_failures,
                "auto_disabled": auto_disabled,
                "message": result_message
            })
            
        except Exception as e:
            # 发生异常时，确保清除Feed的爬虫锁定
            try:
                feed_repo.update_feed_sync_status(feed_id, {
                    "last_sync_status": 2,
                    "last_sync_at": datetime.now(),
                    "last_sync_error": f"处理异常: {str(e)}",
                    "last_sync_crawler_id": None,
                    "consecutive_failures_increment": 1
                })
            except:
                pass
            
            raise e
    except Exception as e:
        logger.error(f"提交Feed同步结果失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"提交Feed同步结果失败: {str(e)}")

@feed_sync_jobs_bp.route("/feed_sync_stats", methods=["GET"])
@app_key_required
def get_feed_sync_stats():
    """获取Feed同步统计信息
    
    Returns:
        统计信息
    """
    try:
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        sync_log_repo = RssSyncLogRepository(db_session)
        
        # 获取统计信息
        stats = {
            "total_feeds": feed_repo.count_active_feeds(),
            "pending_feeds": feed_repo.count_pending_sync_feeds(),
            "syncing_feeds": feed_repo.count_syncing_feeds(),
            "recent_success": sync_log_repo.count_recent_successful_syncs(),
            "recent_failures": sync_log_repo.count_recent_failed_syncs(),
            # 新增统计
            "feeds_near_disable": feed_repo.count_feeds_near_disable(threshold=15),  # 连续失败15次以上的
            "recently_disabled_feeds": feed_repo.count_recently_disabled_feeds(hours=24),  # 24小时内被关闭的
            "high_failure_feeds": feed_repo.count_high_failure_feeds(min_failures=10)  # 连续失败10次以上的
        }
        
        return success_response(stats)
    except Exception as e:
        logger.error(f"获取Feed同步统计失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取Feed同步统计失败: {str(e)}")

@feed_sync_jobs_bp.route("/reset_feed_failures", methods=["POST"])
@app_key_required
def reset_feed_failures():
    """重置Feed的失败计数（管理员操作）
    
    请求参数:
        {
            "feed_id": "feed123",  // 可选，如果不提供则重置所有
            "reactivate": true     // 是否重新激活被关闭的Feed
        }
    
    Returns:
        重置结果
    """
    try:
        data = request.get_json() or {}
        feed_id = data.get("feed_id")
        reactivate = data.get("reactivate", False)
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        
        if feed_id:
            # 重置特定Feed
            result = feed_repo.reset_feed_failures(feed_id, reactivate)
            print(f"[Feed同步] 重置Feed {feed_id} 的失败计数")
        else:
            # 重置所有Feed
            result = feed_repo.reset_all_feed_failures(reactivate)
            print(f"[Feed同步] 重置所有Feed的失败计数")
        
        return success_response(result)
    except Exception as e:
        logger.error(f"重置Feed失败计数失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"重置Feed失败计数失败: {str(e)}")