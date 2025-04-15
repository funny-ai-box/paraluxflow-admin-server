# app/api/client/v1/rss/feed.py
"""客户端Feed API接口"""
import logging
import requests
from flask import Blueprint, request, g
from urllib.parse import urlparse

from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss_feed_repository import RssFeedRepository
from app.infrastructure.database.repositories.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.user_repository import UserSubscriptionRepository
from app.api.middleware.client_auth import client_auth_required

from app.api.client.v1.rss import feed_bp

logger = logging.getLogger(__name__)

@feed_bp.route("/discover", methods=["GET"])
@client_auth_required
def discover_feeds():
    """发现Feed列表，支持分页和筛选
    
    查询参数:
    - page: 页码，默认1
    - per_page: 每页数量，默认20
    - title: 标题模糊搜索
    - category_id: 分类ID
    
    Returns:
        Feed列表和分页信息
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取分页参数
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        
        # 构建筛选条件
        filters = {
            "is_active": True  # 只显示活跃的Feed
        }
        
        # 标题筛选
        title = request.args.get("title")
        if title:
            filters["title"] = title
        
        # 分类筛选
        category_id = request.args.get("category_id", type=int)
        if category_id:
            filters["category_id"] = category_id
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        subscription_repo = UserSubscriptionRepository(db_session)
        
        # 获取订阅列表，用于标记用户是否已订阅
        user_subscriptions = subscription_repo.get_user_subscriptions(user_id)
        subscribed_feed_ids = [sub["feed_id"] for sub in user_subscriptions]
        
        # 获取Feed列表
        result = feed_repo.get_filtered_feeds(filters, page, per_page)
        
        # 标记是否已订阅
        for feed in result["list"]:
            feed["is_subscribed"] = feed["id"] in subscribed_feed_ids
        
        return success_response(result)
    except Exception as e:
        logger.error(f"发现Feed列表失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"发现Feed列表失败: {str(e)}")

@feed_bp.route("/detail", methods=["GET"])
@client_auth_required
def get_feed_detail():
    """获取Feed详情
    
    查询参数:
    - feed_id: Feed ID
    
    Returns:
        Feed详情和用户订阅状态
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取Feed ID
        feed_id = request.args.get("feed_id")
        if not feed_id:
            return error_response(PARAMETER_ERROR, "缺少feed_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        subscription_repo = UserSubscriptionRepository(db_session)
        
        # 获取Feed详情
        err, feed = feed_repo.get_feed_by_id(feed_id)
        if err:
            return error_response(PARAMETER_ERROR, err)
        
        # 查询用户是否已订阅该Feed
        user_subscriptions = subscription_repo.get_user_subscriptions(user_id)
        is_subscribed = any(sub["feed_id"] == feed_id for sub in user_subscriptions)
        
        # 获取订阅信息
        subscription = None
        if is_subscribed:
            for sub in user_subscriptions:
                if sub["feed_id"] == feed_id:
                    subscription = sub
                    break
        
        # 构建结果
        result = {
            "feed": feed,
            "is_subscribed": is_subscribed,
            "subscription": subscription
        }
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取Feed详情失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取Feed详情失败: {str(e)}")

@feed_bp.route("/categories", methods=["GET"])
@client_auth_required
def get_categories():
    """获取Feed分类列表
    
    Returns:
        分类列表
    """
    try:
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        
        # 获取所有分类
        categories = feed_repo.get_all_categories()
        
        return success_response(categories)
    except Exception as e:
        logger.error(f"获取Feed分类失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"获取Feed分类失败: {str(e)}")

@feed_bp.route("/discover_by_url", methods=["POST"])
@client_auth_required
def discover_by_url():
    """通过URL发现Feed
    
    请求体:
    {
        "url": "网站URL"
    }
    
    Returns:
        发现的Feed列表
    """
    try:
        # 获取请求参数
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        url = data.get("url")
        if not url:
            return error_response(PARAMETER_ERROR, "缺少url参数")
        
        # 确保URL有协议前缀
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # 解析URL
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # 尝试获取网站内容
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            html_content = response.text
        except requests.RequestException as e:
            return error_response(PARAMETER_ERROR, f"获取网站内容失败: {str(e)}")
        
        # 从HTML中提取RSS链接
        import re
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 查找可能的RSS链接
        feed_links = []
        
        # 查找link标签
        for link in soup.find_all("link", rel=["alternate", "rss", "atom"]):
            href = link.get("href", "")
            if href and any(x in link.get("type", "") for x in ["rss", "atom", "xml"]):
                # 处理相对URL
                if not href.startswith(('http://', 'https://')):
                    if href.startswith('/'):
                        href = base_url + href
                    else:
                        href = base_url + '/' + href
                
                feed_links.append({
                    "url": href,
                    "title": link.get("title", parsed_url.netloc),
                    "type": link.get("type", "application/rss+xml")
                })
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        
        # 查询数据库中是否已存在这些Feed
        discovered_feeds = []
        for link in feed_links:
            feeds = feed_repo.get_filtered_feeds({"url": link["url"]}, 1, 10)
            if feeds["list"]:
                # 已存在的Feed
                for feed in feeds["list"]:
                    discovered_feeds.append({
                        "feed": feed,
                        "source": "database",
                        "feed_url": link["url"]
                    })
            else:
                # 新发现的Feed
                discovered_feeds.append({
                    "feed": {
                        "url": link["url"],
                        "title": link["title"],
                        "description": f"从 {url} 发现的Feed"
                    },
                    "source": "discovered",
                    "feed_url": link["url"]
                })
        
        # 如果没有发现Feed，可以尝试常见的RSS路径
        if not discovered_feeds:
            common_paths = [
                "/feed", "/rss", "/atom", "/feed.xml", "/rss.xml", 
                "/index.xml", "/atom.xml", "/feed/", "/rss/", "/atom/"
            ]
            
            for path in common_paths:
                potential_url = base_url + path
                try:
                    response = requests.head(potential_url, headers=headers, timeout=5)
                    if response.status_code == 200:
                        # 可能是有效的Feed URL
                        discovered_feeds.append({
                            "feed": {
                                "url": potential_url,
                                "title": f"{parsed_url.netloc} Feed",
                                "description": f"从 {url} 猜测的可能Feed链接"
                            },
                            "source": "guessed",
                            "feed_url": potential_url
                        })
                except requests.RequestException:
                    pass
        
        return success_response({
            "discovered_feeds": discovered_feeds,
            "website_url": url,
            "website_title": soup.title.string if soup.title else parsed_url.netloc
        })
    except Exception as e:
        logger.error(f"通过URL发现Feed失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"通过URL发现Feed失败: {str(e)}")

@feed_bp.route("/request_add", methods=["POST"])
@client_auth_required
def request_add_feed():
    """请求添加新Feed
    
    请求体:
    {
        "url": "Feed URL",
        "title": "Feed标题",
        "description": "Feed描述"
    }
    
    Returns:
        请求结果
    """
    try:
        # 从g对象获取用户ID
        user_id = g.user_id
        
        # 获取请求参数
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        url = data.get("url")
        if not url:
            return error_response(PARAMETER_ERROR, "缺少url参数")
        
        title = data.get("title", "")
        description = data.get("description", "")
        
        # 创建会话和存储库
        db_session = get_db_session()
        feed_repo = RssFeedRepository(db_session)
        
        # 检查是否已存在该Feed
        feeds = feed_repo.get_filtered_feeds({"url": url}, 1, 1)
        if feeds["list"]:
            # 已存在该Feed
            return success_response({
                "feed": feeds["list"][0],
                "status": "exists"
            }, "该Feed已存在")
        
        # TODO: 实现Feed请求表和审核流程
        # 这里简化处理，直接返回成功信息
        
        return success_response({
            "status": "requested",
            "request_info": {
                "url": url,
                "title": title,
                "description": description,
                "user_id": user_id
            }
        }, "已提交Feed添加请求，等待审核")
    except Exception as e:
        logger.error(f"请求添加Feed失败: {str(e)}")
        return error_response(PARAMETER_ERROR, f"请求添加Feed失败: {str(e)}")