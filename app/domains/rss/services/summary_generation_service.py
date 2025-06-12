# app/domains/rss/services/summary_generation_service.py
"""摘要生成服务实现"""
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from app.infrastructure.llm_providers.factory import LLMProviderFactory

logger = logging.getLogger(__name__)

class SummaryGenerationService:
    """摘要生成服务"""
    
    def __init__(self, article_repo, content_repo):
        """初始化摘要生成服务
        
        Args:
            article_repo: 文章仓库
            content_repo: 内容仓库
        """
        self.article_repo = article_repo
        self.content_repo = content_repo
        self.max_summary_length = 200
        
    def is_invalid_summary(self, summary):
        """检查摘要是否无效"""
        if not summary or not isinstance(summary, str):
            return True
        
        summary = summary.strip()
        
        # 检查长度
        if len(summary) < 10:
            return True
        
        # 检查是否包含无效模式
        invalid_patterns = [
            r'点击.*?查看',
            r'查看.*?原文',
            r'阅读.*?原文', 
            r'继续.*?阅读',
            r'更多.*?内容',
            r'详细.*?内容',
            r'完整.*?文章',
            r'read\s+more',
            r'view\s+more',
            r'click\s+here',
            r'see\s+more',
            r'分享到',
            r'转发',
            r'关注',
            r'订阅',
            r'来源[:：]',
            r'作者[:：]',
            r'时间[:：]',
            r'^[^a-zA-Z\u4e00-\u9fff]*>+[^a-zA-Z\u4e00-\u9fff]*$',
            r'^[^a-zA-Z\u4e00-\u9fff]*$'
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, summary, re.IGNORECASE):
                return True
        
        return False
    
    def clean_text(self, text):
        """清理文本"""
        if not text:
            return ""
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除多余的空白
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊字符但保留基本标点
        text = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:，。！？；：\-]', '', text)
        
        return text.strip()
    
    def truncate_summary(self, summary, max_length=None):
        """截断摘要到指定长度"""
        if not summary:
            return summary
        
        max_len = max_length or self.max_summary_length
        
        if len(summary) <= max_len:
            return summary
        
        # 截断到最大长度，并在词边界处结束
        truncated = summary[:max_len-3]
        
        # 尝试在句号、感叹号或问号处结束
        for char in ['。', '！', '？', '.', '!', '?']:
            pos = truncated.rfind(char)
            if pos > max_len * 0.7:  # 至少保留70%的长度
                return truncated[:pos+1]
        
        # 尝试在逗号或分号处结束
        for char in ['，', '；', ',', ';']:
            pos = truncated.rfind(char)
            if pos > max_len * 0.8:  # 至少保留80%的长度
                return truncated[:pos+1]
        
        # 如果都没找到合适的位置，就直接截断并加省略号
        return truncated + "..."
    
    def generate_bilingual_summary_with_llm(self, text, provider_name=None):
        """使用LLM一次性生成中英文双语摘要"""
        try:
            # 创建LLM提供商
            llm_provider = LLMProviderFactory.create_provider(provider_name)
            
            # 清理文本
            clean_text = self.clean_text(text)
            if len(clean_text) < 50:
                return None, None
            
            # 构建双语摘要提示词
            prompt = f"""请为以下文章生成中英文双语摘要，要求：

中文摘要要求：
1. 长度控制在200字以内
2. 突出文章的主要内容和核心观点
3. 语言简洁明了，避免重复
4. 不要包含"点击查看"、"阅读原文"等无关内容

英文摘要要求：
1. Keep it within 200 characters
2. Highlight the main content and key points
3. Use clear and concise language, avoid repetition
4. Do not include irrelevant content like "click to view", "read more", etc.

请按照以下格式输出，不要添加任何其他内容：

中文摘要：[这里是中文摘要内容]

English Summary：[这里是英文摘要内容]

文章内容：
{clean_text[:2000]}"""
            
            # 生成摘要
            response = llm_provider.generate_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,  # 增加token数量以容纳双语摘要
                temperature=0.3
            )
            
            summary_text = response.get("message", {}).get("content", "").strip()
            
            if not summary_text:
                return None, None
            
            # 解析双语摘要
            chinese_summary, english_summary = self._parse_bilingual_summary(summary_text)
            
            # 验证并截断摘要
            if chinese_summary and not self.is_invalid_summary(chinese_summary):
                chinese_summary = self.truncate_summary(chinese_summary)
            else:
                chinese_summary = None
                
            if english_summary and not self.is_invalid_summary(english_summary):
                english_summary = self.truncate_summary(english_summary)
            else:
                english_summary = None
            
            return chinese_summary, english_summary
            
        except Exception as e:
            logger.error(f"LLM生成双语摘要失败: {str(e)}")
            return None, None

    def _parse_bilingual_summary(self, summary_text):
        """解析双语摘要文本"""
        try:
            chinese_summary = None
            english_summary = None
            
            # 使用正则表达式提取中文摘要
            chinese_match = re.search(r'中文摘要[:：]\s*(.+?)(?=\n\s*English Summary|$)', summary_text, re.DOTALL | re.IGNORECASE)
            if chinese_match:
                chinese_summary = chinese_match.group(1).strip()
            
            # 使用正则表达式提取英文摘要
            english_match = re.search(r'English Summary[:：]\s*(.+?)(?=\n\s*中文摘要|$)', summary_text, re.DOTALL | re.IGNORECASE)
            if english_match:
                english_summary = english_match.group(1).strip()
            
            # 如果正则匹配失败，尝试按行分割
            if not chinese_summary or not english_summary:
                lines = summary_text.split('\n')
                current_type = None
                chinese_lines = []
                english_lines = []
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if '中文摘要' in line or '中文：' in line:
                        current_type = 'chinese'
                        # 检查是否同一行就有内容
                        content = re.sub(r'^[^：:]*[:：]\s*', '', line)
                        if content:
                            chinese_lines.append(content)
                    elif 'English Summary' in line or 'English:' in line:
                        current_type = 'english'
                        # 检查是否同一行就有内容
                        content = re.sub(r'^[^：:]*[:：]\s*', '', line)
                        if content:
                            english_lines.append(content)
                    elif current_type == 'chinese':
                        chinese_lines.append(line)
                    elif current_type == 'english':
                        english_lines.append(line)
                
                if chinese_lines and not chinese_summary:
                    chinese_summary = ' '.join(chinese_lines).strip()
                if english_lines and not english_summary:
                    english_summary = ' '.join(english_lines).strip()
            
            # 清理摘要内容
            if chinese_summary:
                chinese_summary = re.sub(r'^[^\u4e00-\u9fff]*', '', chinese_summary)  # 移除开头的非中文字符
                chinese_summary = chinese_summary.strip()
                
            if english_summary:
                english_summary = re.sub(r'^[^a-zA-Z]*', '', english_summary)  # 移除开头的非英文字符
                english_summary = english_summary.strip()
            
            return chinese_summary, english_summary
            
        except Exception as e:
            logger.error(f"解析双语摘要失败: {str(e)}")
            return None, None

    def generate_article_summaries(self, article_id: int, provider_name: Optional[str] = None) -> Tuple[Optional[str], Dict[str, Any]]:
        """为指定文章生成摘要
        
        Args:
            article_id: 文章ID
            provider_name: LLM提供商名称(可选)
            
        Returns:
            (错误信息, 结果数据)
        """
        try:
            logger.info(f"开始为文章 {article_id} 生成双语摘要...")
            
            # 获取文章信息
            err, article = self.article_repo.get_article_by_id(article_id)
            if err:
                return f"获取文章失败: {err}", {}
            
            if not article:
                return f"文章 {article_id} 不存在", {}
            
            # 获取文章内容
            content_id = article.get("content_id")
            if not content_id:
                return f"文章 {article_id} 没有内容", {}
            
            err, content = self.content_repo.get_article_content(content_id)
            if err or not content:
                return f"获取文章内容失败: {err}", {}
            
            # 获取文本内容用于生成摘要
            text_content = content.get("text_content", "")
            if not text_content:
                return "文章文本内容为空", {}
            
            logger.info(f"文章文本长度: {len(text_content)} 字符")
            
            # 一次性生成中英文双语摘要
            chinese_summary, english_summary = self.generate_bilingual_summary_with_llm(
                text_content, provider_name=provider_name
            )
            
            if not chinese_summary and not english_summary:
                return "生成摘要失败", {}
            
            # 检查原始摘要是否需要更新
            original_summary = article.get("summary", "")
            original_summary_updated = False
            updated_original_summary = original_summary
            
            if self.is_invalid_summary(original_summary):
                logger.info(f"原始摘要无效，将被清空: '{original_summary}'")
                updated_original_summary = None
                original_summary_updated = True
            else:
                logger.info(f"原始摘要有效，保持不变: '{original_summary[:50]}...'")
            
            # 更新文章的摘要信息
            update_data = {}
            
            if chinese_summary:
                update_data["chinese_summary"] = chinese_summary
                logger.info(f"生成中文摘要: {chinese_summary}")
            
            if english_summary:
                update_data["english_summary"] = english_summary
                logger.info(f"生成英文摘要: {english_summary}")
            
            if original_summary_updated:
                update_data["summary"] = updated_original_summary
            
            # 更新数据库
            if update_data:
                err, updated_article = self.article_repo.update_article_summaries(article_id, update_data)
                if err:
                    return f"更新摘要失败: {err}", {}
                
                logger.info(f"成功更新文章 {article_id} 的摘要信息")
            
            result = {
                "article_id": article_id,
                "chinese_summary": chinese_summary,
                "english_summary": english_summary,
                "original_summary_updated": original_summary_updated,
                "updated_original_summary": updated_original_summary,
                "provider_used": provider_name or "default"
            }
            
            return None, result
            
        except Exception as e:
            logger.error(f"生成摘要失败: {str(e)}")
            return f"生成摘要失败: {str(e)}", {}

    def update_article_processing_step(self, article_id: int, step: str, status: str = "success", 
                                     data: Optional[Dict[str, Any]] = None, 
                                     error_message: Optional[str] = None) -> Tuple[Optional[str], Dict[str, Any]]:
        """更新文章处理步骤状态
        
        Args:
            article_id: 文章ID
            step: 处理步骤 (content_saved, summary_generated, vectorized)
            status: 状态 (success, failed)
            data: 相关数据
            error_message: 错误信息(如果失败)
            
        Returns:
            (错误信息, 结果数据)
        """
        try:
            logger.info(f"更新文章 {article_id} 的处理步骤: {step} - {status}")
            
            # 获取文章
            err, article = self.article_repo.get_article_by_id(article_id)
            if err:
                return f"获取文章失败: {err}", {}
            
            if not article:
                return f"文章 {article_id} 不存在", {}
            
            # 准备更新数据
            update_data = {}
            
            # 根据步骤更新相应字段
            if step == "content_saved" and status == "success":
                # 内容保存成功
                update_data.update({
                    "status": 1,  # 标记为已抓取
                    "content_id": data.get("content_id") if data else None,
                    "is_locked": False,
                    "error_message": None
                })
                
            elif step == "summary_generated" and status == "success":
                # 摘要生成成功
                if data:
                    if "chinese_summary" in data:
                        update_data["chinese_summary"] = data["chinese_summary"]
                    if "english_summary" in data:
                        update_data["english_summary"] = data["english_summary"]
                    if data.get("original_summary_updated"):
                        update_data["summary"] = data.get("updated_original_summary")
                        
            elif step == "vectorized" and status == "success":
                # 向量化成功
                update_data.update({
                    "is_vectorized": True,
                    "vectorization_status": 1,
                    "vector_id": data.get("vector_id") if data else None,
                    "vectorized_at": datetime.now(),
                    "vectorization_error": None
                })
                
            elif status == "failed":
                # 任何步骤失败
                update_data["error_message"] = error_message
                update_data["is_locked"] = False
                
                if step in ["content_saved", "summary_generated"]:
                    update_data["status"] = 2  # 标记为失败
                elif step == "vectorized":
                    update_data.update({
                        "vectorization_status": 2,
                        "vectorization_error": error_message
                    })
            
            # 更新文章
            if update_data:
                err, updated_article = self.article_repo.update_article_fields(article_id, update_data)
                if err:
                    return f"更新文章失败: {err}", {}
                
                logger.info(f"成功更新文章 {article_id} 的步骤状态: {step}")
            
            return None, {
                "article_id": article_id,
                "step": step,
                "status": status
            }
            
        except Exception as e:
            logger.error(f"更新文章步骤失败: {str(e)}")
            return f"更新失败: {str(e)}", {}