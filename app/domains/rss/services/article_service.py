import re
import logging
import time
import warnings
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import requests
from urllib.parse import urlparse

# 禁用不安全的HTTPS警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class ArticleService:
    """文章管理服务，处理RSS文章的抓取和管理"""
    
    def __init__(self, article_repo, content_repo, feed_repo):
        """初始化文章服务
        
        Args:
            article_repo: 文章仓库
            content_repo: 内容仓库
            feed_repo: Feed仓库
        """
        self.article_repo = article_repo
        self.content_repo = content_repo
        self.feed_repo = feed_repo
        # HTTP代理配置
        self.proxy_config = {
            "proxy_url": "http://178.128.115.155:8118",
            "enabled": True  # 默认启用代理，但在连接失败时会自动尝试不使用代理
        }
    
    def get_articles(self, page: int = 1, per_page: int = 10, filters: Dict = None) -> Dict[str, Any]:
        """获取文章列表
        
        Args:
            page: 页码
            per_page: 每页数量
            filters: 筛选条件
            
        Returns:
            文章列表及分页信息
        """
        return self.article_repo.get_articles(page, per_page, filters)
    
    def get_article(self, article_id: int) -> Dict[str, Any]:
        """获取文章详情
        
        Args:
            article_id: 文章ID
            
        Returns:
            文章详情
            
        Raises:
            Exception: 获取失败时抛出异常
        """
        err, article = self.article_repo.get_article_by_id(article_id)
        if err:
            raise Exception(f"获取文章失败: {err}")
        
        # 获取文章内容
        if article["content_id"]:
            err, content = self.content_repo.get_article_content(article["content_id"])
            if not err:
                article["content"] = content
        
        return article
    
    def sync_feed_articles(self, feed_id: str) -> Dict[str, Any]:
        """同步Feed文章
        
        Args:
            feed_id: Feed ID
            
        Returns:
            同步结果
            
        Raises:
            Exception: 同步失败时抛出异常
        """
        # 获取Feed信息
        err, feed = self.feed_repo.get_feed_by_id(feed_id)
        if err:
            raise Exception(f"获取Feed信息失败: {err}")
        
        feed_url = feed.get("url")
        if not feed_url:
            raise Exception("Feed URL不存在")
        
        # 根据feed的use_proxy字段决定是否使用代理
        use_proxy = bool(feed.get("use_proxy", False))
        
        # 获取Feed条目
        entries, error = self._get_feed_entries(feed_url, use_proxy)
        if error:
            # 更新Feed获取状态为失败
            self.feed_repo.update_feed_fetch_status(feed_id, 2, error)
            raise Exception(f"获取Feed条目失败: {error}")
        
        if not entries:
            self.feed_repo.update_feed_fetch_status(feed_id, 1)
            return {"message": "没有新文章", "total": 0}
        
        # 转换为文章格式
        articles_to_insert = self._prepare_articles(entries, feed)
        
        # 插入新文章
        success = self.article_repo.insert_articles(articles_to_insert)
        if not success:
            # 更新Feed获取状态为失败
            self.feed_repo.update_feed_fetch_status(feed_id, 2, "插入文章失败")
            raise Exception("插入文章失败")
        
        # 更新Feed获取状态为成功
        self.feed_repo.update_feed_fetch_status(feed_id, 1)
        
        return {
            "message": "同步成功",
            "total": len(articles_to_insert),
            "feed_id": feed_id
        }
    
    def batch_sync_articles(self, feed_ids: List[str]) -> Dict[str, Any]:
        """批量同步多个Feed的文章
        
        Args:
            feed_ids: Feed ID列表
            
        Returns:
            同步结果
        """
        results = {
            "success": 0,
            "failed": 0,
            "details": {}
        }
        
        for feed_id in feed_ids:
            try:
                result = self.sync_feed_articles(feed_id)
                results["success"] += 1
                results["details"][feed_id] = {
                    "status": "success",
                    "message": result.get("message", "同步成功"),
                    "total": result.get("total", 0)
                }
            except Exception as e:
                results["failed"] += 1
                results["details"][feed_id] = {
                    "status": "failed",
                    "message": str(e)
                }
        
        return results
    
    def reset_article(self, article_id: int) -> Dict[str, Any]:
        """重置文章状态，允许重新抓取
        
        Args:
            article_id: 文章ID
            
        Returns:
            重置结果
            
        Raises:
            Exception: 重置失败时抛出异常
        """
        err, result = self.article_repo.reset_article(article_id)
        if err:
            raise Exception(f"重置文章失败: {err}")
        
        return result
    
    def proxy_image(self, image_url: str) -> Tuple[bytes, str, Optional[str]]:
        """代理获取图片
        
        Args:
            image_url: 图片URL
            
        Returns:
            (图片内容, MIME类型, 错误信息)
        """
        # 尝试使用代理和不使用代理两种方式
        for use_proxy in [True, False]:
            try:
                # 设置请求头
                parsed_url = urlparse(image_url)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": f"{parsed_url.scheme}://{parsed_url.netloc}",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
                }
                
                # 设置代理
                proxies = None
                if use_proxy:
                    proxies = {"http": self.proxy_config["proxy_url"], "https": self.proxy_config["proxy_url"]}
                    logger.info(f"尝试使用代理获取图片: {image_url}")
                else:
                    logger.info(f"尝试直接获取图片（不使用代理）: {image_url}")
                
                # 禁用SSL验证，解决SSL错误问题
                verify_ssl = False
                
                # 获取图片内容
                response = requests.get(
                    image_url, 
                    headers=headers, 
                    proxies=proxies, 
                    stream=True, 
                    timeout=20, 
                    verify=verify_ssl
                )
                response.raise_for_status()
                
                # 获取MIME类型
                mime_type = response.headers.get('content-type', 'image/jpeg')
                
                return response.content, mime_type, None
                
            except requests.RequestException as e:
                error_msg = f"获取图片失败 {'(使用代理)' if use_proxy else '(不使用代理)'}: {str(e)}"
                logger.warning(error_msg)
                # 如果使用代理失败，会尝试下一个循环（不使用代理）
                # 如果不使用代理也失败，将在循环结束后返回错误
            
            except Exception as e:
                error_msg = f"处理图片失败 {'(使用代理)' if use_proxy else '(不使用代理)'}: {str(e)}"
                logger.warning(error_msg)
        
        # 如果两种方式都失败了
        error_msg = f"所有获取图片的尝试都失败: {image_url}"
        logger.error(error_msg)
        return b"", "image/jpeg", error_msg
    
    def get_content_from_url(self, url: str, use_proxy: bool = False) -> Tuple[Dict[str, Any], Optional[str]]:
        """从URL获取文章内容
        
        Args:
            url: 文章URL
            use_proxy: 是否使用代理
            
        Returns:
            (内容信息, 错误信息)
        """
        try:
            # 设置请求头
            parsed_url = urlparse(url)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": f"{parsed_url.scheme}://{parsed_url.netloc}",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            }
            
            # 设置代理
            proxies = None
            verify_ssl = True  # 默认验证SSL
            
            if use_proxy:
                proxies = {"http": self.proxy_config["proxy_url"], "https": self.proxy_config["proxy_url"]}
                # 当使用代理时禁用SSL验证，解决SSL错误问题
                verify_ssl = False
                logger.info(f"使用代理获取内容: {url}, SSL验证: {verify_ssl}")
            
            # 获取文章页面
            response = requests.get(url, headers=headers, proxies=proxies, timeout=30, verify=verify_ssl)
            response.raise_for_status()
            
            # 获取内容类型
            content_type = response.headers.get('content-type', '')
            if 'text/html' not in content_type:
                return {}, f"不支持的内容类型: {content_type}"
            
            # 获取HTML内容
            html_content = response.text
            
            # 简化的文本提取
            text_content = re.sub(r'<[^>]+>', ' ', html_content)
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            
            return {
                "html_content": html_content,
                "text_content": text_content,
                "url": url,
                "title": self._extract_title(html_content),
                "fetched_at": datetime.now().isoformat()
            }, None
        except requests.RequestException as e:
            error_msg = f"获取文章失败: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
        except Exception as e:
            error_msg = f"解析文章失败: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg
    
    def _get_feed_entries(self, feed_url: str, use_proxy: bool = False) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """获取Feed条目
        
        Args:
            feed_url: Feed URL
            use_proxy: 是否使用代理
            
        Returns:
            (Feed条目列表, 错误信息)
        """
        try:
            import feedparser
            import random
            import socket
            import time
            from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout, SSLError
            
            # 增加UA列表，减少被识别为爬虫的可能性
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
            ]
            
            # 如果需要使用代理，最大尝试次数为10次
            # 如果不需要使用代理，则最大尝试次数为3次
            max_retries = 10 if use_proxy else 3
            
            for attempt in range(max_retries):
                # 随机选择UA
                user_agent = random.choice(user_agents)
                
                try:
                    # 如果要求使用代理，则强制使用代理
                    if use_proxy:
                        # 只使用HTTP代理方式
                        headers = {
                            "User-Agent": user_agent,
                            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
                        }
                        
                        proxies = {"http": self.proxy_config["proxy_url"], "https": self.proxy_config["proxy_url"]}
                        verify_ssl = False
                        logger.info(f"尝试 #{attempt+1}: 使用HTTP代理获取Feed: {feed_url}")
                        
                        # 设置较短的超时时间，以便快速失败并尝试下一次
                        response = requests.get(
                            feed_url, 
                            headers=headers, 
                            proxies=proxies, 
                            timeout=15,
                            verify=verify_ssl
                        )
                        response.raise_for_status()
                        content = response.content
                    else:
                        # 不使用代理的情况下直接获取
                        headers = {
                            "User-Agent": user_agent,
                            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
                        }
                        logger.info(f"尝试 #{attempt+1}: 直接获取Feed（无代理）: {feed_url}")
                        response = requests.get(feed_url, headers=headers, timeout=30)
                        response.raise_for_status()
                        content = response.content
                    
                    # 如果内容为空，抛出异常
                    if not content or len(content) < 10:  # 至少应该有一些基本的XML结构
                        raise Exception("获取到的内容为空或太小")
                    
                    # 解析Feed
                    feed = feedparser.parse(content)
                    
                    # 检查feed是否有有效内容
                    if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                        if feed.bozo and hasattr(feed, 'bozo_exception'):
                            logger.warning(f"Feed解析警告: {feed.bozo_exception}")
                            # 特殊处理：某些Feed即使有bozo异常也可能部分有效
                            if hasattr(feed, 'entries') and len(feed.entries) > 0:
                                logger.info("尽管有解析警告，但Feed仍包含有效条目，继续处理")
                            else:
                                raise Exception(f"Feed解析错误: {feed.bozo_exception}")
                        else:
                            raise Exception("Feed没有任何条目")
                    
                    # 提取条目
                    entries = []
                    for entry in feed.entries:
                        # 处理发布日期
                        published_date = entry.get('published_parsed') or entry.get('updated_parsed')
                        if published_date:
                            published_date = datetime(*published_date[:6])
                        else:
                            published_date = datetime.now()
                        
                        # 处理摘要
                        summary = entry.get('summary', '')
                        if not summary and 'content' in entry:
                            for content in entry.content:
                                if content.get('type') == 'text/html':
                                    summary = content.value
                                    break
                        
                        # 处理缩略图
                        thumbnail_url = None
                        if 'media_thumbnail' in entry:
                            for thumbnail in entry.media_thumbnail:
                                thumbnail_url = thumbnail.get('url')
                                if thumbnail_url:
                                    break
                        
                        entries.append({
                            "title": entry.get('title', '无标题'),
                            "link": entry.get('link', ''),
                            "summary": summary,
                            "thumbnail_url": thumbnail_url,
                            "published_date": published_date.isoformat()
                        })
                    
                    logger.info(f"成功获取Feed条目: {feed_url}, 条目数: {len(entries)}")
                    return entries, None
                    
                except (ConnectionError, ConnectTimeout, ReadTimeout, socket.timeout, ConnectionResetError, SSLError) as e:
                    # 网络连接问题
                    error_type = type(e).__name__
                    error_msg = f"{error_type} 错误 #{attempt+1}: {str(e)}"
                    logger.warning(error_msg)
                    
                    # 增加随机等待时间再尝试
                    wait_time = random.uniform(1.5, 4.0)
                    logger.info(f"等待 {wait_time:.2f} 秒后重试...")
                    time.sleep(wait_time)
                
                except Exception as e:
                    error_msg = f"获取Feed尝试 #{attempt+1} 失败: {str(e)}"
                    logger.warning(error_msg)
                    # 继续下一个尝试
                    time.sleep(random.uniform(0.5, 2.0))  # 随机等待时间，避免请求模式被识别
            
            # 如果所有尝试都失败
            error_msg = "所有获取Feed的尝试都失败"
            if use_proxy:
                error_msg += "（使用代理）"
            else:
                error_msg += "（不使用代理）"
            
            return [], error_msg
            
        except Exception as e:
            error_msg = f"解析Feed失败: {str(e)}"
            logger.error(error_msg)
            return [], error_msg
    
    def _prepare_articles(self, entries: List[Dict[str, Any]], feed: Dict[str, Any]) -> List[Dict[str, Any]]:
        """准备文章数据
        
        Args:
            entries: Feed条目列表
            feed: Feed信息
            
        Returns:
            准备好的文章数据列表
        """
        articles = []
        for entry in entries:
            try:
                article = {
                    "feed_id": feed["id"],
                    "feed_logo": feed.get("logo"),
                    "feed_title": feed.get("title"),
                    "link": entry.get("link"),
                    "title": entry.get("title"),
                    "summary": entry.get("summary", ""),
                    "thumbnail_url": entry.get("thumbnail_url"),
                    "status": 0,  # 待抓取
                    "published_date": datetime.fromisoformat(entry.get("published_date")),
                }
                articles.append(article)
            except Exception as e:
                logger.error(f"处理条目失败: {str(e)}")
                continue
        
        return articles
    
    def _extract_title(self, html_content: str) -> str:
        """从HTML内容中提取标题
        
        Args:
            html_content: HTML内容
            
        Returns:
            标题
        """
        match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return "未知标题"