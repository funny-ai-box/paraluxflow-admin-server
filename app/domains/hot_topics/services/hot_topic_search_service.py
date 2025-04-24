# app/domains/hot_topics/services/hot_topic_search_service.py
"""热点话题搜索服务 - 用于检索与热点相关的RSS文章"""
import logging
from typing import Dict, List, Any, Optional
from datetime import date, datetime, timedelta

from app.infrastructure.database.repositories.hot_topic_repository import UnifiedHotTopicRepository, HotTopicRepository
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.domains.rss.services.vectorization_service import ArticleVectorizationService
from app.core.exceptions import APIException

logger = logging.getLogger(__name__)

class HotTopicSearchService:
    """热点话题搜索服务 - 负责检索与热点相关的RSS文章"""
    
    def __init__(
        self, 
        unified_topic_repo: UnifiedHotTopicRepository,
        hot_topic_repo: HotTopicRepository,
        article_repo: RssFeedArticleRepository,
        vectorization_service: ArticleVectorizationService
    ):
        """初始化搜索服务
        
        Args:
            unified_topic_repo: 统一热点仓库
            hot_topic_repo: 原始热点仓库
            article_repo: RSS文章仓库
            vectorization_service: 向量化服务
        """
        self.unified_topic_repo = unified_topic_repo
        self.hot_topic_repo = hot_topic_repo
        self.article_repo = article_repo
        self.vectorization_service = vectorization_service
    
    def find_related_articles(
        self, 
        unified_topic_id: str, 
        limit: int = 10, 
        days_range: int = 7
    ) -> Dict[str, Any]:
        """查找与热点相关的文章
        
        Args:
            unified_topic_id: 统一热点ID
            limit: 返回的最大文章数量
            days_range: 查找的最大天数范围
            
        Returns:
            查询结果
        """
        try:
            # 1. 获取统一热点信息
            topic_dicts = self.unified_topic_repo.get_topic_by_id(unified_topic_id)
            if not topic_dicts:
                raise APIException(f"未找到ID为 {unified_topic_id} 的统一热点")
            
            unified_topic = topic_dicts[0] if isinstance(topic_dicts, list) else topic_dicts
            
            # 2. 提取关键词
            keywords = unified_topic.get("keywords", [])
            if not keywords:
                # 如果没有关键词，则使用标题作为查询
                logger.warning(f"热点 {unified_topic_id} 没有关键词，将使用标题作为查询")
                query_text = unified_topic.get("unified_title", "")
                search_results = self._search_with_combined_query(query_text, limit, days_range)
                return {
                    "unified_topic_id": unified_topic_id,
                    "unified_topic": unified_topic,
                    "articles": search_results,
                    "query_method": "title",
                    "total": len(search_results)
                }
            
            # 3. 获取原始热点中的一些标题作为补充查询
            related_ids = unified_topic.get("related_topic_ids", [])
            original_topics = []
            if related_ids:
                # 获取至多3个原始热点的标题
                original_topics = self.hot_topic_repo.get_topics_by_ids(related_ids[:3])
            
            # 4. 使用关键词进行向量搜索
            search_results = self._search_with_keywords(
                keywords, 
                original_topics, 
                unified_topic.get("unified_title", ""),
                limit, 
                days_range
            )
            
            return {
                "unified_topic_id": unified_topic_id,
                "unified_topic": unified_topic,
                "articles": search_results,
                "keywords_used": keywords,
                "query_method": "keywords",
                "total": len(search_results)
            }
            
        except APIException as e:
            # 直接重新抛出API异常
            raise e
        except Exception as e:
            logger.error(f"查找相关文章时出错: {str(e)}", exc_info=True)
            raise APIException(f"查找相关文章失败: {str(e)}")
    
    def _search_with_keywords(
        self, 
        keywords: List[str], 
        original_topics: List[Dict[str, Any]],
        unified_title: str,
        limit: int = 10, 
        days_range: int = 7
    ) -> List[Dict[str, Any]]:
        """使用关键词查找相关文章
        
        Args:
            keywords: 关键词列表
            original_topics: 原始热点列表
            unified_title: 统一热点标题
            limit: 返回的最大文章数量
            days_range: 查找的最大天数范围
            
        Returns:
            相关文章列表
        """
        try:
            # 1. 使用每个关键词单独查询
            all_results = []
            seen_article_ids = set()
            
            # 每个关键词分配的查询配额
            keywords_limit = max(5, limit // (len(keywords) + 1))
            
            # 使用关键词查询
            for keyword in keywords:
                logger.info(f"使用关键词 '{keyword}' 查询相关文章")
                keyword_results = self.vectorization_service.search_articles(keyword, keywords_limit)
                
                # 检查查询结果并过滤已有的文章
                for article in keyword_results:
                    if article["id"] not in seen_article_ids:
                        seen_article_ids.add(article["id"])
                        all_results.append(article)
            
            # 2. 如果有原始热点标题，也使用它们进行查询（给一定的权重）
            for topic in original_topics:
                if len(all_results) >= limit * 2:  # 获取足够的候选结果后停止
                    break
                    
                title = topic.get("topic_title", "")
                if title:
                    logger.info(f"使用原始热点标题 '{title}' 查询相关文章")
                    title_results = self.vectorization_service.search_articles(title, 3)  # 每个标题只获取少量结果
                    
                    for article in title_results:
                        if article["id"] not in seen_article_ids:
                            seen_article_ids.add(article["id"])
                            all_results.append(article)
            
            # 3. 使用统一热点标题进行查询
            if unified_title and len(all_results) < limit * 2:
                logger.info(f"使用统一热点标题 '{unified_title}' 查询相关文章")
                title_results = self.vectorization_service.search_articles(unified_title, 5)
                
                for article in title_results:
                    if article["id"] not in seen_article_ids:
                        seen_article_ids.add(article["id"])
                        all_results.append(article)
            
            # 4. 按相似度排序结果
            all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            
            # 5. 返回前 limit 条结果
            return all_results[:limit]
        except Exception as e:
            logger.error(f"使用关键词查询相关文章失败: {str(e)}", exc_info=True)
            return []  # 出错时返回空列表
    
    def _search_with_combined_query(
        self,
        query_text: str,
        limit: int = 10,
        days_range: int = 7
    ) -> List[Dict[str, Any]]:
        """使用组合查询查找相关文章
        
        Args:
            query_text: 查询文本
            limit: 返回的最大文章数量
            days_range: 查找的最大天数范围
            
        Returns:
            相关文章列表
        """
        try:
            # 直接使用向量化服务的搜索功能
            return self.vectorization_service.search_articles(query_text, limit)
        except Exception as e:
            logger.error(f"使用组合查询相关文章失败: {str(e)}", exc_info=True)
            return []  # 出错时返回空列表
    
    def get_topic_by_id(self, unified_topic_id: str) -> Dict[str, Any]:
        """获取统一热点详情
        
        Args:
            unified_topic_id: 统一热点ID
            
        Returns:
            统一热点信息
            
        Raises:
            APIException: 如果热点不存在
        """
        try:
            topic_dicts = self.unified_topic_repo.get_topic_by_id(unified_topic_id)
            if not topic_dicts:
                raise APIException(f"未找到ID为 {unified_topic_id} 的统一热点",50001)
            
            unified_topic = topic_dicts[0] if isinstance(topic_dicts, list) else topic_dicts
            
            # 获取原始热点详情
            related_ids = unified_topic.get("related_topic_ids", [])
            if related_ids:
                original_topics = self.hot_topic_repo.get_topics_by_ids(related_ids)
                unified_topic["original_topics"] = original_topics
            
            return unified_topic
        except APIException:
            raise
        except Exception as e:
            logger.error(f"获取统一热点详情失败: {str(e)}", exc_info=True)
            raise APIException(f"获取统一热点详情失败: {str(e)}", 50001)