# app/utils/summary_generator.py
"""文章摘要生成工具"""
import logging
from typing import Optional
import re
from bs4 import BeautifulSoup

# 导入sumy库
from sumy.parsers.html import HtmlParser
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.summarizers.luhn import LuhnSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

logger = logging.getLogger(__name__)

class SummaryGenerator:
    """使用sumy库生成文章摘要"""
    
    def __init__(self, language: str = "chinese"):
        """初始化摘要生成器
        
        Args:
            language: 文章语言，默认为中文
        """
        self.language = language
        self.stemmer = Stemmer(language)
        self.tokenizer = Tokenizer(language)
        self.stop_words = get_stop_words(language)
        
        # 初始化不同的摘要算法
        self.lsa_summarizer = LsaSummarizer(self.stemmer)
        self.lsa_summarizer.stop_words = self.stop_words
        
        self.lex_rank_summarizer = LexRankSummarizer(self.stemmer)
        self.lex_rank_summarizer.stop_words = self.stop_words
        
        self.luhn_summarizer = LuhnSummarizer(self.stemmer)
        self.luhn_summarizer.stop_words = self.stop_words
    
    def _clean_html(self, html_content: str) -> str:
        """清理HTML内容，提取正文文本
        
        Args:
            html_content: HTML内容
            
        Returns:
            清理后的文本
        """
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 移除script和style标签
        for script in soup(["script", "style"]):
            script.extract()
        
        # 获取文本
        text = soup.get_text()
        
        # 清理多余空白
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def _normalize_text(self, text: str) -> str:
        """规范化文本，用于摘要生成
        
        Args:
            text: 原始文本
            
        Returns:
            规范化后的文本
        """
        # 确保文本有句号结尾
        text = text.strip()
        if text and not text.endswith(('.', '。', '!', '?', '！', '？')):
            text += '。'
        
        # 处理过长的段落
        paragraphs = text.split('\n')
        normalized_paragraphs = []
        
        for paragraph in paragraphs:
            if len(paragraph) > 1000:  # 如果段落太长
                # 尝试按句子分割
                sentences = re.split(r'(?<=[.。!?！？])', paragraph)
                chunks = []
                current_chunk = ""
                
                for sentence in sentences:
                    if not sentence.strip():
                        continue
                    
                    if len(current_chunk) + len(sentence) < 1000:
                        current_chunk += sentence
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = sentence
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                normalized_paragraphs.extend(chunks)
            else:
                normalized_paragraphs.append(paragraph)
        
        return '\n'.join(normalized_paragraphs)
    
    def generate_summary_from_html(self, html_content: str, sentences_count: int = 3) -> str:
        """从HTML内容生成摘要
        
        Args:
            html_content: HTML内容
            sentences_count: 摘要句子数量
            
        Returns:
            生成的摘要
        """
        try:
            # 清理HTML
            text = self._clean_html(html_content)
            
            # 使用HtmlParser解析
            parser = HtmlParser.from_string(html_content, self.tokenizer, self.language)
            
            # 使用LsaSummarizer生成摘要
            summary = self.lsa_summarizer(parser.document, sentences_count)
            
            # 合并摘要句子
            summary_text = " ".join(str(sentence) for sentence in summary)
            
            return summary_text
        except Exception as e:
            logger.error(f"从HTML生成摘要失败: {str(e)}")
            # 如果出错，尝试使用备用方法
            return self.generate_summary_from_text(text, sentences_count)
    
    def generate_summary_from_text(self, text: str, sentences_count: int = 3) -> str:
        """从纯文本生成摘要
        
        Args:
            text: 文本内容
            sentences_count: 摘要句子数量
            
        Returns:
            生成的摘要
        """
        try:
            # 规范化文本
            normalized_text = self._normalize_text(text)
            
            # 使用PlaintextParser解析
            parser = PlaintextParser.from_string(normalized_text, self.tokenizer)
            
            # 使用不同算法生成摘要
            lsa_summary = self.lsa_summarizer(parser.document, sentences_count)
            lex_rank_summary = self.lex_rank_summarizer(parser.document, sentences_count)
            luhn_summary = self.luhn_summarizer(parser.document, sentences_count)
            
            # 选择最佳摘要（这里简单地选择LSA摘要）
            summary = lsa_summary
            
            # 如果LSA摘要为空，尝试使用其他摘要
            if not summary:
                if lex_rank_summary:
                    summary = lex_rank_summary
                elif luhn_summary:
                    summary = luhn_summary
            
            # 合并摘要句子
            summary_text = " ".join(str(sentence) for sentence in summary)
            
            # 如果摘要太短，尝试从文本中提取前几个句子
            if len(summary_text) < 100:
                sentences = re.split(r'(?<=[.。!?！？])', normalized_text)
                filtered_sentences = [s for s in sentences if len(s.strip()) > 10]
                if filtered_sentences:
                    summary_text = " ".join(filtered_sentences[:sentences_count])
            
            return summary_text
        except Exception as e:
            logger.error(f"从文本生成摘要失败: {str(e)}")
            # 如果失败，返回文本的前200个字符作为摘要
            return text[:200] + "..." if len(text) > 200 else text
    
    def check_summary_quality(self, summary: str, min_length: int = 100) -> bool:
        """检查摘要质量
        
        Args:
            summary: 摘要内容
            min_length: 最小长度
            
        Returns:
            摘要是否满足质量要求
        """
        if not summary:
            return False
        
        # 检查长度
        if len(summary) < min_length:
            return False
        
        # 检查是否包含足够的句子
        sentences = re.split(r'(?<=[.。!?！？])', summary)
        valid_sentences = [s for s in sentences if len(s.strip()) > 10]
        if len(valid_sentences) < 2:
            return False
        
        return True

# 暴露简便的函数接口
def generate_summary(text: str = None, html: str = None, sentences_count: int = 3, language: str = "chinese") -> str:
    """生成文章摘要
    
    Args:
        text: 文本内容（与html二选一）
        html: HTML内容（与text二选一）
        sentences_count: 摘要句子数量
        language: 文章语言
            
    Returns:
        生成的摘要
            
    Raises:
        ValueError: 参数错误时抛出异常
    """
    if not text and not html:
        raise ValueError("text和html参数必须提供一个")
    
    generator = SummaryGenerator(language)
    
    if html:
        return generator.generate_summary_from_html(html, sentences_count)
    else:
        return generator.generate_summary_from_text(text, sentences_count)