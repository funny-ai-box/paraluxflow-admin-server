"""RSS Feed相关存储库"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union

from sqlalchemy import and_, or_, desc
from sqlalchemy.exc import SQLAlchemyError, NoResultFound
from sqlalchemy.orm import Session

from app.infrastructure.database.models.feed import (
    RssFeed, 
    RssFeedCategory, 
    RssFeedCollection,
    RssFeedCrawlScript,
    RssFeedArticle,
    RssFeedArticleContent,
    RssFeedArticleCrawlLog,
    RssFeedArticleCrawlBatch
)
from app.core.exceptions import NotFoundException, ValidationException
from app.core.status_codes import NOT_FOUND, PARAMETER_ERROR

logger = logging.getLogger(__name__)


class RssFeedRepository:
    """RSS Feed存储库"""

    def __init__(self, db_session: Session):
        """初始化存储库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_feeds_eligible_for_update(self) -> List[Dict[str, Any]]:
        """获取需要更新的Feed列表
        
        Returns:
            符合条件的Feed列表
        """
        try:
            # 获取超过6小时未更新且处于激活状态的Feed
            six_hours_ago = datetime.now() - timedelta(hours=6)
            
            eligible_feeds = self.db.query(RssFeed).filter(
                RssFeed.is_active == True,
                or_(
                    RssFeed.last_successful_fetch_at == None,
                    RssFeed.last_successful_fetch_at < six_hours_ago,
                )
            ).order_by(RssFeed.last_successful_fetch_at).all()
            
            return [self._feed_to_dict(feed) for feed in eligible_feeds]
        except SQLAlchemyError as e:
            logger.error(f"获取需要更新的Feed列表失败: {str(e)}")
            return []

    def get_all_feeds(self) -> List[Dict[str, Any]]:
        """获取所有Feed
        
        Returns:
            所有Feed列表
        """
        try:
            feeds = self.db.query(RssFeed).order_by(desc(RssFeed.id)).all()
            return [self._feed_to_dict(feed) for feed in feeds]
        except SQLAlchemyError as e:
            logger.error(f"获取所有Feed失败: {str(e)}")
            return []

    def get_filtered_feeds(self, filters: Dict[str, Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """根据条件筛选Feed，支持分页
        
        Args:
            filters: 筛选条件字典
            page: 页码，从1开始
            per_page: 每页记录数
                
        Returns:
            分页结果，包含列表和分页信息
        """
        try:
            query = self.db.query(RssFeed)
            
            # 应用筛选条件
            if filters.get("title"):
                query = query.filter(RssFeed.title.like(f"%{filters['title']}%"))
            
            if filters.get("category_id"):
                query = query.filter(RssFeed.category_id == filters["category_id"])
                
            if filters.get("url"):
                query = query.filter(RssFeed.url.like(f"%{filters['url']}%"))
                
            if filters.get("description"):
                query = query.filter(RssFeed.description.like(f"%{filters['description']}%"))
                
            if "is_active" in filters:
                query = query.filter(RssFeed.is_active == filters["is_active"])
            
            # 计算总记录数
            total = query.count()
            
            # 按ID降序排列
            query = query.order_by(desc(RssFeed.id))
            
            # 应用分页
            feeds = query.limit(per_page).offset((page - 1) * per_page).all()
            
            # 计算总页数
            pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            return {
                "list": [self._feed_to_dict(feed) for feed in feeds],
                "total": total,
                "pages": pages,
                "current_page": page,
                "per_page": per_page
            }
        except SQLAlchemyError as e:
            logger.error(f"筛选Feed失败: {str(e)}")
            return {
                "list": [],
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "error": str(e)
            }

    def get_feed_by_id(self, feed_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """根据ID获取Feed
        
        Args:
            feed_id: Feed ID
            
        Returns:
            (错误信息, Feed信息)
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return f"未找到ID为{feed_id}的Feed", None
            
            return None, self._feed_to_dict(feed)
        except SQLAlchemyError as e:
            logger.error(f"获取Feed失败, ID={feed_id}: {str(e)}")
            return str(e), None

    def add_feed(self, feed_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """添加新Feed
        
        Args:
            feed_data: Feed数据
            
        Returns:
            (错误信息, 新增的Feed信息)
        """
        try:
            new_feed = RssFeed(**feed_data)
            self.db.add(new_feed)
            self.db.commit()
            self.db.refresh(new_feed)
            
            return None, self._feed_to_dict(new_feed)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"添加Feed失败: {str(e)}")
            return str(e), None

    def update_feed_status(self, feed_id: str, status: bool) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新Feed状态
        
        Args:
            feed_id: Feed ID
            status: 新状态
            
        Returns:
            (错误信息, 更新后的Feed信息)
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return f"未找到ID为{feed_id}的Feed", None
            
            feed.is_active = status
            self.db.commit()
            self.db.refresh(feed)
            
            return None, self._feed_to_dict(feed)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新Feed状态失败, ID={feed_id}: {str(e)}")
            return str(e), None

    def update_feed_fetch_status(
        self, feed_id: str, status: int, error_message: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新Feed获取状态
        
        Args:
            feed_id: Feed ID
            status: 状态(1=成功, 2=失败)
            error_message: 错误信息
            
        Returns:
            (错误信息, 更新后的Feed信息)
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return f"未找到ID为{feed_id}的Feed", None
            
            current_time = datetime.now()
            feed.last_fetch_at = current_time
            feed.last_fetch_status = status
            
            if status == 1:  # 成功
                feed.last_successful_fetch_at = current_time
                feed.consecutive_failures = 0
                feed.last_fetch_error = None
            else:  # 失败
                feed.consecutive_failures += 1
                feed.last_fetch_error = error_message
            
            self.db.commit()
            self.db.refresh(feed)
            
            return None, self._feed_to_dict(feed)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新Feed获取状态失败, ID={feed_id}: {str(e)}")
            return str(e), None

    def bulk_update_feeds_fetch_time(self, feed_ids: List[str]) -> Optional[str]:
        """批量更新Feed获取时间
        
        Args:
            feed_ids: Feed ID列表
            
        Returns:
            错误信息
        """
        try:
            self.db.query(RssFeed).filter(RssFeed.id.in_(feed_ids)).update(
                {RssFeed.last_fetch_at: datetime.now()},
                synchronize_session=False
            )
            self.db.commit()
            return None
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"批量更新Feed获取时间失败: {str(e)}")
            return str(e)

    def _feed_to_dict(self, feed: RssFeed) -> Dict[str, Any]:
        """将Feed对象转换为字典
        
        Args:
            feed: Feed对象
            
        Returns:
            Feed字典
        """
        return {
            "id": feed.id,
            "url": feed.url,
            "category_id": feed.category_id,

            "group_id": feed.group_id,
            "logo": feed.logo,
            "title": feed.title,
            "description": feed.description,
            "is_active": feed.is_active,
            "last_fetch_at": feed.last_fetch_at.isoformat() if feed.last_fetch_at else None,
            "last_fetch_status": feed.last_fetch_status,
            "last_fetch_error": feed.last_fetch_error,
            "last_successful_fetch_at": feed.last_successful_fetch_at.isoformat() if feed.last_successful_fetch_at else None,
            "total_articles_count": feed.total_articles_count,
            "consecutive_failures": feed.consecutive_failures,
            "created_at": feed.created_at.isoformat() if feed.created_at else None,
            "updated_at": feed.updated_at.isoformat() if feed.updated_at else None,
        }


class RssFeedCategoryRepository:
    """RSS Feed分类存储库"""

    def __init__(self, db_session: Session):
        """初始化存储库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """获取所有分类
        
        Returns:
            所有分类列表
        """
        try:
            categories = self.db.query(RssFeedCategory).all()
            return [self._category_to_dict(category) for category in categories]
        except SQLAlchemyError as e:
            logger.error(f"获取所有分类失败: {str(e)}")
            return []

    def _category_to_dict(self, category: RssFeedCategory) -> Dict[str, Any]:
        """将分类对象转换为字典
        
        Args:
            category: 分类对象
            
        Returns:
            分类字典
        """
        return {
            "id": category.id,
            "name": category.name,
            "is_delete": category.is_delete
        }


class RssFeedCollectionRepository:
    """RSS Feed集合存储库"""

    def __init__(self, db_session: Session):
        """初始化存储库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_all_collections(self) -> List[Dict[str, Any]]:
        """获取所有集合
        
        Returns:
            所有集合列表
        """
        try:
            collections = self.db.query(RssFeedCollection).all()
            return [self._collection_to_dict(collection) for collection in collections]
        except SQLAlchemyError as e:
            logger.error(f"获取所有集合失败: {str(e)}")
            return []

    def _collection_to_dict(self, collection: RssFeedCollection) -> Dict[str, Any]:
        """将集合对象转换为字典
        
        Args:
            collection: 集合对象
            
        Returns:
            集合字典
        """
        return {
            "id": collection.id,
            "name": collection.name,
            "is_delete": collection.is_delete
        }


class RssFeedArticleRepository:
    """RSS Feed文章存储库"""

    def __init__(self, db_session: Session):
        """初始化存储库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_articles(
        self, page: int = 1, per_page: int = 10, filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """获取文章列表
        
        Args:
            page: 页码
            per_page: 每页数量
            filters: 筛选条件
            
        Returns:
            分页的文章列表
        """
        try:
            query = self.db.query(RssFeedArticle)
            
            if filters:
                # 应用ID筛选
                if "id" in filters:
                    query = query.filter(RssFeedArticle.id == filters["id"])
                
                # 应用Feed ID筛选
                if "feed_id" in filters:
                    query = query.filter(RssFeedArticle.feed_id == filters["feed_id"])
                
                # 应用状态筛选
                if "status" in filters:
                    query = query.filter(RssFeedArticle.status == filters["status"])
                
                # 应用标题搜索
                if "title" in filters and filters["title"]:
                    query = query.filter(RssFeedArticle.title.ilike(f"%{filters['title']}%"))
                
                # 应用日期范围筛选
                if "date_range" in filters:
                    start_date, end_date = filters["date_range"]
                    if start_date:
                        query = query.filter(RssFeedArticle.published_date >= datetime.strptime(start_date, "%Y-%m-%d"))
                    if end_date:
                        query = query.filter(RssFeedArticle.published_date <= datetime.strptime(end_date, "%Y-%m-%d"))
                
                # 应用锁定状态筛选
                if "is_locked" in filters:
                    query = query.filter(RssFeedArticle.is_locked == filters["is_locked"])
                
                # 应用重试次数范围筛选
                if "retry_range" in filters:
                    min_retries, max_retries = filters["retry_range"]
                    if min_retries is not None:
                        query = query.filter(RssFeedArticle.retry_count >= min_retries)
                    if max_retries is not None:
                        query = query.filter(RssFeedArticle.retry_count <= max_retries)
            
            # 应用排序（按ID降序）
            query = query.order_by(desc(RssFeedArticle.id))
            
            # 计算总记录数
            total = query.count()
            
            # 应用分页
            items = query.limit(per_page).offset((page - 1) * per_page).all()
            items_dict = [self._article_to_dict(item) for item in items]
            
            # 计算总页数
            pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            return {
                "list": items_dict,
                "total": total,
                "pages": pages,
                "current_page": page,
                "per_page": per_page,
                "filters_applied": filters or {},
            }
        except SQLAlchemyError as e:
            logger.error(f"获取文章列表失败: {str(e)}")
            return {
                "list": [],
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "filters_applied": filters or {},
                "error": str(e)
            }

    def get_article_by_id(self, article_id: int) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """根据ID获取文章
        
        Args:
            article_id: 文章ID
            
        Returns:
            (错误信息, 文章信息)
        """
        try:
            article = self.db.query(RssFeedArticle).filter(RssFeedArticle.id == article_id).first()
            if not article:
                return f"未找到ID为{article_id}的文章", None
            
            return None, self._article_to_dict(article)
        except SQLAlchemyError as e:
            logger.error(f"获取文章失败, ID={article_id}: {str(e)}")
            return str(e), None

    def insert_articles(self, articles_data: List[Dict[str, Any]]) -> bool:
        """批量插入文章
        
        Args:
            articles_data: 文章数据列表
            
        Returns:
            是否成功
        """
        try:
            # 首先，按照published_date倒序排序
            sorted_articles_data = sorted(
                articles_data, key=lambda x: x["published_date"], reverse=True
            )
            
            # 获取所有链接
            links = [data["link"] for data in sorted_articles_data]
            
            # 检查是否存在相同链接的文章
            existing_links = self.db.query(RssFeedArticle.link).filter(RssFeedArticle.link.in_(links)).all()
            existing_links_set = {link[0] for link in existing_links}
            
            # 过滤出新文章
            new_articles_data = [
                data for data in sorted_articles_data 
                if data["link"] not in existing_links_set
            ]
            
            # 批量插入新文章
            for data in new_articles_data:
                article = RssFeedArticle(**data)
                self.db.add(article)
            
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"批量插入文章失败: {str(e)}")
            return False

    def _article_to_dict(self, article: RssFeedArticle) -> Dict[str, Any]:
        """将文章对象转换为字典
        
        Args:
            article: 文章对象
            
        Returns:
            文章字典
        """
        return {
            "id": article.id,
            "feed_id": article.feed_id,
            "feed_logo": article.feed_logo,
            "feed_title": article.feed_title,
            "link": article.link,
            "content_id": article.content_id,
            "status": article.status,
            "title": article.title,
            "summary": article.summary,
            "thumbnail_url": article.thumbnail_url,
            "published_date": article.published_date.isoformat() if article.published_date else None,
            "is_locked": article.is_locked,
            "lock_timestamp": article.lock_timestamp.isoformat() if article.lock_timestamp else None,
            "crawler_id": article.crawler_id,
            "retry_count": article.retry_count,
            "max_retries": article.max_retries,
            "error_message": article.error_message,
            "created_at": article.created_at.isoformat() if article.created_at else None,
            "updated_at": article.updated_at.isoformat() if article.updated_at else None,
        }


class RssFeedArticleContentRepository:
    """RSS Feed文章内容存储库"""

    def __init__(self, db_session: Session):
        """初始化存储库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_article_content(self, content_id: int) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """根据ID获取文章内容
        
        Args:
            content_id: 内容ID
            
        Returns:
            (错误信息, 内容信息)
        """
        try:
            content = self.db.query(RssFeedArticleContent).filter(RssFeedArticleContent.id == content_id).first()
            if not content:
                return f"未找到ID为{content_id}的文章内容", None
            
            return None, self._content_to_dict(content)
        except SQLAlchemyError as e:
            logger.error(f"获取文章内容失败, ID={content_id}: {str(e)}")
            return str(e), None

    def insert_article_content(self, content_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """插入文章内容
        
        Args:
            content_data: 内容数据
            
        Returns:
            (错误信息, 内容信息)
        """
        try:
            new_content = RssFeedArticleContent(**content_data)
            self.db.add(new_content)
            self.db.commit()
            self.db.refresh(new_content)
            
            return None, self._content_to_dict(new_content)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"插入文章内容失败: {str(e)}")
            return str(e), None

    def _content_to_dict(self, content: RssFeedArticleContent) -> Dict[str, Any]:
        """将内容对象转换为字典
        
        Args:
            content: 内容对象
            
        Returns:
            内容字典
        """
        return {
            "id": content.id,
            "html_content": content.html_content,
            "text_content": content.text_content,
            "created_at": content.created_at.isoformat() if content.created_at else None,
            "updated_at": content.updated_at.isoformat() if content.updated_at else None,
        }