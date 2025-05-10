# app/api/client/v1/hot_topics/hot_topics.py
"""客户端热点话题API控制器 (GET/POST only)"""
import logging
from flask import Blueprint, request, g
from datetime import datetime, date

from app.api.middleware.client_auth import client_auth_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, NOT_FOUND
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.hot_topic_repository import HotTopicPlatformRepository, HotTopicRepository, UnifiedHotTopicRepository


from app.domains.hot_topics.services.hot_topic_search_service import HotTopicSearchService
from app.domains.hot_topics.services.hot_topic_platform_service import HotTopicPlatformService
from app.domains.rss.services.vectorization_service import ArticleVectorizationService
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.rss.rss_vectorization_repository import RssFeedArticleVectorizationTaskRepository

# Assuming client_hot_topics_bp is defined in app/api/client/v1/hot_topics/__init__.py
client_hot_topics_bp = Blueprint("client_hot_topics", __name__) # Removed url_prefix

logger = logging.getLogger(__name__)

@client_hot_topics_bp.route("/unified/latest", methods=["GET"])
# @client_auth_required # Decide if auth is needed
def get_latest_unified_hot_topics():
    """获取最新聚合(Unified)的热点话题
    
    查询参数:
    - topic_date: 可选，指定日期 (YYYY-MM-DD). 默认获取最新有数据的日期.
    - page: 页码，默认1
    - per_page: 每页条数，默认20
    
    Returns:
        最新聚合热点话题列表及日期
    """
    try:
        topic_date_str = request.args.get("topic_date")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        db_session = get_db_session()
        unified_topic_repo = UnifiedHotTopicRepository(db_session)
        hot_topic_repo = HotTopicRepository(db_session)

        target_date = None
        if topic_date_str:
            try:
                target_date = date.fromisoformat(topic_date_str)
            except ValueError:
                return error_response(PARAMETER_ERROR, "无效的日期格式，应为YYYY-MM-DD")
        else:
            target_date = unified_topic_repo.get_latest_unified_topic_date()
            if not target_date:
                 return success_response({"list": [], "total": 0, "page": page, "per_page": per_page, "pages": 0, "topic_date": None})

        unified_result = unified_topic_repo.get_unified_topics_by_date(target_date, page, per_page)
        unified_topics_list = unified_result.get("list", [])

        # --- Fetch and attach simplified raw topics ---
        all_related_ids = set()
        for unified_topic in unified_topics_list:
            related_ids = unified_topic.get("related_topic_ids", [])
            if isinstance(related_ids, list):
                all_related_ids.update(related_ids)

        raw_topics_map = {}
        if all_related_ids:
            raw_topics_list = hot_topic_repo.get_topics_by_ids(list(all_related_ids))
            raw_topics_map = {topic["id"]: topic for topic in raw_topics_list}

        for unified_topic in unified_topics_list:
            related_ids = unified_topic.get("related_topic_ids", [])
            raw_topics_simplified = []
            for raw_id in related_ids:
                 raw_topic = raw_topics_map.get(raw_id)
                 if raw_topic:
                      raw_topics_simplified.append({
                           "id": raw_topic["id"], "platform": raw_topic["platform"],
                           "title": raw_topic["topic_title"], "url": raw_topic["topic_url"],
                           "hot_value": raw_topic["hot_value"], "rank": raw_topic["rank"],
                      })
            raw_topics_simplified.sort(key=lambda x: x.get('platform', ''))
            unified_topic["related_raw_topics"] = raw_topics_simplified
            # unified_topic.pop("related_topic_ids", None) # Optional: Remove IDs
        # --- End raw topics logic ---

        final_response_data = {
            "list": unified_topics_list,
            "total": unified_result.get('total', 0),
            "pages": unified_result.get('pages', 0),
            "current_page": page,
            "per_page": per_page,
            "topic_date": target_date.isoformat()
        }
        return success_response(final_response_data)
        
    except Exception as e:
        logger.error(f"获取最新聚合热点话题失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取最新聚合热点话题失败: {str(e)}")

