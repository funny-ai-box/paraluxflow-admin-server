"""摘要服务实现"""
# 插入services/digest_service.py的内容
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union

from app.core.exceptions import APIException, ValidationException
from app.core.status_codes import EXTERNAL_API_ERROR, PARAMETER_ERROR
from app.infrastructure.database.repositories.digest_repository import DigestRepository
from app.infrastructure.database.repositories.rss_repository import RssFeedArticleRepository, RssFeedArticleContentRepository
from app.infrastructure.database.repositories.llm_repository import LLMProviderConfigRepository
from app.infrastructure.llm_providers.factory import LLMProviderFactory

logger = logging.getLogger(__name__)


class DigestService:
    """摘要服务，处理文章摘要生成和管理"""
    
    def __init__(
        self, 
        digest_repo: DigestRepository, 
        article_repo: Optional[RssFeedArticleRepository] = None,
        article_content_repo: Optional[RssFeedArticleContentRepository] = None,
        llm_config_repo: Optional[LLMProviderConfigRepository] = None
    ):
        """初始化服务
        
        Args:
            digest_repo: 摘要存储库
            article_repo: 文章存储库(可选)
            article_content_repo: 文章内容存储库(可选)
            llm_config_repo: LLM配置存储库(可选)
        """
        self.digest_repo = digest_repo
        self.article_repo = article_repo
        self.article_content_repo = article_content_repo
        self.llm_config_repo = llm_config_repo
    
    def generate_daily_digest(
        self, 
        user_id: str, 
        date: Optional[datetime] = None, 
        rule_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成每日摘要
        
        Args:
            user_id: 用户ID
            date: 日期，默认为前一天
            rule_id: 规则ID，不提供则使用默认规则
            
        Returns:
            生成的摘要信息
            
        Raises:
            ValidationException: 参数验证失败
            APIException: 生成失败
        """
        try:
            # 确定日期，默认为前一天
            if not date:
                date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            
            # 获取规则
            rule = None
            if rule_id:
                rule = self.digest_repo.get_digest_rule(rule_id, user_id)
            else:
                # 获取用户的默认规则
                rules = self.digest_repo.get_digest_rules(user_id)
                for r in rules:
                    if r["is_active"] and r["digest_type"] == "daily":
                        rule = r
                        break
            
            if not rule:
                # 使用默认设置
                rule = {
                    "digest_type": "daily",
                    "feed_filter": None,
                    "article_filter": None,
                    "summary_length": 300,
                    "include_categories": True,
                    "include_keywords": True,
                    "provider_config_id": None
                }
            
            # 检查是否已存在当天的摘要
            existing_digests = self.digest_repo.get_digests(
                user_id, 
                filters={
                    "digest_type": "daily",
                    "date_range": (date.strftime("%Y-%m-%d"), date.strftime("%Y-%m-%d"))
                }
            )
            
            if existing_digests["total"] > 0:
                return {"message": "当天的摘要已存在", "digest_id": existing_digests["list"][0]["id"]}
            
            # 获取文章
            articles = self.digest_repo.get_articles_for_digest(
                user_id, 
                date, 
                {
                    "feed_ids": rule.get("feed_filter", {}).get("feed_ids"),
                    "keywords": rule.get("article_filter", {}).get("keywords")
                }
            )
            
            if not articles:
                return {"message": "没有找到符合条件的文章", "articles_count": 0}
            
            # 创建摘要
            digest_title = f"{date.strftime('%Y-%m-%d')}阅读摘要"
            
            digest = self.digest_repo.create_digest({
                "user_id": user_id,
                "title": digest_title,
                "content": "正在生成中...",
                "article_count": len(articles),
                "source_date": date,
                "digest_type": "daily",
                "status": 0,  # 生成中
                "metadata": {
                    "rule_id": rule.get("id"),
                    "article_count": len(articles),
                    "generation_started_at": datetime.now().isoformat()
                }
            })
            
            # 获取LLM配置
            llm_provider = None
            llm_config = None
            
            if rule.get("provider_config_id") and self.llm_config_repo:
                try:
                    llm_config = self.llm_config_repo.get_by_id(rule["provider_config_id"], user_id)
                    
                    # 初始化LLM提供商
                    provider_config = {
                        "default_model": llm_config.get("default_model", ""),
                        "max_retries": llm_config.get("max_retries", 3),
                        "timeout": llm_config.get("request_timeout", 60)
                    }
                    
                    llm_provider = LLMProviderFactory.create_provider(
                        llm_config["provider_type"],
                        llm_config["api_key"],
                        **provider_config
                    )
                except Exception as e:
                    logger.error(f"初始化LLM提供商失败: {str(e)}")
                    # 继续执行，使用默认摘要方法
            
            # 处理文章，按Feed分组
            feed_groups = {}
            for article in articles:
                feed_id = article["feed_id"]
                feed_title = article["feed_title"]
                
                if feed_id not in feed_groups:
                    feed_groups[feed_id] = {
                        "title": feed_title,
                        "articles": []
                    }
                
                feed_groups[feed_id]["articles"].append(article)
            
            # 处理每个Feed分组，添加到摘要
            for feed_id, group in feed_groups.items():
                for i, article in enumerate(group["articles"][:10]):  # 每个Feed最多取10篇
                    # 添加文章到摘要
                    self.digest_repo.add_article_to_digest(
                        digest.id,
                        article["id"],
                        section=group["title"],
                        rank=i
                    )
            
            # 生成摘要内容
            digest_content = self._generate_digest_content(
                articles, 
                feed_groups,
                rule,
                date,
                llm_provider
            )
            self.digest_repo.update_digest(digest.id, user_id, {
                "content": digest_content,
                "status": 1,  # 已完成
                "metadata": {
                    **digest.metadata,
                    "generation_completed_at": datetime.now().isoformat(),
                    "used_llm": llm_provider.get_provider_name() if llm_provider else "none"
                }
            })
            
            return {
                "message": "摘要生成成功",
                "digest_id": digest.id,
                "title": digest_title,
                "article_count": len(articles)
            }
        except ValidationException as e:
            raise e
        except Exception as e:
            logger.error(f"生成摘要失败: {str(e)}")
            # 如果摘要已创建，更新状态为失败
            if 'digest' in locals() and digest:
                try:
                    self.digest_repo.update_digest(digest.id, user_id, {
                        "status": 2,  # 失败
                        "error_message": str(e),
                        "metadata": {
                            **digest.metadata,
                            "error_at": datetime.now().isoformat()
                        }
                    })
                except Exception as update_error:
                    logger.error(f"更新摘要状态失败: {str(update_error)}")
            
            raise APIException(f"生成摘要失败: {str(e)}", EXTERNAL_API_ERROR)
    
    def _generate_digest_content(
        self, 
        articles: List[Dict[str, Any]], 
        feed_groups: Dict[str, Any], 
        rule: Dict[str, Any], 
        date: datetime,
        llm_provider = None
    ) -> str:
        """生成摘要内容
        
        Args:
            articles: 文章列表
            feed_groups: 按Feed分组的文章
            rule: 摘要规则
            date: 日期
            llm_provider: LLM提供商(可选)
            
        Returns:
            摘要内容
        """
        try:
            # 如果有LLM提供商，使用LLM生成摘要
            if llm_provider:
                return self._generate_digest_with_llm(articles, feed_groups, rule, date, llm_provider)
            
            # 否则使用简单方法生成摘要
            return self._generate_simple_digest(articles, feed_groups, rule, date)
        except Exception as e:
            logger.error(f"生成摘要内容失败: {str(e)}")
            # 生成简单摘要作为后备
            return self._generate_simple_digest(articles, feed_groups, rule, date)
    
    def _generate_digest_with_llm(
        self, 
        articles: List[Dict[str, Any]], 
        feed_groups: Dict[str, Any], 
        rule: Dict[str, Any], 
        date: datetime,
        llm_provider
    ) -> str:
        """使用LLM生成摘要
        
        Args:
            articles: 文章列表
            feed_groups: 按Feed分组的文章
            rule: 摘要规则
            date: 日期
            llm_provider: LLM提供商
            
        Returns:
            摘要内容
        """
        try:
            # 构建提示词
            date_str = date.strftime("%Y年%m月%d日")
            
            # 准备文章内容
            articles_text = []
            for feed_id, group in feed_groups.items():
                articles_text.append(f"## {group['title']}")
                for i, article in enumerate(group["articles"][:5]):  # 每个分类最多取5篇
                    title = article["title"]
                    summary = article["summary"] or ""
                    articles_text.append(f"{i+1}. {title}\n   {summary[:200]}...")
            
            articles_content = "\n\n".join(articles_text)
            
            # 构建完整提示词
            prompt = f"""你是一位专业的内容编辑，请为用户生成{date_str}的阅读摘要。以下是用户订阅的内容更新:

{articles_content}

请基于以上内容，生成一份每日阅读摘要，要求:
1. 提炼出重要的信息和热点话题
2. 按照内容分类组织
3. 提供简明扼要的总结
4. 包含每个主题的关键信息
5. 摘要应该是中文的，格式整洁清晰

请直接生成摘要内容，不需要额外的解释。"""

            # 调用LLM生成摘要
            response = llm_provider.generate_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.7
            )
            
            if "message" in response and "content" in response["message"]:
                return response["message"]["content"]
            
            # 如果调用失败，返回简单摘要
            return self._generate_simple_digest(articles, feed_groups, rule, date)
        except Exception as e:
            logger.error(f"使用LLM生成摘要失败: {str(e)}")
            # 返回简单摘要作为后备
            return self._generate_simple_digest(articles, feed_groups, rule, date)
    
    def _generate_simple_digest(
        self, 
        articles: List[Dict[str, Any]], 
        feed_groups: Dict[str, Any], 
        rule: Dict[str, Any], 
        date: datetime
    ) -> str:
        """生成简单摘要
        
        Args:
            articles: 文章列表
            feed_groups: 按Feed分组的文章
            rule: 摘要规则
            date: 日期
            
        Returns:
            摘要内容
        """
        date_str = date.strftime("%Y年%m月%d日")
        
        # 生成简单摘要内容
        content_parts = [f"# {date_str}阅读摘要", ""]
        
        # 总览部分
        content_parts.append(f"今日共有{len(articles)}篇文章更新，来自{len(feed_groups)}个订阅源。")
        content_parts.append("")
        
        # 热门关键词（简单实现，实际中可能需要更复杂的NLP）
        if rule.get("include_keywords", True):
            word_counts = {}
            for article in articles:
                title = article["title"] or ""
                words = title.split()
                for word in words:
                    if len(word) > 1:
                        word_counts[word] = word_counts.get(word, 0) + 1
            
            # 取出现频率最高的前10个词
            top_keywords = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            if top_keywords:
                keywords_str = ", ".join([word for word, _ in top_keywords])
                content_parts.append(f"## 热门关键词")
                content_parts.append(keywords_str)
                content_parts.append("")
        
        # 按Feed分组展示文章
        if rule.get("include_categories", True):
            content_parts.append("## 文章摘要")
            content_parts.append("")
            
            for feed_id, group in feed_groups.items():
                content_parts.append(f"### {group['title']}")
                for i, article in enumerate(group["articles"][:10]):  # 每个Feed最多显示10篇
                    title = article["title"] or "无标题"
                    summary = article["summary"] or "无摘要"
                    # 处理摘要长度
                    if summary and len(summary) > rule.get("summary_length", 300):
                        summary = summary[:rule.get("summary_length", 300)] + "..."
                    
                    content_parts.append(f"**{i+1}. {title}**")
                    content_parts.append(f"{summary}")
                    content_parts.append("")
        
        # 构建完整内容
        return "\n".join(content_parts)
    
    def update_digest(self, digest_id: str, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新摘要
        
        Args:
            digest_id: 摘要ID
            user_id: 用户ID
            data: 更新数据
            
        Returns:
            更新后的摘要
            
        Raises:
            NotFoundException: 摘要不存在
        """
        try:
            # 更新摘要
            digest = self.digest_repo.update_digest(digest_id, user_id, data)
            
            return self.digest_repo.get_digest_by_id(digest_id, user_id)
        except Exception as e:
            logger.error(f"更新摘要失败: {str(e)}")
            raise
    
    def create_or_update_rule(self, user_id: str, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建或更新摘要规则
        
        Args:
            user_id: 用户ID
            rule_data: 规则数据
            
        Returns:
            创建或更新的规则
        """
        try:
            # 确保用户ID
            rule_data["user_id"] = user_id
            
            # 如果有ID，更新规则
            if "id" in rule_data and rule_data["id"]:
                rule = self.digest_repo.update_digest_rule(rule_data["id"], user_id, rule_data)
            else:
                # 否则创建新规则
                rule = self.digest_repo.create_digest_rule(rule_data)
            
            return self.digest_repo._rule_to_dict(rule)
        except Exception as e:
            logger.error(f"创建或更新规则失败: {str(e)}")
            raise