import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.rss import RssFeedDailySummary, RssFeedArticle

logger = logging.getLogger(__name__)

class RssFeedDailySummaryRepository:
    """RSS Feed每日摘要仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库"""
        self.db = db_session

    def create_summary(self, summary_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """创建每日摘要
        
        Args:
            summary_data: 摘要数据
            
        Returns:
            (错误信息, 创建的摘要)
        """
        try:
            # 检查是否已存在相同日期和语言的摘要
            existing = self.db.query(RssFeedDailySummary).filter(
                RssFeedDailySummary.feed_id == summary_data["feed_id"],
                RssFeedDailySummary.summary_date == summary_data["summary_date"],
                RssFeedDailySummary.language == summary_data["language"],
                RssFeedDailySummary.status == 1
            ).first()
            
            if existing:
                return f"该Feed在{summary_data['summary_date']}的{summary_data['language']}摘要已存在", None
            
            # 创建新摘要
            summary = RssFeedDailySummary(**summary_data)
            self.db.add(summary)
            self.db.commit()
            self.db.refresh(summary)
            
            return None, self._summary_to_dict(summary)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"创建每日摘要失败: {str(e)}")
            return str(e), None

    def get_summaries_by_date(self, target_date: date, language: str = None) -> List[Dict[str, Any]]:
        """获取指定日期的所有摘要
        
        Args:
            target_date: 目标日期
            language: 语言过滤，可选
            
        Returns:
            摘要列表
        """
        try:
            query = self.db.query(RssFeedDailySummary).filter(
                RssFeedDailySummary.summary_date == target_date,
                RssFeedDailySummary.status == 1
            )
            
            if language:
                query = query.filter(RssFeedDailySummary.language == language)
            
            summaries = query.order_by(desc(RssFeedDailySummary.created_at)).all()
            return [self._summary_to_dict(summary) for summary in summaries]
        except SQLAlchemyError as e:
            logger.error(f"获取每日摘要失败: {str(e)}")
            return []

    def get_feed_summary(self, feed_id: str, target_date: date, language: str) -> Optional[Dict[str, Any]]:
        """获取特定Feed的摘要
        
        Args:
            feed_id: Feed ID
            target_date: 目标日期
            language: 语言
            
        Returns:
            摘要信息
        """
        try:
            summary = self.db.query(RssFeedDailySummary).filter(
                RssFeedDailySummary.feed_id == feed_id,
                RssFeedDailySummary.summary_date == target_date,
                RssFeedDailySummary.language == language,
                RssFeedDailySummary.status == 1
            ).first()
            
            return self._summary_to_dict(summary) if summary else None
        except SQLAlchemyError as e:
            logger.error(f"获取Feed摘要失败: {str(e)}")
            return None

    def get_feeds_needing_summary(self, target_date: date, language: str) -> List[str]:
        """获取需要生成摘要的Feed列表
        
        Args:
            target_date: 目标日期
            language: 语言
            
        Returns:
            需要生成摘要的Feed ID列表
        """
        try:
            # 获取在指定日期有文章的Feed
            feeds_with_articles = self.db.query(RssFeedArticle.feed_id).filter(
                func.date(RssFeedArticle.published_date) == target_date,
                RssFeedArticle.status == 1  # 只考虑已成功爬取的文章
            ).distinct().subquery()
            
            # 获取已经有摘要的Feed
            feeds_with_summaries = self.db.query(RssFeedDailySummary.feed_id).filter(
                RssFeedDailySummary.summary_date == target_date,
                RssFeedDailySummary.language == language,
                RssFeedDailySummary.status == 1
            ).distinct().subquery()
            
            # 找出需要生成摘要的Feed（有文章但没有摘要的）
            feeds_needing_summary = self.db.query(feeds_with_articles.c.feed_id).filter(
                ~feeds_with_articles.c.feed_id.in_(
                    self.db.query(feeds_with_summaries.c.feed_id)
                )
            ).all()
            
            return [feed[0] for feed in feeds_needing_summary]
        except SQLAlchemyError as e:
            logger.error(f"获取需要生成摘要的Feed列表失败: {str(e)}")
            return []

    def _summary_to_dict(self, summary: RssFeedDailySummary) -> Dict[str, Any]:
        """将摘要对象转换为字典"""
        return {
            "id": summary.id,
            "feed_id": summary.feed_id,
            "summary_date": summary.summary_date.isoformat() if summary.summary_date else None,
            "language": summary.language,
            "summary_title": summary.summary_title,
            "summary_content": summary.summary_content,
            "article_count": summary.article_count,
            "article_ids": summary.article_ids,
            "generated_by": summary.generated_by,
            "llm_provider": summary.llm_provider,
            "llm_model": summary.llm_model,
            "generation_cost_tokens": summary.generation_cost_tokens,
            "status": summary.status,
            "quality_score": summary.quality_score,
            "created_at": summary.created_at.isoformat() if summary.created_at else None,
            "updated_at": summary.updated_at.isoformat() if summary.updated_at else None,
        }
