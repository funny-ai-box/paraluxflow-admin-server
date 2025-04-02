"""RSS Feed服务实现"""
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
import requests
from urllib.parse import urlparse

from app.core.exceptions import APIException
from app.core.status_codes import EXTERNAL_API_ERROR, PARAMETER_ERROR

logger = logging.getLogger(__name__)


class FeedService:
    """RSS Feed服务，处理Feed内容获取和解析"""
    
    @staticmethod
    def format_feed_entries(feed_url: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """格式化Feed条目
        
        Args:
            feed_url: Feed URL
            
        Returns:
            (条目列表, 错误信息)
        """
        try:
            # 这里添加请求头防止被屏蔽
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"
            }
            
            # 获取RSS内容
            response = requests.get(feed_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 解析内容
            # 注意：这里可以使用feedparser库来解析RSS/Atom内容
            # 简化实现，实际中可以替换为更完整的解析逻辑
            
            # 模拟解析结果
            entries = []
            # 假设解析逻辑在此 
            # TODO: 实现实际的RSS解析逻辑
            
            return entries, None
        except requests.RequestException as e:
            error_msg = f"获取Feed失败: {str(e)}"
            logger.error(error_msg)
            return [], error_msg
        except Exception as e:
            error_msg = f"解析Feed失败: {str(e)}"
            logger.error(error_msg)
            return [], error_msg
    
    @staticmethod
    def fetch_article_content(url: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """获取文章内容
        
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
            
            # 简化的文本提取 (实际应使用BeautifulSoup或其他HTML解析库)
            # 移除HTML标签获取粗略文本内容
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
    
    @staticmethod
    def _extract_title(html_content: str) -> str:
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
    
    @staticmethod
    def proxy_image(image_url: str) -> Tuple[bytes, str, Optional[str]]:
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
        
    