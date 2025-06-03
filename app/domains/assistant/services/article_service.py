# app/domains/assistant/services/streaming_article_service.py
"""支持流式输出的AI助手文章处理服务"""
import json
import logging
from typing import Dict, Any, Optional, Generator, Tuple
from datetime import datetime

from app.infrastructure.llm_providers.factory import LLMProviderFactory
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.user_preferences_repository import UserPreferencesRepository
from app.domains.user.services.preferences_service import UserPreferencesService
from app.core.exceptions import ValidationException, NotFoundException
from app.core.status_codes import PARAMETER_ERROR, NOT_FOUND

logger = logging.getLogger(__name__)

class AssistantArticleService:
    """支持流式输出的AI助手文章处理服务"""
    
    # 支持的语言映射
    LANGUAGE_MAPPING = {
        "zh-CN": "中文（简体）",
        "zh-TW": "中文（繁体）",
        "en": "英文",
        "en-US": "英文",
        "ja": "日文",
        "ko": "韩文",
        "fr": "法文",
        "de": "德文",
        "es": "西班牙文",
        "ru": "俄文",
        "ar": "阿拉伯文",
        "pt": "葡萄牙文",
        "it": "意大利文",
        "th": "泰文",
        "vi": "越南文"
    }
    
    def __init__(
        self,
        article_repo: RssFeedArticleRepository,
        content_repo: RssFeedArticleContentRepository,
        preferences_repo: UserPreferencesRepository
    ):
        """初始化服务
        
        Args:
            article_repo: 文章仓库
            content_repo: 内容仓库
            preferences_repo: 用户偏好仓库
        """
        self.article_repo = article_repo
        self.content_repo = content_repo
        self.preferences_service = UserPreferencesService(preferences_repo)
    
    def _get_article_and_content(self, article_id: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """获取文章和内容信息
        
        Args:
            article_id: 文章ID
            
        Returns:
            (文章信息, 内容信息)
            
        Raises:
            NotFoundException: 文章不存在
            ValidationException: 文章内容不存在
        """
        # 获取文章信息
        err, article = self.article_repo.get_article_by_id(article_id)
        if err:
            raise NotFoundException(f"文章不存在: {err}")
        
        # 获取文章内容
        if not article.get("content_id"):
            raise ValidationException("文章内容不存在，无法处理", PARAMETER_ERROR)
        
        err, content = self.content_repo.get_article_content(article["content_id"])
        if err:
            raise ValidationException(f"获取文章内容失败: {err}", PARAMETER_ERROR)
        
        return article, content
    
    def _get_user_language_preferences(self, user_id: str) -> Tuple[str, str]:
        """获取用户语言偏好
        
        Args:
            user_id: 用户ID
            
        Returns:
            (偏好语言, 摘要语言)
        """
        preferred_language = self.preferences_service.get_user_preference(
            user_id, "language", "preferred_language"
        ) or "zh-CN"
        
        summary_language = self.preferences_service.get_user_preference(
            user_id, "language", "summary_language"
        ) or preferred_language
        
        return preferred_language, summary_language
    
    def _get_default_summary_length(self, user_id: str) -> str:
        """获取用户默认摘要长度偏好
        
        Args:
            user_id: 用户ID
            
        Returns:
            摘要长度
        """
        return self.preferences_service.get_user_preference(
            user_id, "reading", "default_summary_length"
        ) or "medium"
    
    def _create_sse_data(self, event_type: str, data: Any) -> str:
        """创建SSE格式的数据
        
        Args:
            event_type: 事件类型
            data: 数据
            
        Returns:
            SSE格式的字符串
        """
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    def summarize_article_stream(self, user_id: str, article_id: int) -> Generator[str, None, None]:
        """流式生成文章概括
        
        Args:
            user_id: 用户ID
            article_id: 文章ID
            
        Yields:
            SSE格式的流式数据
        """
        try:
            # 发送开始事件
            yield self._create_sse_data("start", {
                "article_id": article_id,
                "status": "processing",
                "message": "开始生成文章概括..."
            })
            
            # 获取文章和内容
            article, content = self._get_article_and_content(article_id)
            
            # 获取用户偏好
            _, summary_language = self._get_user_language_preferences(user_id)
            summary_length = self._get_default_summary_length(user_id)
            target_lang_name = self.LANGUAGE_MAPPING.get(summary_language, "中文（简体）")
            
            # 发送配置信息
            yield self._create_sse_data("config", {
                "article_title": article.get("title"),
                "target_language": summary_language,
                "target_language_name": target_lang_name,
                "summary_length": summary_length
            })
            
            # 构建提示词
            length_mapping = {
                "short": "简短（100-150字）",
                "medium": "中等（200-300字）",
                "long": "详细（400-500字）"
            }
            length_desc = length_mapping.get(summary_length, "中等（200-300字）")
            
            text_content = content.get("text_content", "")
            if len(text_content) > 8000:
                text_content = text_content[:8000] + "..."
            
            prompt = f"""请为以下文章生成一个{length_desc}的概括，使用{target_lang_name}输出。

要求：
1. 准确概括文章的核心内容和主要观点
2. 保持客观中性的语调
3. 突出重要信息和关键结论
4. 字数控制在{length_desc}范围内
5. 输出语言：{target_lang_name}

文章标题：{article.get('title', '无标题')}

文章内容：
{text_content}

请直接输出概括内容，无需添加前缀或解释："""

            # 发送AI处理状态
            yield self._create_sse_data("ai_processing", {
                "message": "正在调用AI生成概括...",
                "prompt_length": len(prompt)
            })
            
            # 调用AI生成概括（流式）
            provider = LLMProviderFactory.create_provider()
            
            # 检查提供商是否支持流式输出
            if hasattr(provider, 'generate_chat_completion_stream'):
                # 使用流式API
                accumulated_content = ""
                usage_info = {}
                
                for chunk in provider.generate_chat_completion_stream(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=800,
                    temperature=0.3
                ):
                    if chunk.get("type") == "content":
                        content_delta = chunk.get("content", "")
                        accumulated_content += content_delta
                        
                        # 发送增量内容
                        yield self._create_sse_data("content", {
                            "delta": content_delta,
                            "accumulated": accumulated_content
                        })
                    elif chunk.get("type") == "usage":
                        usage_info = chunk.get("usage", {})
                
                summary = accumulated_content.strip()
            else:
                # 降级到非流式API
                response = provider.generate_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=800,
                    temperature=0.3
                )
                
                summary = response.get("message", {}).get("content", "").strip()
                usage_info = response.get("usage", {})
                
                # 模拟流式输出
                words = summary.split()
                accumulated = ""
                for i, word in enumerate(words):
                    accumulated += word + " "
                    yield self._create_sse_data("content", {
                        "delta": word + " ",
                        "accumulated": accumulated.strip()
                    })
                    
                    # 每10个词发送一次，模拟真实的流式体验
                    if i % 10 == 0:
                        import time
                        time.sleep(0.1)
            
            if not summary:
                raise ValidationException("AI生成概括失败", PARAMETER_ERROR)
            
            # 发送完成事件
            yield self._create_sse_data("complete", {
                "article_id": article_id,
                "article_title": article.get("title"),
                "summary": summary,
                "target_language": summary_language,
                "target_language_name": target_lang_name,
                "summary_length": summary_length,
                "generated_at": datetime.now().isoformat(),
                "usage": usage_info,
                "model": getattr(provider, 'default_model', 'unknown')
            })
            
            logger.info(f"成功生成文章概括流: 用户={user_id}, 文章={article_id}")
            
        except Exception as e:
            logger.error(f"生成文章概括流失败: 用户={user_id}, 文章={article_id}, 错误={str(e)}")
            yield self._create_sse_data("error", {
                "error": str(e),
                "article_id": article_id
            })
    
    def translate_article_stream(self, user_id: str, article_id: int) -> Generator[str, None, None]:
        """流式翻译文章
        
        Args:
            user_id: 用户ID
            article_id: 文章ID
            
        Yields:
            SSE格式的流式数据
        """
        try:
            # 发送开始事件
            yield self._create_sse_data("start", {
                "article_id": article_id,
                "status": "processing",
                "message": "开始翻译文章..."
            })
            
            # 获取文章和内容
            article, content = self._get_article_and_content(article_id)
            
            # 获取用户偏好语言
            preferred_language, _ = self._get_user_language_preferences(user_id)
            target_lang_name = self.LANGUAGE_MAPPING.get(preferred_language, "中文（简体）")
            
            # 发送配置信息
            yield self._create_sse_data("config", {
                "article_title": article.get("title"),
                "target_language": preferred_language,
                "target_language_name": target_lang_name
            })
            
            provider = LLMProviderFactory.create_provider()
            
            # 第一步：翻译标题和摘要
            yield self._create_sse_data("phase", {
                "phase": "title_summary",
                "message": "正在翻译标题和摘要..."
            })
            
            title = article.get("title", "")
            summary = article.get("summary", "")
            
            title_summary_prompt = f"""请将以下文章标题和摘要翻译成{target_lang_name}，保持原意和语调。

要求：
1. 准确翻译，保持原意
2. 语言自然流畅
3. 保持专业术语的准确性
4. 分别输出翻译后的标题和摘要

标题：{title}

摘要：{summary}

请按以下格式输出：
标题：[翻译后的标题]
摘要：[翻译后的摘要]"""

            # 翻译标题和摘要
            if hasattr(provider, 'generate_chat_completion_stream'):
                accumulated_content = ""
                for chunk in provider.generate_chat_completion_stream(
                    messages=[{"role": "user", "content": title_summary_prompt}],
                    max_tokens=1000,
                    temperature=0.2
                ):
                    if chunk.get("type") == "content":
                        content_delta = chunk.get("content", "")
                        accumulated_content += content_delta
                        
                        yield self._create_sse_data("title_summary_content", {
                            "delta": content_delta,
                            "accumulated": accumulated_content
                        })
                
                title_summary_result = accumulated_content.strip()
            else:
                response = provider.generate_chat_completion(
                    messages=[{"role": "user", "content": title_summary_prompt}],
                    max_tokens=1000,
                    temperature=0.2
                )
                title_summary_result = response.get("message", {}).get("content", "").strip()
            
            # 解析标题和摘要翻译结果
            translated_title = title
            translated_summary = summary
            
            lines = title_summary_result.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('标题：'):
                    translated_title = line.replace('标题：', '').strip()
                elif line.startswith('摘要：'):
                    translated_summary = line.replace('摘要：', '').strip()
            
            # 发送标题和摘要翻译结果
            yield self._create_sse_data("title_summary_complete", {
                "original_title": title,
                "translated_title": translated_title,
                "original_summary": summary,
                "translated_summary": translated_summary
            })
            
            # 第二步：翻译正文内容
            yield self._create_sse_data("phase", {
                "phase": "content",
                "message": "正在翻译正文内容..."
            })
            
            text_content = content.get("text_content", "")
            translated_content = ""
            
            if text_content:
                if len(text_content) > 6000:
                    # 分段翻译长文本
                    yield self._create_sse_data("content_info", {
                        "message": "文章较长，将分段翻译...",
                        "total_length": len(text_content)
                    })
                    
                    translated_content = yield from self._translate_long_content_stream(
                        text_content, target_lang_name, provider
                    )
                else:
                    translated_content = yield from self._translate_content_stream(
                        text_content, target_lang_name, provider
                    )
            
            # 发送完成事件
            yield self._create_sse_data("complete", {
                "article_id": article_id,
                "original_title": title,
                "translated_title": translated_title,
                "original_summary": summary,
                "translated_summary": translated_summary,
                "target_language": preferred_language,
                "target_language_name": target_lang_name,
                "translated_at": datetime.now().isoformat(),
                "content_translated": bool(text_content),
                "original_content": text_content,
                "translated_content": translated_content,
                "model": getattr(provider, 'default_model', 'unknown')
            })
            
            logger.info(f"成功翻译文章流: 用户={user_id}, 文章={article_id}")
            
        except Exception as e:
            logger.error(f"翻译文章流失败: 用户={user_id}, 文章={article_id}, 错误={str(e)}")
            yield self._create_sse_data("error", {
                "error": str(e),
                "article_id": article_id
            })
    
    def _translate_content_stream(self, content: str, target_lang_name: str, provider) -> Generator[str, None, None]:
        """流式翻译内容
        
        Args:
            content: 要翻译的内容
            target_lang_name: 目标语言名称
            provider: AI提供商实例
            
        Yields:
            翻译的内容流
            
        Returns:
            完整翻译内容
        """
        prompt = f"""请将以下文章内容翻译成{target_lang_name}。

要求：
1. 准确翻译，保持原意和语调
2. 保持段落结构
3. 专业术语翻译准确
4. 语言自然流畅

内容：
{content}

请直接输出翻译结果："""

        if hasattr(provider, 'generate_chat_completion_stream'):
            accumulated_content = ""
            for chunk in provider.generate_chat_completion_stream(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.2
            ):
                if chunk.get("type") == "content":
                    content_delta = chunk.get("content", "")
                    accumulated_content += content_delta
                    
                    yield self._create_sse_data("content_translation", {
                        "delta": content_delta,
                        "accumulated": accumulated_content
                    })
            
            return accumulated_content.strip()
        else:
            response = provider.generate_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.2
            )
            
            translated = response.get("message", {}).get("content", "").strip()
            
            # 模拟流式输出
            words = translated.split()
            accumulated = ""
            for word in words:
                accumulated += word + " "
                yield self._create_sse_data("content_translation", {
                    "delta": word + " ",
                    "accumulated": accumulated.strip()
                })
            
            return translated
    
    def _translate_long_content_stream(self, content: str, target_lang_name: str, provider) -> Generator[str, None, None]:
        """分段流式翻译长内容
        
        Args:
            content: 要翻译的长内容
            target_lang_name: 目标语言名称
            provider: AI提供商实例
            
        Yields:
            翻译的内容流
            
        Returns:
            完整翻译内容
        """
        # 按段落分割内容
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        translated_paragraphs = []
        
        # 将段落分组，每组不超过5000字符
        current_group = []
        current_length = 0
        groups = []
        
        for paragraph in paragraphs:
            if current_length + len(paragraph) > 5000 and current_group:
                groups.append('\n\n'.join(current_group))
                current_group = [paragraph]
                current_length = len(paragraph)
            else:
                current_group.append(paragraph)
                current_length += len(paragraph)
        
        if current_group:
            groups.append('\n\n'.join(current_group))
        
        # 逐组翻译
        for i, group_text in enumerate(groups):
            yield self._create_sse_data("content_group", {
                "group_index": i + 1,
                "total_groups": len(groups),
                "message": f"正在翻译第{i+1}段..."
            })
            
            translated_text = yield from self._translate_content_stream(group_text, target_lang_name, provider)
            translated_paragraphs.append(translated_text)
        
        return '\n\n'.join(translated_paragraphs)