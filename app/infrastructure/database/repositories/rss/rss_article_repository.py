# app/infrastructure/database/repositories/rss_article_repository.py
"""RSS文章仓库"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, or_, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.rss import RssFeedArticle

logger = logging.getLogger(__name__)

class RssFeedArticleRepository:
    """RSS Feed文章仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
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
            
            # 应用排序（按发布日期降序）
            query = query.order_by(desc(RssFeedArticle.published_date))
            
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

    def reset_article(self, article_id: int) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """重置文章状态，允许重新抓取
        
        Args:
            article_id: 文章ID
            
        Returns:
            (错误信息, 重置后的文章信息)
        """
        try:
            article = self.db.query(RssFeedArticle).filter(RssFeedArticle.id == article_id).first()
            if not article:
                return f"未找到ID为{article_id}的文章", None
            
            # 重置文章状态
            article.is_locked = False
            article.lock_timestamp = None
            article.crawler_id = None
            article.status = 0  # 待抓取
            article.error_message = None
            
            self.db.commit()
            self.db.refresh(article)
            
            return None, self._article_to_dict(article)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"重置文章状态失败, ID={article_id}: {str(e)}")
            return str(e), None

    def lock_article(self, article_id: int, crawler_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """锁定文章进行抓取
        
        Args:
            article_id: 文章ID
            crawler_id: 爬虫标识
            
        Returns:
            (错误信息, 锁定后的文章信息)
        """
        try:
            article = self.db.query(RssFeedArticle).filter(
                RssFeedArticle.id == article_id,
                RssFeedArticle.is_locked == False  # 只锁定未被锁定的文章
            ).first()
            
            if not article:
                # 检查是否存在该文章
                exists = self.db.query(RssFeedArticle).filter(RssFeedArticle.id == article_id).first()
                if not exists:
                    return f"未找到ID为{article_id}的文章", None
                else:
                    return f"文章ID {article_id} 已被锁定", None
            
            # 锁定文章
            article.is_locked = True
            article.lock_timestamp = datetime.now()
            article.crawler_id = crawler_id
            
            self.db.commit()
            self.db.refresh(article)
            
            return None, self._article_to_dict(article)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"锁定文章失败, ID={article_id}: {str(e)}")
            return str(e), None

    def update_article_status(
        self, article_id: int, status: int, content_id: Optional[int] = None, error_message: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新文章状态
        
        Args:
            article_id: 文章ID
            status: 状态(1=成功, 2=失败)
            content_id: 内容ID(成功时提供)
            error_message: 错误信息(失败时提供)
            
        Returns:
            (错误信息, 更新后的文章信息)
        """
        try:
            article = self.db.query(RssFeedArticle).filter(RssFeedArticle.id == article_id).first()
            if not article:
                return f"未找到ID为{article_id}的文章", None
            
            # 更新文章状态
            article.status = status
            article.is_locked = False  # 解除锁定
            article.lock_timestamp = None
            
            if status == 1 and content_id:  # 成功
                article.content_id = content_id
                article.error_message = None
            elif status == 2:  # 失败
                article.retry_count += 1
                article.error_message = error_message
            
            self.db.commit()
            self.db.refresh(article)
            
            return None, self._article_to_dict(article)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新文章状态失败, ID={article_id}: {str(e)}")
            return str(e), None

    def get_pending_articles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取待抓取的文章
        
        Args:
            limit: 获取数量
            
        Returns:
            待抓取文章列表
        """
        try:
            articles = self.db.query(RssFeedArticle).filter(
                RssFeedArticle.status == 0,  # 待抓取
                RssFeedArticle.is_locked == False,  # 未锁定
                RssFeedArticle.retry_count < RssFeedArticle.max_retries  # 重试次数未达上限
            ).order_by(
                RssFeedArticle.retry_count,  # 优先未重试的
                desc(RssFeedArticle.published_date)  # 然后是最新发布的
            ).limit(limit).all()
            
            return [self._article_to_dict(article) for article in articles]
        except SQLAlchemyError as e:
            logger.error(f"获取待抓取文章失败: {str(e)}")
            return []
        
    def update_article_vectorization(self, article_id: int, update_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新文章向量化信息
        
        Args:
            article_id: 文章ID
            update_data: 更新数据
            
        Returns:
            (错误信息, 更新后的文章信息)
        """
        try:
            article = self.db.query(RssFeedArticle).filter(RssFeedArticle.id == article_id).first()
            if not article:
                return f"未找到ID为{article_id}的文章", None
            
            # 更新字段
            for key, value in update_data.items():
                if hasattr(article, key):
                    setattr(article, key, value)
            
            self.db.commit()
            self.db.refresh(article)
            
            return None, self._article_to_dict(article)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新文章向量化信息失败, ID={article_id}: {str(e)}")
            return str(e), None

    def update_article_vectorization_status(self, article_id: int, status: int, error_message: Optional[str] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新文章向量化状态
        
        Args:
            article_id: 文章ID
            status: 状态(0=未处理, 1=成功, 2=失败, 3=处理中)
            error_message: 错误信息(失败时提供)
            
        Returns:
            (错误信息, 更新后的文章信息)
        """
        try:
            article = self.db.query(RssFeedArticle).filter(RssFeedArticle.id == article_id).first()
            if not article:
                return f"未找到ID为{article_id}的文章", None
            
            # 更新状态
            article.vectorization_status = status
            
            if status == 1:  # 成功
                article.is_vectorized = True
                article.vectorized_at = datetime.now()
                article.vectorization_error = None
            elif status == 2:  # 失败
                article.is_vectorized = False
                article.vectorization_error = error_message
            elif status == 3:  # 处理中
                article.is_vectorized = False
                article.vectorization_error = None
            
            self.db.commit()
            self.db.refresh(article)
            
            return None, self._article_to_dict(article)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新文章向量化状态失败, ID={article_id}: {str(e)}")
            return str(e), None

    def get_articles_for_vectorization(self, limit: int = 10, status: int = 0) -> List[Dict[str, Any]]:
        """获取待向量化文章
        
        Args:
            limit: 获取数量
            status: 向量化状态(0=未处理, 1=成功, 2=失败, 3=处理中)
            
        Returns:
            待向量化文章列表
        """
        try:
            articles = self.db.query(RssFeedArticle).filter(
                RssFeedArticle.vectorization_status == status,  # 指定状态
                RssFeedArticle.content_id != None  # 确保有内容
            ).order_by(
                desc(RssFeedArticle.published_date)
            ).limit(limit).all()
            
            return [self._article_to_dict(article) for article in articles]
        except SQLAlchemyError as e:
            logger.error(f"获取待向量化文章失败: {str(e)}")
            return []

    def update_article_summaries(self, article_id: int, update_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新文章摘要信息
        
        Args:
            article_id: 文章ID
            update_data: 更新数据
            
        Returns:
            (错误信息, 更新后的文章信息)
        """
        try:
            article = self.db.query(RssFeedArticle).filter(RssFeedArticle.id == article_id).first()
            if not article:
                return f"未找到ID为{article_id}的文章", None
            
            # 更新字段
            for key, value in update_data.items():
                if hasattr(article, key):
                    setattr(article, key, value)
            
            # 更新时间
            article.updated_at = datetime.now()
            
            self.db.commit()
            self.db.refresh(article)
            
            return None, self._article_to_dict(article)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新文章摘要失败, ID={article_id}: {str(e)}")
            return str(e), None

    def update_article_fields(self, article_id: int, update_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新文章字段
        
        Args:
            article_id: 文章ID
            update_data: 更新数据
            
        Returns:
            (错误信息, 更新后的文章信息)
        """
        try:
            article = self.db.query(RssFeedArticle).filter(RssFeedArticle.id == article_id).first()
            if not article:
                return f"未找到ID为{article_id}的文章", None
            
            # 更新字段
            for key, value in update_data.items():
                if hasattr(article, key):
                    setattr(article, key, value)
                    logger.debug(f"更新字段 {key} = {value}")
                else:
                    logger.warning(f"文章模型不存在字段: {key}")
            
            # 更新时间
            article.updated_at = datetime.now()
            
            self.db.commit()
            self.db.refresh(article)
            
            logger.info(f"成功更新文章 {article_id} 的字段")
            return None, self._article_to_dict(article)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新文章字段失败, ID={article_id}: {str(e)}")
            return str(e), None
        
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
            "chinese_summary": getattr(article, 'chinese_summary', None),  # 新增字段
            "english_summary": getattr(article, 'english_summary', None),   # 新增字段
            "thumbnail_url": article.thumbnail_url,
            "published_date": article.published_date.isoformat() if article.published_date else None,
            "is_locked": article.is_locked,
            "lock_timestamp": article.lock_timestamp.isoformat() if article.lock_timestamp else None,
            "crawler_id": article.crawler_id,
            "vectorization_status": article.vectorization_status,
            "is_vectorized": article.is_vectorized,
            "vectorized_at": article.vectorized_at.isoformat() if article.vectorized_at else None,
            "vectorization_error": article.vectorization_error,
            "vector_id": article.vector_id,
            "retry_count": article.retry_count,
            "max_retries": article.max_retries,
            "error_message": article.error_message,
            "created_at": article.created_at.isoformat() if article.created_at else None,
            "updated_at": article.updated_at.isoformat() if article.updated_at else None,
        }