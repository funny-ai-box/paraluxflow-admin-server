# app/domains/rss/services/article_service.py
"""文章服务实现"""
import re
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import requests
from urllib.parse import urlparse

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
        
        # 获取Feed条目
        entries, error = self._get_feed_entries(feed_url)
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
        try:
            # 设置请求头
            parsed_url = urlparse(image_url)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": f"{parsed_url.scheme}://{parsed_url.netloc}",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
            }
            
            # 获取图片内容
            response = requests.get(image_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # 获取MIME类型
            mime_type = response.headers.get('content-type', 'image/jpeg')
            
            return response.content, mime_type, None
        except requests.RequestException as e:
            error_msg = f"获取图片失败: {str(e)}"
            logger.error(error_msg)
            return b"", "image/jpeg", error_msg
        except Exception as e:
            error_msg = f"处理图片失败: {str(e)}"
            logger.error(error_msg)
            return b"", "image/jpeg", error_msg
    
    def get_content_from_url(self, url: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """从URL获取文章内容
        
        Args:
            url: 文章URL
            
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
            
            # 获取文章页面
            response = requests.get(url, headers=headers, timeout=30)
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
    
    def _get_feed_entries(self, feed_url: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """获取Feed条目
        
        Args:
            feed_url: Feed URL
            
        Returns:
            (Feed条目列表, 错误信息)
        """
        try:
            import feedparser
            # 设置请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"
            }
            
            # 获取RSS内容
            response = requests.get(feed_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 解析Feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo and not feed.entries:
                return [], f"Feed解析错误: {feed.bozo_exception}"
            
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
            
            return entries, None
        except requests.RequestException as e:
            error_msg = f"获取Feed失败: {str(e)}"
            logger.error(error_msg)
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