@client_hot_topics_bp.route("/unified/detail", methods=["GET"])
# @client_auth_required # Decide if auth needed
def get_unified_topic_detail():
    """获取聚合(Unified)热点话题详情
    
    查询参数:
    - topic_id: Unified Hot Topic ID (UUID) (Required)
    
    Returns:
        聚合热点详情，包含关联的原始热点信息
    """
    try:
        topic_id = request.args.get("topic_id")
        if not topic_id:
             return error_response(PARAMETER_ERROR, "缺少 topic_id 查询参数")

        db_session = get_db_session()
        unified_topic_repo = UnifiedHotTopicRepository(db_session)
        hot_topic_repo = HotTopicRepository(db_session)

        unified_topic = unified_topic_repo.get_topic_by_id(topic_id)
        if not unified_topic:
             return error_response(NOT_FOUND, f"未找到ID为 {topic_id} 的聚合热点")

        # --- Fetch and attach simplified raw topics ---
        related_ids = unified_topic.get("related_topic_ids", [])
        raw_topics_map = {}
        if isinstance(related_ids, list) and related_ids:
            raw_topics_list = hot_topic_repo.get_topics_by_ids(related_ids)
            raw_topics_map = {topic["id"]: topic for topic in raw_topics_list}

        raw_topics_simplified = []
        for raw_id in related_ids:
             raw_topic = raw_topics_map.get(raw_id)
             if raw_topic:
                 raw_topics_simplified.append({
                     "id": raw_topic["id"], "platform": raw_topic["platform"],
                     "title": raw_topic["topic_title"], "url": raw_topic["topic_url"],
                     "hot_value": raw_topic["hot_value"], "rank": raw_topic["rank"],
                 })
        raw_topics_simplified.sort(key=lambda x: x.get('platform', ''))
        unified_topic["related_raw_topics"] = raw_topics_simplified
        # unified_topic.pop("related_topic_ids", None) # Optional: Remove IDs
        # --- End raw topics logic ---
        
        return success_response(unified_topic)
    except Exception as e:
        logger.error(f"获取聚合热点详情失败 (ID: {topic_id}): {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取聚合热点详情失败: {str(e)}")


@client_hot_topics_bp.route("/unified/related_articles", methods=["GET"])
# @client_auth_required # Decide if auth needed
def get_hot_topic_related_articles():
    """获取与聚合(Unified)热点相关的RSS文章
    
    查询参数:
    - topic_id: Unified Hot Topic ID (UUID) (Required)
    - limit: 返回的最大文章数量，默认5
    - days_range: 查找的最大天数范围 (基于文章发布日期)，默认7
    
    Returns:
        相关文章列表
    """
    try:
        topic_id = request.args.get("topic_id")
        if not topic_id:
             return error_response(PARAMETER_ERROR, "缺少 topic_id 查询参数")
             
        limit = request.args.get("limit", 5, type=int)
        days_range = request.args.get("days_range", 7, type=int)
        
        db_session = get_db_session()
        
        # Instantiate dependencies checking for None
        unified_topic_repo = UnifiedHotTopicRepository(db_session)
        hot_topic_repo = HotTopicRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session) if RssFeedArticleRepository else None
        content_repo = RssFeedArticleContentRepository(db_session) if RssFeedArticleContentRepository else None
        task_repo = RssFeedArticleVectorizationTaskRepository(db_session) if RssFeedArticleVectorizationTaskRepository else None

        if not all([unified_topic_repo, hot_topic_repo, article_repo, content_repo, task_repo, 
                    ArticleVectorizationService, HotTopicSearchService]):
            missing = [name for name, obj in locals().items() if obj is None and name.endswith('_repo')]
            missing.extend([svc.__name__ for svc in [ArticleVectorizationService, HotTopicSearchService] if svc is None])
            raise ImportError(f"相关文章功能配置不完整, 缺少: {', '.join(missing)}")
             
        vectorization_service = ArticleVectorizationService(
            article_repo=article_repo, content_repo=content_repo, task_repo=task_repo
        )
        search_service = HotTopicSearchService(
            unified_topic_repo=unified_topic_repo, hot_topic_repo=hot_topic_repo,
            article_repo=article_repo, vectorization_service=vectorization_service
        )
        
        result = search_service.find_related_articles(
            unified_topic_id=topic_id, limit=limit, days_range=days_range
        )
        
        # Optional: Add reading status if user context available (needs auth)
        # if g.get('user_id'):
        #     reading_history_repo = UserReadingHistoryRepository(db_session)
        #     result["articles"] = _add_reading_status_to_articles(g.user_id, result.get("articles",[]), reading_history_repo)

        return success_response(result)
        
    except (ImportError, AttributeError) as ie:
         logger.error(f"初始化相关文章服务失败: {str(ie)}", exc_info=True)
         return error_response(PARAMETER_ERROR, f"相关文章功能配置不完整: {str(ie)}")
    except Exception as e:
        logger.error(f"获取热点相关文章失败 (Topic ID: {topic_id}): {str(e)}", exc_info=True)
        status_code = NOT_FOUND if "未找到统一热点" in str(e) else PARAMETER_ERROR
        return error_response(status_code, f"获取热点相关文章失败: {str(e)}")


