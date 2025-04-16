# app/api/client/v1/hot_topics/hot_topics.py
"""客户端热点话题API控制器"""
import logging
from flask import Blueprint, request, g

from app.api.middleware.client_auth import client_auth_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.hot_topic_repository import HotTopicTaskRepository, HotTopicRepository
from app.domains.hot_topics.services.hot_topic_service import HotTopicService

logger = logging.getLogger(__name__)

# 创建蓝图
client_hot_topics_bp = Blueprint("hot_topics", __name__)

@client_hot_topics_bp.route("/latest", methods=["GET"])
def get_latest_hot_topics():
    """获取最新热点话题
    
    查询参数:
    - platform: 平台筛选（weibo, zhihu, baidu, toutiao, douyin）
    - limit: 返回条数，默认50
    
    Returns:
        最新热点话题列表
    """
    try:
        # 获取参数
        platform = request.args.get("platform")
        limit = request.args.get("limit", 50, type=int)
        
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        topic_repo = HotTopicRepository(db_session)
        
        # 创建服务
        hot_topic_service = HotTopicService(task_repo, topic_repo)
        
        # 获取最新热点
        topics = hot_topic_service.get_latest_hot_topics(platform, limit)
        
        return success_response(topics)
    except Exception as e:
        logger.error(f"获取最新热点话题失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取最新热点话题失败: {str(e)}")

@client_hot_topics_bp.route("/platforms", methods=["GET"])
def get_available_platforms():
    """获取可用的热点平台列表
    
    Returns:
        平台列表
    """
    # 返回固定的平台列表
    platforms = [
        {"id": "weibo", "name": "微博热搜", "icon": "weibo-icon"},
        {"id": "zhihu", "name": "知乎热榜", "icon": "zhihu-icon"},
        {"id": "baidu", "name": "百度热搜", "icon": "baidu-icon"},
        {"id": "toutiao", "name": "今日头条", "icon": "toutiao-icon"},
        {"id": "douyin", "name": "抖音热点", "icon": "douyin-icon"}
    ]
    
    return success_response(platforms)

@client_hot_topics_bp.route("/summary", methods=["GET"])
def get_hot_topics_summary():
    """获取热点话题摘要
    
    返回各平台最新的前10条热点
    
    Returns:
        热点摘要数据
    """
    try:
        # 创建会话和存储库
        db_session = get_db_session()
        task_repo = HotTopicTaskRepository(db_session)
        topic_repo = HotTopicRepository(db_session)
        
        # 创建服务
        hot_topic_service = HotTopicService(task_repo, topic_repo)
        
        # 获取各平台热点
        platforms = ["weibo", "zhihu", "baidu", "toutiao", "douyin"]
        summary = {}
        
        for platform in platforms:
            # 每个平台获取前10条
            topics = hot_topic_service.get_latest_hot_topics(platform, 10)
            
            # 简化数据，只保留必要字段
            simplified_topics = []
            for topic in topics:
                simplified_topics.append({
                    "id": topic["id"],
                    "title": topic["topic_title"],
                    "url": topic["topic_url"],
                    "hot_value": topic["hot_value"],
                    "is_hot": topic["is_hot"],
                    "is_new": topic["is_new"],
                    "rank": topic["rank"],
                    "heat_level": topic["heat_level"]
                })
            
            summary[platform] = simplified_topics
        
        # 获取更新时间
        latest_update = None
        all_topics = hot_topic_service.get_latest_hot_topics(None, 1)
        if all_topics:
            latest_update = all_topics[0]["created_at"]
        
        result = {
            "summary": summary,
            "updated_at": latest_update
        }
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取热点话题摘要失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取热点话题摘要失败: {str(e)}")

@client_hot_topics_bp.route("/trend", methods=["GET"])
@client_auth_required
def get_hot_topics_trend():
    """获取热点话题趋势
    
    查询参数:
    - platform: 平台，必填
    - days: 天数，默认7
    
    Returns:
        热点趋势数据
    """
    try:
        # 获取参数
        platform = request.args.get("platform")
        days = request.args.get("days", 7, type=int)
        
        if not platform:
            return error_response(PARAMETER_ERROR, "缺少platform参数")
        
        # 由于当前数据模型不支持历史趋势查询，返回简化的示例数据
        # 在实际实现中，需要扩展数据模型以支持趋势查询
        
        # 模拟数据示例
        trend_data = {
            "platform": platform,
            "days": days,
            "trend": [
                {
                    "date": "2025-04-10",
                    "top_topics": [
                        {"title": "示例话题1", "rank": 1, "heat_level": 5},
                        {"title": "示例话题2", "rank": 2, "heat_level": 4}
                    ]
                },
                {
                    "date": "2025-04-11",
                    "top_topics": [
                        {"title": "示例话题3", "rank": 1, "heat_level": 5},
                        {"title": "示例话题4", "rank": 2, "heat_level": 4}
                    ]
                }
                # 实际实现中应返回更多天数的数据
            ]
        }
        
        return success_response(trend_data)
    except Exception as e:
        logger.error(f"获取热点话题趋势失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取热点话题趋势失败: {str(e)}")