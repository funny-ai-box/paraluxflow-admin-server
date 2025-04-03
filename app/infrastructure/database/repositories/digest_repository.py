"""摘要相关存储库"""
# 插入repositories/digest_repository.py的内容
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union

from sqlalchemy import and_, or_, desc, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.digest import (
    ArticleDigest,
    DigestRule,
    DigestArticleMapping
)
from app.infrastructure.database.models.rss import RssFeedArticle
from app.core.exceptions import NotFoundException, ValidationException
from app.core.status_codes import NOT_FOUND, PARAMETER_ERROR

logger = logging.getLogger(__name__)


class DigestRepository:
    """摘要存储库"""

    def __init__(self, db_session: Session):
        """初始化存储库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_digests(
        self, user_id: str, page: int = 1, per_page: int = 10, filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """获取摘要列表
        
        Args:
            user_id: 用户ID
            page: 页码
            per_page: 每页数量
            filters: 筛选条件
            
        Returns:
            分页结果
        """
        try:
            query = self.db.query(ArticleDigest).filter(ArticleDigest.user_id == user_id)
            
            # 应用筛选条件
            if filters:
                if "digest_type" in filters:
                    query = query.filter(ArticleDigest.digest_type == filters["digest_type"])
                if "status" in filters:
                    query = query.filter(ArticleDigest.status == filters["status"])
                if "date_range" in filters and filters["date_range"]:
                    start_date, end_date = filters["date_range"]
                    if start_date:
                        query = query.filter(ArticleDigest.source_date >= start_date)
                    if end_date:
                        query = query.filter(ArticleDigest.source_date <= end_date)
                if "title" in filters and filters["title"]:
                    query = query.filter(ArticleDigest.title.like(f"%{filters['title']}%"))
            
            # 计算总记录数
            total = query.count()
            
            # 分页查询
            query = query.order_by(desc(ArticleDigest.created_at))
            digests = query.limit(per_page).offset((page - 1) * per_page).all()
            
            # 转换为字典列表
            result = []
            for digest in digests:
                result.append(self._digest_to_dict(digest))
            
            # 计算总页数
            pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            return {
                "list": result,
                "total": total,
                "pages": pages,
                "current_page": page,
                "per_page": per_page
            }
        except SQLAlchemyError as e:
            logger.error(f"获取摘要列表失败: {str(e)}")
            raise

    def get_digest_by_id(self, digest_id: str, user_id: str) -> Dict[str, Any]:
        """获取摘要详情
        
        Args:
            digest_id: 摘要ID
            user_id: 用户ID
            
        Returns:
            摘要详情
            
        Raises:
            NotFoundException: 摘要不存在
        """
        try:
            digest = self.db.query(ArticleDigest).filter(
                ArticleDigest.id == digest_id,
                ArticleDigest.user_id == user_id
            ).first()
            
            if not digest:
                raise NotFoundException(f"未找到ID为{digest_id}的摘要")
            
            # 获取摘要中的文章
            article_mappings = self.db.query(DigestArticleMapping).filter(
                DigestArticleMapping.digest_id == digest_id
            ).order_by(DigestArticleMapping.section, DigestArticleMapping.rank).all()
            
            # 获取文章ID列表
            article_ids = [mapping.article_id for mapping in article_mappings]
            
            # 查询文章详情
            articles = {}
            if article_ids:
                article_records = self.db.query(RssFeedArticle).filter(
                    RssFeedArticle.id.in_(article_ids)
                ).all()
                
                # 构建ID到文章的映射
                for article in article_records:
                    articles[article.id] = {
                        "id": article.id,
                        "title": article.title,
                        "feed_title": article.feed_title,
                        "feed_logo": article.feed_logo,
                        "link": article.link,
                        "summary": article.summary,
                        "published_date": article.published_date.isoformat() if article.published_date else None
                    }
            
            # 构建分类文章映射
            sections = {}
            for mapping in article_mappings:
                section = mapping.section or "未分类"
                if section not in sections:
                    sections[section] = []
                
                if mapping.article_id in articles:
                    article_info = articles[mapping.article_id].copy()
                    article_info["digest_summary"] = mapping.summary
                    article_info["rank"] = mapping.rank
                    sections[section].append(article_info)
            
            # 转换摘要为字典
            result = self._digest_to_dict(digest)
            result["sections"] = sections
            
            return result
        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"获取摘要详情失败: {str(e)}")
            raise

    def create_digest(self, data: Dict[str, Any]) -> ArticleDigest:
        """创建摘要
        
        Args:
            data: 摘要数据
            
        Returns:
            创建的摘要
            
        Raises:
            SQLAlchemyError: 数据库错误
        """
        try:
            digest = ArticleDigest(**data)
            self.db.add(digest)
            self.db.commit()
            self.db.refresh(digest)
            return digest
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建摘要失败: {str(e)}")
            raise

    def update_digest(self, digest_id: str, user_id: str, data: Dict[str, Any]) -> ArticleDigest:
        """更新摘要
        
        Args:
            digest_id: 摘要ID
            user_id: 用户ID
            data: 要更新的数据
            
        Returns:
            更新后的摘要
            
        Raises:
            NotFoundException: 摘要不存在
            SQLAlchemyError: 数据库错误
        """
        try:
            digest = self.db.query(ArticleDigest).filter(
                ArticleDigest.id == digest_id,
                ArticleDigest.user_id == user_id
            ).first()
            
            if not digest:
                raise NotFoundException(f"未找到ID为{digest_id}的摘要")
            
            # 更新字段
            for key, value in data.items():
                if hasattr(digest, key):
                    setattr(digest, key, value)
            
            self.db.commit()
            self.db.refresh(digest)
            return digest
        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新摘要失败: {str(e)}")
            raise

    def add_article_to_digest(self, digest_id: str, article_id: int, section: str = None, summary: str = None, rank: int = 0) -> DigestArticleMapping:
        """添加文章到摘要
        
        Args:
            digest_id: 摘要ID
            article_id: 文章ID
            section: 分类
            summary: 摘要
            rank: 排序
            
        Returns:
            创建的映射
            
        Raises:
            SQLAlchemyError: 数据库错误
        """
        try:
            mapping = DigestArticleMapping(
                digest_id=digest_id,
                article_id=article_id,
                section=section,
                summary=summary,
                rank=rank
            )
            self.db.add(mapping)
            self.db.commit()
            
            # 更新摘要的文章数量
            digest = self.db.query(ArticleDigest).filter(ArticleDigest.id == digest_id).first()
            if digest:
                digest.article_count = self.db.query(DigestArticleMapping).filter(
                    DigestArticleMapping.digest_id == digest_id
                ).count()
                self.db.commit()
            
            return mapping
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"添加文章到摘要失败: {str(e)}")
            raise

    def get_articles_for_digest(self, user_id: str, date: datetime, rules: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """获取指定日期可用于摘要的文章
        
        Args:
            user_id: 用户ID
            date: 日期
            rules: 规则条件
            
        Returns:
            文章列表
        """
        try:
            # 默认获取指定日期的文章
            next_day = date + timedelta(days=1)
            query = self.db.query(RssFeedArticle).filter(
                RssFeedArticle.published_date >= date,
                RssFeedArticle.published_date < next_day,
                RssFeedArticle.status == 1  # 确保文章状态正常
            )
            
            # 应用规则条件
            if rules:
                # 按Feed过滤
                if "feed_ids" in rules and rules["feed_ids"]:
                    query = query.filter(RssFeedArticle.feed_id.in_(rules["feed_ids"]))
                
                # 按关键词过滤
                if "keywords" in rules and rules["keywords"]:
                    keyword_conditions = []
                    for keyword in rules["keywords"]:
                        keyword_conditions.append(RssFeedArticle.title.like(f"%{keyword}%"))
                        keyword_conditions.append(RssFeedArticle.summary.like(f"%{keyword}%"))
                    query = query.filter(or_(*keyword_conditions))
            
            # 获取文章
            articles = query.order_by(desc(RssFeedArticle.published_date)).all()
            
            # 转换为字典列表
            result = []
            for article in articles:
                result.append({
                    "id": article.id,
                    "feed_id": article.feed_id,
                    "feed_title": article.feed_title,
                    "feed_logo": article.feed_logo,
                    "title": article.title,
                    "summary": article.summary,
                    "link": article.link,
                    "published_date": article.published_date.isoformat() if article.published_date else None
                })
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"获取用于摘要的文章失败: {str(e)}")
            raise

    def get_digest_rule(self, rule_id: str, user_id: str) -> Dict[str, Any]:
        """获取摘要规则
        
        Args:
            rule_id: 规则ID
            user_id: 用户ID
            
        Returns:
            规则详情
            
        Raises:
            NotFoundException: 规则不存在
        """
        try:
            rule = self.db.query(DigestRule).filter(
                DigestRule.id == rule_id,
                DigestRule.user_id == user_id
            ).first()
            
            if not rule:
                raise NotFoundException(f"未找到ID为{rule_id}的规则")
            
            return self._rule_to_dict(rule)
        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"获取摘要规则失败: {str(e)}")
            raise

    def get_digest_rules(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有摘要规则
        
        Args:
            user_id: 用户ID
            
        Returns:
            规则列表
        """
        try:
            rules = self.db.query(DigestRule).filter(
                DigestRule.user_id == user_id
            ).order_by(DigestRule.created_at.desc()).all()
            
            return [self._rule_to_dict(rule) for rule in rules]
        except SQLAlchemyError as e:
            logger.error(f"获取摘要规则列表失败: {str(e)}")
            raise

    def create_digest_rule(self, data: Dict[str, Any]) -> DigestRule:
        """创建摘要规则
        
        Args:
            data: 规则数据
            
        Returns:
            创建的规则
            
        Raises:
            SQLAlchemyError: 数据库错误
        """
        try:
            rule = DigestRule(**data)
            self.db.add(rule)
            self.db.commit()
            self.db.refresh(rule)
            return rule
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建摘要规则失败: {str(e)}")
            raise

    def update_digest_rule(self, rule_id: str, user_id: str, data: Dict[str, Any]) -> DigestRule:
        """更新摘要规则
        
        Args:
            rule_id: 规则ID
            user_id: 用户ID
            data: 要更新的数据
            
        Returns:
            更新后的规则
            
        Raises:
            NotFoundException: 规则不存在
            SQLAlchemyError: 数据库错误
        """
        try:
            rule = self.db.query(DigestRule).filter(
                DigestRule.id == rule_id,
                DigestRule.user_id == user_id
            ).first()
            
            if not rule:
                raise NotFoundException(f"未找到ID为{rule_id}的规则")
            
            # 更新字段
            for key, value in data.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            
            self.db.commit()
            self.db.refresh(rule)
            return rule
        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新摘要规则失败: {str(e)}")
            raise

    def delete_digest_rule(self, rule_id: str, user_id: str) -> bool:
        """删除摘要规则
        
        Args:
            rule_id: 规则ID
            user_id: 用户ID
            
        Returns:
            是否成功
            
        Raises:
            NotFoundException: 规则不存在
            SQLAlchemyError: 数据库错误
        """
        try:
            rule = self.db.query(DigestRule).filter(
                DigestRule.id == rule_id,
                DigestRule.user_id == user_id
            ).first()
            
            if not rule:
                raise NotFoundException(f"未找到ID为{rule_id}的规则")
            
            self.db.delete(rule)
            self.db.commit()
            return True
        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"删除摘要规则失败: {str(e)}")
            raise

    def _digest_to_dict(self, digest: ArticleDigest) -> Dict[str, Any]:
        """将摘要对象转换为字典
        
        Args:
            digest: 摘要对象
            
        Returns:
            字典表示
        """
        return {
            "id": digest.id,
            "user_id": digest.user_id,
            "title": digest.title,
            "content": digest.content,
            "article_count": digest.article_count,
            "source_date": digest.source_date.isoformat() if digest.source_date else None,
            "digest_type": digest.digest_type,
            "metadata": digest.metadata,
            "status": digest.status,
            "error_message": digest.error_message,
            "created_at": digest.created_at.isoformat() if digest.created_at else None,
            "updated_at": digest.updated_at.isoformat() if digest.updated_at else None
        }

    def _rule_to_dict(self, rule: DigestRule) -> Dict[str, Any]:
        """将规则对象转换为字典
        
        Args:
            rule: 规则对象
            
        Returns:
            字典表示
        """
        return {
            "id": rule.id,
            "user_id": rule.user_id,
            "name": rule.name,
            "digest_type": rule.digest_type,
            "feed_filter": rule.feed_filter,
            "article_filter": rule.article_filter,
            "summary_length": rule.summary_length,
            "include_categories": rule.include_categories,
            "include_keywords": rule.include_keywords,
            "provider_config_id": rule.provider_config_id,
            "schedule_time": rule.schedule_time,
            "is_active": rule.is_active,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "updated_at": rule.updated_at.isoformat() if rule.updated_at else None
        }