@client_hot_topics_bp.route("/platforms", methods=["GET"])
def get_available_platforms():
    """获取可用的热点平台列表
    
    Returns:
        平台列表
    """
    try:
        db_session = get_db_session()
        platform_repo = HotTopicPlatformRepository(db_session)
        hot_topic_repo = HotTopicRepository(db_session)
        
        # 使用平台服务获取平台信息
        platform_service = HotTopicPlatformService(platform_repo, hot_topic_repo)
        platforms = platform_service.get_platforms(only_active=True)
        
        # 如果数据库中没有平台数据，返回默认平台列表
        if not platforms:
            platforms = [
                {"code": "weibo", "name": "微博热搜", "icon": "fab fa-weibo"},
                {"code": "zhihu", "name": "知乎热榜", "icon": "fab fa-zhihu"},
                {"code": "baidu", "name": "百度热搜", "icon": "fas fa-search"},
                {"code": "toutiao", "name": "今日头条", "icon": "far fa-newspaper"},
                {"code": "douyin", "name": "抖音热点", "icon": "fab fa-tiktok"}
            ]
        
        return success_response(platforms)
    except Exception as e:
        logger.error(f"获取热点平台列表失败: {str(e)}", exc_info=True)
        # 发生错误时也返回默认平台列表
        default_platforms = [
            {"code": "weibo", "name": "微博热搜", "icon": "fab fa-weibo"},
            {"code": "zhihu", "name": "知乎热榜", "icon": "fab fa-zhihu"},
            {"code": "baidu", "name": "百度热搜", "icon": "fas fa-search"},
            {"code": "toutiao", "name": "今日头条", "icon": "far fa-newspaper"},
        ]
        return success_response(default_platforms)


