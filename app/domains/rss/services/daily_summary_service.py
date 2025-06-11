# app/domains/rss/services/daily_summary_service.py

import logging
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy import and_, or_

from app.infrastructure.llm_providers.factory import LLMProviderFactory
from app.core.exceptions import APIException

logger = logging.getLogger(__name__)

class DailySummaryService:
    """RSS每日摘要服务"""
    
    def __init__(self, summary_repo, article_repo, feed_repo):
        """初始化服务"""
        self.summary_repo = summary_repo
        self.article_repo = article_repo
        self.feed_repo = feed_repo
    
    def generate_daily_summaries(self, target_date: date = None, languages: List[str] = None) -> Dict[str, Any]:
        """生成每日摘要
        
        Args:
            target_date: 目标日期，默认为昨天
            languages: 语言列表，默认为['zh', 'en']
            
        Returns:
            生成结果
        """
        if target_date is None:
            target_date = date.today() - timedelta(days=1)
        
        if languages is None:
            languages = ['zh', 'en']
        
        logger.info(f"开始生成 {target_date} 的每日摘要，语言: {languages}")
        
        result = {
            "target_date": target_date.isoformat(),
            "languages": languages,
            "total_feeds_processed": 0,
            "success_count": 0,
            "failed_count": 0,
            "details": []
        }
        
        for language in languages:
            logger.info(f"处理语言: {language}")
            
            # 获取需要生成摘要的Feed列表
            feeds_to_process = self.summary_repo.get_feeds_needing_summary(target_date, language)
            logger.info(f"找到 {len(feeds_to_process)} 个Feed需要生成{language}摘要")
            
            for feed_id in feeds_to_process:
                try:
                    summary_result = self._generate_feed_summary(feed_id, target_date, language)
                    result["success_count"] += 1
                    result["details"].append({
                        "feed_id": feed_id,
                        "language": language,
                        "status": "success",
                        "summary_id": summary_result.get("id"),
                        "article_count": summary_result.get("article_count", 0)
                    })
                except Exception as e:
                    logger.error(f"生成Feed {feed_id} {language}摘要失败: {str(e)}")
                    result["failed_count"] += 1
                    result["details"].append({
                        "feed_id": feed_id,
                        "language": language,
                        "status": "failed",
                        "error": str(e)
                    })
                
                result["total_feeds_processed"] += 1
        
        logger.info(f"每日摘要生成完成: 成功{result['success_count']}，失败{result['failed_count']}")
        return result
    
    def _generate_feed_summary(self, feed_id: str, target_date: date, language: str) -> Dict[str, Any]:
        """为特定Feed生成摘要
        
        Args:
            feed_id: Feed ID
            target_date: 目标日期
            language: 语言
            
        Returns:
            生成的摘要
        """
        # 1. 获取Feed信息
        err, feed = self.feed_repo.get_feed_by_id(feed_id)
        if err:
            raise Exception(f"获取Feed信息失败: {err}")
        
        # 2. 获取当日文章
        articles = self._get_feed_articles_by_date(feed_id, target_date)
        if not articles:
            raise Exception(f"Feed {feed_id} 在 {target_date} 没有文章")
        
        logger.info(f"Feed {feed['title']} 在 {target_date} 有 {len(articles)} 篇文章")
        
        # 3. 准备文章内容
        article_contents = []
        article_ids = []
        
        for article in articles:
            article_ids.append(article["id"])
            # 优先使用生成的摘要，其次使用原始摘要，最后使用标题
            content = article.get("generated_summary") or article.get("summary") or article.get("title", "")
            article_contents.append({
                "title": article.get("title", ""),
                "content": content[:500],  # 限制长度
                "published_date": article.get("published_date", "")
            })
        
        # 4. 生成摘要
        summary_data = self._generate_ai_summary(feed, article_contents, language)
        
        # 5. 保存摘要
        summary_record = {
            "feed_id": feed_id,
            "summary_date": target_date,
            "language": language,
            "summary_title": summary_data["title"],
            "summary_content": summary_data["content"],
            "article_count": len(articles),
            "article_ids": article_ids,
            "generated_by": "ai",
            "llm_provider": summary_data.get("provider"),
            "llm_model": summary_data.get("model"),
            "generation_cost_tokens": summary_data.get("tokens_used", 0)
        }
        
        err, saved_summary = self.summary_repo.create_summary(summary_record)
        if err:
            raise Exception(f"保存摘要失败: {err}")
        
        return saved_summary
    
    def _get_feed_articles_by_date(self, feed_id: str, target_date: date) -> List[Dict[str, Any]]:
        """获取Feed在指定日期的文章"""
        try:
            from app.infrastructure.database.models.rss import RssFeedArticle
            from sqlalchemy import and_, or_
            
            # 直接查询数据库，按发布日期筛选
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())
            
            logger.info(f"查询Feed {feed_id} 在 {start_datetime} 到 {end_datetime} 的文章")
            
            articles = self.article_repo.db.query(RssFeedArticle).filter(
                and_(
                    RssFeedArticle.feed_id == feed_id,
                    RssFeedArticle.status == 1,  # 只获取成功爬取的文章
                    # 优先使用published_date，如果为空则使用created_at
                    or_(
                        and_(
                            RssFeedArticle.published_date.isnot(None),
                            RssFeedArticle.published_date >= start_datetime,
                            RssFeedArticle.published_date <= end_datetime
                        ),
                        and_(
                            RssFeedArticle.published_date.is_(None),
                            RssFeedArticle.created_at >= start_datetime,
                            RssFeedArticle.created_at <= end_datetime
                        )
                    )
                )
            ).order_by(RssFeedArticle.published_date.desc()).all()
            
            logger.info(f"找到 {len(articles)} 篇文章")
            
            # 转换为字典格式
            result_articles = []
            for article in articles:
                result_articles.append({
                    "id": article.id,
                    "title": article.title,
                    "summary": article.summary,
                    "generated_summary": getattr(article, 'generated_summary', None),
                    "published_date": article.published_date.isoformat() if article.published_date else article.created_at.isoformat(),
                    "link": article.link
                })
            
            return result_articles
        except Exception as e:
            logger.error(f"获取Feed文章失败: {str(e)}", exc_info=True)
            return []
    
    def _generate_ai_summary(self, feed: Dict[str, Any], articles: List[Dict[str, Any]], language: str) -> Dict[str, Any]:
        """使用AI生成摘要
        
        Args:
            feed: Feed信息
            articles: 文章列表
            language: 目标语言
            
        Returns:
            生成的摘要数据
        """
        try:
            # 创建LLM提供商
            llm_provider = LLMProviderFactory.create_provider()
            
            # 构建提示词
            prompt = self._build_summary_prompt(feed, articles, language)
            
            # 调用LLM生成摘要
            response = llm_provider.generate_chat_completion(
                messages=[
                    {
                        "role": "system", 
                        "content": self._get_system_prompt(language)
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            # 解析响应
            summary_text = response["message"]["content"]
            
            # 尝试从JSON格式中提取标题和内容
            try:
                summary_json = json.loads(summary_text)
                title = summary_json.get("title", f"{feed['title']}每日摘要")
                content = summary_json.get("content", summary_text)
            except json.JSONDecodeError:
                # 如果不是JSON格式，直接使用文本
                title = f"{feed['title']}每日摘要"
                content = summary_text
            
            return {
                "title": title,
                "content": content,
                "provider": llm_provider.get_provider_name(),
                "model": getattr(llm_provider, 'default_model', 'unknown'),
                "tokens_used": response.get("usage", {}).get("total_tokens", 0)
            }
            
        except Exception as e:
            logger.error(f"AI生成摘要失败: {str(e)}")
            raise Exception(f"AI生成摘要失败: {str(e)}")
    
    def _get_system_prompt(self, language: str) -> str:
        """获取系统提示词"""
        if language == "zh":
            return """你是一个专业的新闻摘要生成器。请根据提供的RSS订阅源文章，生成一份简洁而全面的中文每日阅读摘要。

要求：
1. 摘要应该涵盖当天该订阅源的主要内容和亮点
2. 使用简洁明了的中文表达
3. 突出重要信息和趋势
4. 控制在200-300字以内
5. 返回JSON格式：{"title": "摘要标题", "content": "摘要内容"}

注意：如果文章数量较少，可以更详细地描述；如果文章很多，则提炼共同主题和重点。"""
        else:
            return """You are a professional news summarizer. Please generate a concise and comprehensive English daily reading summary based on the provided RSS feed articles.

Requirements:
1. The summary should cover the main content and highlights of the day for this feed
2. Use clear and concise English expression
3. Highlight important information and trends
4. Keep it within 200-300 words
5. Return in JSON format: {"title": "Summary Title", "content": "Summary Content"}

Note: If there are few articles, you can describe them in more detail; if there are many articles, extract common themes and key points."""
    
    def _build_summary_prompt(self, feed: Dict[str, Any], articles: List[Dict[str, Any]], language: str) -> str:
        """构建摘要生成提示词"""
        feed_title = feed.get("title", "未知订阅源")
        feed_desc = feed.get("description", "")
        
        # 构建文章列表文本
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"{i}. 标题：{article['title']}\n"
            if article['content']:
                articles_text += f"   内容：{article['content']}\n"
            articles_text += f"   发布时间：{article['published_date']}\n\n"
        
        if language == "zh":
            prompt = f"""
订阅源信息：
- 名称：{feed_title}
- 描述：{feed_desc}

今日文章列表（共{len(articles)}篇）：
{articles_text}

请为以上内容生成一份中文每日阅读摘要。"""
        else:
            prompt = f"""
Feed Information:
- Name: {feed_title}
- Description: {feed_desc}

Today's Articles (Total: {len(articles)}):
{articles_text}

Please generate an English daily reading summary for the above content."""
        
        return prompt
    
    def get_daily_summaries(self, target_date: date = None, language: str = "zh") -> List[Dict[str, Any]]:
        """获取每日摘要列表
        
        Args:
            target_date: 目标日期，默认为昨天
            language: 语言，默认为中文
            
        Returns:
            摘要列表
        """
        if target_date is None:
            target_date = date.today() - timedelta(days=1)
        
        summaries = self.summary_repo.get_summaries_by_date(target_date, language)
        
        # 为每个摘要补充Feed信息
        for summary in summaries:
            err, feed = self.feed_repo.get_feed_by_id(summary["feed_id"])
            if not err and feed:
                summary["feed_title"] = feed.get("title")
                summary["feed_logo"] = feed.get("logo")
                summary["feed_description"] = feed.get("description")
        
        return summaries