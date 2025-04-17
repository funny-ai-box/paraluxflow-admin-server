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
        try:
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
        except Exception as e:
            logger.error(f"初始化Sumy组件失败 (语言: {language}): {e}")
            # Handle initialization failure gracefully if possible,
            # maybe by setting components to None and checking later,
            # or re-raising a specific exception.
            raise RuntimeError(f"无法初始化Sumy组件: {e}") from e


    def _clean_html(self, html_content: str) -> str:
        """清理HTML内容，提取正文文本

        Args:
            html_content: HTML内容

        Returns:
            清理后的文本
        """
        if not html_content: # Handle empty input
            return ""
        try:
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # 移除script和style标签
            for script in soup(["script", "style", "nav", "footer", "aside"]): # Added more common non-content tags
                script.extract()

            # 获取文本
            text = soup.get_text(separator='\n') # Use separator for better structure

            # 清理多余空白 more robustly
            lines = (line.strip() for line in text.splitlines())
            # Filter out empty lines after stripping
            text = '\n'.join(line for line in lines if line)

            return text
        except Exception as e:
            logger.error(f"清理HTML时出错: {e}")
            return "" # Return empty string on error

    def _normalize_text(self, text: str) -> str:
        """规范化文本，用于摘要生成

        Args:
            text: 原始文本

        Returns:
            规范化后的文本
        """
        # === Add check for None or empty input ===
        if not text:
            return ""

        text = text.strip()
        # Ensure text ends with appropriate punctuation for sentence splitting
        if text and not re.search(r'[.。!?！？]$', text):
            # Try to detect the most likely sentence ending punctuation used
            if '。' in text or '！' in text or '？' in text:
                text += '。'
            else:
                 text += '.' # Default to period if Chinese punctuation not found

        # 处理过长的段落 - Consider if this is always necessary, might break meaningful paragraphs
        # Sumy generally works better with distinct sentences. Splitting long paragraphs might be okay.
        paragraphs = text.split('\n')
        normalized_paragraphs = []
        max_paragraph_len = 1500 # Increased length slightly

        for paragraph in paragraphs:
            paragraph = paragraph.strip() # Strip individual paragraphs
            if not paragraph:
                continue

            if len(paragraph) > max_paragraph_len:  # 如果段落太长
                # Try splitting into sentences more reliably
                sentences = re.split(r'(?<=[.。!?！？])\s*', paragraph) # Split and capture delimiter, handle spaces
                current_chunk = ""

                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    # Re-chunk sentences if needed (though less common if split correctly)
                    if len(current_chunk) == 0:
                        current_chunk = sentence
                    elif len(current_chunk) + len(sentence) + 1 < max_paragraph_len: # +1 for potential space
                         current_chunk += " " + sentence # Re-add space if joining sentences
                    else:
                        normalized_paragraphs.append(current_chunk)
                        current_chunk = sentence

                if current_chunk: # Add the last chunk
                    normalized_paragraphs.append(current_chunk)

            else:
                normalized_paragraphs.append(paragraph)

        # Join paragraphs back with newline, ensuring no double newlines if input had them
        return '\n'.join(p for p in normalized_paragraphs if p)


    def generate_summary_from_text(self, text: str, sentences_count: int = 3) -> str:
        """从纯文本生成摘要

        Args:
            text: 文本内容
            sentences_count: 摘要句子数量

        Returns:
            生成的摘要
        """
        # === Add check for None or empty input early ===
        if not text:
            logger.warning("generate_summary_from_text 收到空文本输入。")
            return ""

        try:
            # 规范化文本
            normalized_text = self._normalize_text(text)
            if not normalized_text: # If normalization resulted in empty text
                 logger.warning("文本规范化后为空。")
                 return ""

            # 使用PlaintextParser解析
            parser = PlaintextParser.from_string(normalized_text, self.tokenizer)

            # --- Generate summaries ---
            # It's often better to try one reliable method first, then fall back.
            # LexRank is generally considered robust. LSA can sometimes produce less coherent results.
            summary_sentences = []
            try:
                 # Try LexRank first
                 summary_sentences = self.lex_rank_summarizer(parser.document, sentences_count)
            except Exception as e:
                 logger.warning(f"LexRank摘要生成失败: {e}")

            if not summary_sentences:
                try:
                    # Fallback to LSA
                    logger.info("LexRank失败或返回空，尝试LSA。")
                    summary_sentences = self.lsa_summarizer(parser.document, sentences_count)
                except Exception as e:
                    logger.warning(f"LSA摘要生成失败: {e}")

            if not summary_sentences:
                 try:
                    # Fallback to Luhn
                    logger.info("LSA失败或返回空，尝试Luhn。")
                    summary_sentences = self.luhn_summarizer(parser.document, sentences_count)
                 except Exception as e:
                    logger.warning(f"Luhn摘要生成失败: {e}")


            # 合并摘要句子
            # Ensure sentences are strings and join appropriately for the language
            if self.language == "chinese":
                 summary_text = "".join(str(sentence) for sentence in summary_sentences).strip()
            else:
                 summary_text = " ".join(str(sentence) for sentence in summary_sentences).strip()


            # Fallback: If summary is still too short or empty, use initial sentences
            # Make the length check more robust (e.g., character count AND sentence count)
            min_summary_chars = 50 # Adjust as needed
            if not summary_text or len(summary_text) < min_summary_chars:
                logger.info(f"生成的摘要太短 ('{summary_text}'), 使用原文前 {sentences_count} 句作为后备。")
                # Split sentences more carefully
                sentences = re.split(r'(?<=[.。!?！？])\s*', normalized_text)
                # Filter potentially empty strings from split and very short "sentences"
                min_sentence_len = 5 # Minimum characters for a sentence to be considered valid
                meaningful_sentences = [s.strip() for s in sentences if s and len(s.strip()) >= min_sentence_len]

                if meaningful_sentences:
                    fallback_summary = meaningful_sentences[:sentences_count]
                    if self.language == "chinese":
                         summary_text = "".join(fallback_summary)
                    else:
                         summary_text = " ".join(fallback_summary)
                else:
                    # Ultimate fallback: truncate original text if no sentences found
                    logger.warning("无法从原文提取句子作为后备，将截断原文。")
                    summary_text = text[:200] + "..." if len(text) > 200 else text


            return summary_text.strip()

        except Exception as e:
            # Log the full traceback for debugging
            logger.error(f"从文本生成摘要时发生意外错误", exc_info=True)
            # Fallback to truncated original text in case of any unexpected error
            return text[:200] + "..." if len(text) > 200 else text

    def check_summary_quality(self, summary: str, min_length: int = 100, min_sentences: int = 2) -> bool:
        """检查摘要质量 (更严格的检查)

        Args:
            summary: 摘要内容
            min_length: 最小字符长度
            min_sentences: 最小句子数量

        Returns:
            摘要是否满足质量要求
        """
        if not summary:
            return False

        summary = summary.strip()

        # 检查长度
        if len(summary) < min_length:
             logger.debug(f"摘要质量检查失败：长度 {len(summary)} < {min_length}")
             return False

        # 检查是否包含足够的句子 (更可靠的句子分割)
        sentences = re.split(r'(?<=[.。!?！？])\s*', summary)
        # Filter empty strings and very short "sentences" resulting from split
        valid_sentences = [s for s in sentences if s and len(s.strip()) > 5] # Min 5 chars for a valid sentence fragment
        if len(valid_sentences) < min_sentences:
             logger.debug(f"摘要质量检查失败：句子数 {len(valid_sentences)} < {min_sentences}")
             return False

        # Optional: Add more checks (e.g., repetition, presence of keywords from original?)

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
        RuntimeError: 如果Sumy组件初始化失败
    """
    if not text and not html:
        raise ValueError("参数'text'和'html'必须至少提供一个")
    if text and html:
        logger.warning("提供了'text'和'html'参数，将优先使用'text'。")
        # Or raise ValueError("不能同时提供 'text' 和 'html' 参数") depending on desired behavior

    try:
        generator = SummaryGenerator(language)
    except RuntimeError as e:
         logger.error(f"无法创建SummaryGenerator: {e}")
         return "" # Or re-raise the exception

    input_text = text # Default to using text if provided

    # If text is not provided (or is empty) and html is provided, process html
    if not input_text and html:
        logger.debug("正在从HTML内容生成摘要...")
        input_text = generator._clean_html(html)
        if not input_text:
             logger.error("从HTML提取文本失败，无法生成摘要。")
             return "" # Return empty if HTML cleaning failed
    elif not input_text:
         # This case should ideally be caught by the initial check, but good for safety
         logger.error("没有提供有效的文本或HTML内容。")
         return ""

    # Now, generate the summary from the determined input_text
    logger.debug("正在从文本生成摘要...")
    summary = generator.generate_summary_from_text(input_text, sentences_count)

    # Optional: Check quality before returning
    # if not generator.check_summary_quality(summary):
    #     logger.warning(f"生成的摘要可能质量不高: '{summary}'")
        # Decide what to do: return low-quality summary, return empty, or try fallback?

    return summary

# Example Usage (for testing)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Test with Text
    sample_text = """
    人工智能（AI）是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。该领域的研究包括机器人、语言识别、图像识别、自然语言处理和专家系统等。人工智能从诞生以来，理论和技术日益成熟，应用领域也不断扩大，可以设想，未来人工智能带来的科技产品，将会是人类智慧的“容器”。人工智能可以对人的意识、思维的信息过程的模拟。人工智能不是人的智能，但能像人那样思考、也可能超过人的智能。
    人工智能的应用极其广泛。例如，医疗诊断、金融交易、机器人控制、法律服务、科学发现以及玩具等多个领域。目前，许多AI应用都集中在所谓的“弱AI”（Narrow AI）上，即专注于执行特定任务的系统。然而，研究人员也在探索“强AI”（General AI）的可能性，即拥有与人类相当的认知能力的机器。
    未来的发展充满了机遇与挑战。数据隐私、算法偏见、就业影响以及AI的伦理问题都是需要认真考虑和解决的关键议题。我们需要确保AI的发展是为了全人类的福祉。技术的进步不应以牺牲人类价值为代价。
    """
    print("--- 摘要来自文本 ---")
    summary_from_text = generate_summary(text=sample_text, sentences_count=2, language="chinese")
    print(summary_from_text)
    print("-" * 20)

    # Test with HTML
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head><title>测试页面</title></head>
    <body>
        <header><nav>导航栏</nav></header>
        <h1>欢迎来到AI的世界</h1>
        <p>人工智能（AI）是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。<strong>非常重要</strong>！</p>
        <script>console.log('脚本内容');</script>
        <style>p { color: blue; }</style>
        <p>该领域的研究包括机器人、语言识别、图像识别、自然语言处理和专家系统等。AI的应用无处不在。</p>
        <p>未来的发展充满了机遇与挑战。我们需要确保AI的发展是为了全人类的福祉。</p>
        <footer>版权所有</footer>
    </body>
    </html>
    """
    print("--- 摘要来自HTML ---")
    summary_from_html = generate_summary(html=sample_html, sentences_count=1, language="chinese")
    print(summary_from_html)
    print("-" * 20)

    # Test with None/Empty
    print("--- 测试空输入 ---")
    try:
        generate_summary()
    except ValueError as e:
        print(f"捕获到预期的错误: {e}")

    print("--- 测试仅HTML但HTML清理失败(模拟) ---")
    # Simulate cleaning failure by overriding _clean_html temporarily if needed for test,
    # or by passing intentionally malformed HTML if BeautifulSoup handles it poorly.
    # For now, we'll rely on the logging if cleaning returns empty.
    summary_bad_html = generate_summary(html="<malformed>", sentences_count=1)
    print(f"处理无效HTML的摘要: '{summary_bad_html}'") # Should likely be empty

    print("--- 测试长段落规范化 ---")
    long_paragraph_text = "这是第一句。" + "这是第二句。" * 500 + "这是最后一句。"
    generator_test = SummaryGenerator()
    normalized_lp = generator_test._normalize_text(long_paragraph_text)
    # print(f"规范化后的长段落:\n{normalized_lp}") # Verify it splits correctly
    summary_lp = generate_summary(text=long_paragraph_text, sentences_count=2)
    print(f"长段落摘要: {summary_lp}")