@client_hot_topics_bp.route("/platform/topics", methods=["GET"])
def get_platform_topics():
    """获取指定平台的热点话题列表
    
    查询参数:
    - platform_code: 平台代码 (必需)
    - limit: 返回数量限制，默认50
    - topic_date: 指定日期 (YYYY-MM-DD)，不指定则获取最新
    
    Returns:
        指定平台的热点话题列表
    """
    try:
        platform_code = request.args.get("platform_code")
        if not platform_code:
            return error_response(PARAMETER_ERROR, "缺少 platform_code 查询参数")
            
        limit = request.args.get("limit", 50, type=int)
        topic_date = request.args.get("topic_date")
        
        db_session = get_db_session()
        platform_repo = HotTopicPlatformRepository(db_session)
        hot_topic_repo = HotTopicRepository(db_session)
        
        platform_service = HotTopicPlatformService(platform_repo, hot_topic_repo)
        
        try:
            topics = platform_service.get_platform_topics(
                platform_code=platform_code,
                limit=limit,
                date_str=topic_date
            )
            
            # 获取平台信息
            platform = platform_service.get_platform_by_code(platform_code)
            
            return success_response({
                "platform": platform,
                "topics": topics,
                "total": len(topics)
            })
        except Exception as e:
            # 如果平台不存在或其他错误
            logger.error(f"获取平台 {platform_code} 的热点失败: {str(e)}")
            return error_response(NOT_FOUND if "不存在" in str(e) else PARAMETER_ERROR, str(e))
            
    except Exception as e:
        logger.error(f"获取平台热点失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取平台热点失败: {str(e)}")


@client_hot_topics_bp.route("/platform/all_topics", methods=["GET"])
def get_all_platforms_topics():
    """获取所有平台的热点话题
    
    查询参数:
    - limit_per_platform: 每个平台返回的话题数量，默认10
    
    Returns:
        所有平台的热点话题
    """
    try:
        limit_per_platform = request.args.get("limit_per_platform", 10, type=int)
        
        db_session = get_db_session()
        platform_repo = HotTopicPlatformRepository(db_session)
        hot_topic_repo = HotTopicRepository(db_session)
        
        platform_service = HotTopicPlatformService(platform_repo, hot_topic_repo)
        
        result = platform_service.get_all_platforms_topics(limit_per_platform)
        
        # 构建更友好的返回结构
        platforms_topics = []
        for platform_code, data in result.items():
            platform_data = {
                "platform": data.get("platform", {}),
                "topics": data.get("topics", []),
                "total": len(data.get("topics", [])),
                "error": data.get("error")
            }
            platforms_topics.append(platform_data)
            
        return success_response({
            "platforms": platforms_topics,
            "total_platforms": len(platforms_topics)
        })
    except Exception as e:
        logger.error(f"获取所有平台热点失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取所有平台热点失败: {str(e)}")


@client_hot_topics_bp.route("/summary", methods=["GET"])
def get_hot_topics_summary():
    """获取最新聚合(Unified)热点话题的摘要 (每个平台Top N)
    
    查询参数:
    - limit_per_platform: 每个平台返回条数，默认5
    
    Returns:
        各平台Top N聚合热点摘要及更新日期
    """
    try:
        limit = request.args.get("limit_per_platform", 5, type=int)
        
        db_session = get_db_session()
        unified_topic_repo = UnifiedHotTopicRepository(db_session)
        
        latest_date = unified_topic_repo.get_latest_unified_topic_date()
        if not latest_date:
            return success_response({"summary": {}, "topic_date": None})
            
        # Fetch all unified topics for the latest date (limit might need adjustment)
        # Consider if repo can provide grouped top N for efficiency
        per_page = 100 # Fetch enough to likely cover top N for all platforms
        unified_result = unified_topic_repo.get_unified_topics_by_date(latest_date, page=1, per_page=per_page)
        all_topics_latest_date = unified_result.get("list", [])

        summary = {}
        platform_counts = {}
        
        for topic in all_topics_latest_date:
             platforms = topic.get("source_platforms", [])
             if not platforms: continue
             
             # Add topic to summary for each platform it belongs to, up to the limit
             for platform in platforms:
                 if platform not in summary:
                      summary[platform] = []
                      platform_counts[platform] = 0
                 
                 if platform_counts[platform] < limit:
                      summary[platform].append({
                           "id": topic["id"],
                           "title": topic["unified_title"],
                           "keywords": topic.get("keywords", []),
                      })
                      platform_counts[platform] += 1

        result = {
            "summary": summary,
            "topic_date": latest_date.isoformat()
        }
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取聚合热点话题摘要失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取聚合热点话题摘要失败: {str(e)}")