# app/domains/hot_topics/services/hot_topic_aggregation_service.py
import logging
import json
import time
import hashlib
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session

from app.infrastructure.database.repositories.hot_topic_repository import HotTopicRepository, UnifiedHotTopicRepository
from app.infrastructure.llm_providers.factory import LLMProviderFactory
from app.infrastructure.llm_providers.base import LLMProviderInterface
from app.core.exceptions import APIException
from app.core.status_codes import EXTERNAL_API_ERROR, PROVIDER_NOT_FOUND

logger = logging.getLogger(__name__)

class HotTopicAggregationService:
    """
    负责使用AI聚合不同平台的热点话题服务，优化token使用和输出格式
    """
    def __init__(
        self,
        db_session: Session,
        hot_topic_repo: HotTopicRepository,
        unified_topic_repo: UnifiedHotTopicRepository,
        llm_provider: Optional[LLMProviderInterface] = None,
        vectorization_service: Optional[Any] = None
    ):
        self.db_session = db_session
        self.hot_topic_repo = hot_topic_repo
        self.unified_topic_repo = unified_topic_repo
        self.llm_provider = llm_provider
        self.vectorization_service = vectorization_service

    def _generate_stable_hash(self, title: str, platform: str) -> str:
        """生成基于标题和平台的稳定哈希值（与HotTopicService保持一致）
        
        Args:
            title: 话题标题
            platform: 平台名称
            
        Returns:
            64位哈希字符串
        """
        # 标准化标题（去除特殊字符、转小写）
        normalized_title = ''.join(c for c in title.lower() if c.isalnum() or c.isspace()).strip()
        # 创建唯一标识
        unique_string = f"{platform}:{normalized_title}"
        # 生成SHA256哈希
        return hashlib.sha256(unique_string.encode('utf-8')).hexdigest()

    def _init_llm_provider(self, provider_type: Optional[str] = None, model_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        初始化LLM提供商，优先使用火山引擎
        
        Args:
            provider_type: (可选) 指定要使用的提供商类型。如果为None，优先使用火山引擎
            model_id: (可选) 指定要使用的模型ID
            
        Returns:
            成功标志和错误消息元组
        """
        if self.llm_provider:
            logger.debug("LLM provider already initialized.")
            return True, ""

        # 如果没有指定provider_type，优先使用火山引擎
        if not provider_type:
            provider_type = "volcengine"
            logger.info("未指定provider_type，优先使用火山引擎")

        logger.info(f"正在初始化LLM提供商: {provider_type}, 模型: {model_id or 'Default'}")

        try:
            self.llm_provider = LLMProviderFactory.create_provider(
                provider_name=provider_type,
                model_id=model_id
            )

            initialized_provider_type = self.llm_provider.get_provider_name() if self.llm_provider else "Unknown"
            initialized_model_id = getattr(self.llm_provider, "default_model", "Unknown")

            logger.info(f"成功初始化LLM提供商: Type={initialized_provider_type}, Model={initialized_model_id}")
            return True, ""

        except APIException as e:
            logger.error(f"初始化LLM提供商失败: {e.message} (Code: {e.code})")
            return False, e.message
        except Exception as e:
            logger.error(f"初始化LLM提供商时发生意外错误: {str(e)}", exc_info=True)
            return False, f"实例化LLM提供商时发生意外错误: {str(e)}"

    def _prepare_prompt(self, topics: List[Dict[str, Any]], target_date: date) -> str:
        """准备用于AI聚合的Prompt，使用ID代替哈希以减少token消耗"""

        # 选取关键信息，使用ID代替哈希
        simplified_topics = [
            {
                "id": topic["id"],  # 使用数字ID代替哈希
                "platform": topic["platform"],
                "title": topic["topic_title"],
                "description": topic.get("topic_description", "")[:50]  # 进一步减少描述长度
            }
            for topic in topics if topic.get("topic_title")
        ]

        topics_json_str = json.dumps(simplified_topics, ensure_ascii=False, indent=2)

        # 分类列表
        categories = [
            "政治", "经济", "科技", "军事", "社会", "文化", "体育", 
            "健康", "教育", "环境", "国际", "灾难", "法律", "旅游", "生活", "其他"
        ]
        categories_str = "、".join(categories)

        prompt = f"""
        任务：请分析以下来自不同平台在 {target_date.isoformat()} 的热点列表，将描述**同一核心事件或话题**的热点归为一组，生成约10个聚合组。

        标题要求（非常重要）：
        1. 标题不超过30个字，必须简洁精准
        2. 必须包含具体的数据、地点、人物、机构等关键信息
        3. 采用"主体+动作+关键数据"的紧凑格式
        4. 避免使用"相关"、"热点"、"事件"等模糊词汇

        优秀标题示例（30字内）：
        - "人社部等十部门：放开城镇落户限制"
        - "广州12月1日起取消普通住宅标准"
        - "陕西神木化学事故致死26人"
        - "A股大跳水：沪指失守3300点"
        - "中国异种器官移植获新突破"

        分类要求：
        请为每个聚合组选择最适合的分类，可选分类：{categories_str}

        聚合要求：
        1. 识别相似的热点并将它们分组，每组至少包含2个不同平台的热点
        2. 生成约10个高质量的聚合组
        3. 统一标题不超过30个字，必须包含核心信息
        4. 统一摘要60字以内，补充标题中的关键细节
        5. 关键词1-2个，使用核心短语（如"政策调整"、"股市波动"）
        6. 包含所有被归入该组的原始热点ID列表
        7. 包含所有涉及的平台名称列表
        8. 为每个组选择最合适的分类

        原始热点数据 (JSON格式):
        ```json
        {topics_json_str}
        ```

        输出格式要求：
        请严格按照以下JSON格式返回结果，返回一个包含约10个组对象的列表。

        ```json
        [
        {{
            "unified_title": "机构+行动+数据（30字内）",
            "unified_summary": "事件背景和影响（60字内）",
            "keywords": ["核心短语1", "核心短语2"],
            "category": "政治",
            "related_topic_ids": [1, 2, 3],
            "source_platforms": ["平台A", "平台B"]
        }}
        ]
        ```
        
        注意：
        - 标题30字内，必须精炼准确
        - 必须包含具体主体和关键数据
        - category必须从可选分类中选择
        - related_topic_ids必须来自上方原始数据
        - 关键词要精炼，1-2个核心短语
        - 目标生成10个左右高质量聚合组
        """
        return prompt.strip()

    def trigger_aggregation(self, topic_date_str: str, model_id: Optional[str] = None, provider_type: Optional[str] = None) -> Dict[str, Any]:
        """
        触发热点聚合任务，优先使用火山引擎

        Args:
            topic_date_str: 需要聚合的热点日期字符串(YYYY-MM-DD)
            model_id: 可选的模型ID
            provider_type: 可选的提供商类型，默认使用火山引擎

        Returns:
            聚合任务的结果
        """
        # 1. 验证日期格式
        try:
            topic_date = datetime.strptime(topic_date_str, "%Y-%m-%d").date()
        except ValueError:
            return {
                "status": "error",
                "message": "无效的日期格式，应为YYYY-MM-DD"
            }

        # 2. 初始化LLM提供商（如果没有指定，优先使用火山引擎）
        if not self.llm_provider:
            success, error_message = self._init_llm_provider(provider_type or "volcengine", model_id)
            if not success:
                return {
                    "status": "llm_error",
                    "message": error_message
                }

        # 3. 调用聚合方法
        return self.aggregate_topics_for_date(topic_date, model_id=model_id)

    def aggregate_topics_for_date(self, topic_date: date, model_id: Optional[str] = None) -> Dict[str, Any]:
        """
        执行指定日期的热点聚合任务，优化token使用

        Args:
            topic_date: 需要聚合的热点日期
            model_id: (可选) 传入的模型ID

        Returns:
            聚合结果摘要
        """
        start_time = time.time()
        logger.info(f"开始聚合日期 {topic_date.isoformat()} 的热点话题...")

        # 确保LLM提供商已初始化
        if not self.llm_provider:
            success, error_message = self._init_llm_provider(model_id=model_id)
            if not success:
                return {"status": "llm_error", "message": error_message}

        # 1. 获取原始热点
        raw_topics_result = self.hot_topic_repo.get_topics(
            filters={"topic_date": topic_date.isoformat(), "status": 1}, 
            page=1, 
            per_page=500
        )
        raw_topics = raw_topics_result.get("list", [])
        if not raw_topics:
            logger.info(f"日期 {topic_date.isoformat()} 没有找到需要聚合的热点话题。")
            return {"status": "no_topics", "message": "没有找到需要聚合的热点话题"}
        
        logger.info(f"为日期 {topic_date.isoformat()} 获取到 {len(raw_topics)} 条原始热点。")

        # 2. 创建ID到哈希的映射表
        id_to_hash_map = {}
        id_to_topic_map = {}
        for topic in raw_topics:
            topic_id = topic["id"]
            stable_hash = topic.get("stable_hash")
            if not stable_hash:
                # 如果没有哈希，生成一个
                stable_hash = self._generate_stable_hash(topic["topic_title"], topic["platform"])
            id_to_hash_map[topic_id] = stable_hash
            id_to_topic_map[topic_id] = topic

        # 3. 准备Prompt（使用ID）
        prompt = self._prepare_prompt(raw_topics, topic_date)

        try:
            ai_start_time = time.time()

            # 调用AI聚合，增加max_tokens
            ai_response = self.llm_provider.generate_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=6000  # 增加token限制
            )
            ai_processing_time = time.time() - ai_start_time
            logger.info(f"AI模型调用完成，耗时: {ai_processing_time:.2f} 秒")

            # 提取AI生成的聚合结果文本
            aggregated_result_text = ai_response.get("message", {}).get("content")
            if not aggregated_result_text:
                raise APIException("AI未能返回有效的聚合结果。")

            # 清理和解析AI返回的JSON文本
            if "```json" in aggregated_result_text:
                aggregated_result_text = aggregated_result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in aggregated_result_text:
                aggregated_result_text = aggregated_result_text.split("```")[1].split("```")[0].strip()

            try:
                aggregated_groups = json.loads(aggregated_result_text)
                if not isinstance(aggregated_groups, list):
                    raise ValueError("AI返回的不是一个列表")
            except json.JSONDecodeError as e:
                logger.error(f"解析AI返回的JSON失败: {e}\n原始文本: {aggregated_result_text}")
                # 尝试修复截断的JSON
                try:
                    # 如果JSON被截断，尝试找到最后一个完整的对象
                    fixed_text = self._try_fix_truncated_json(aggregated_result_text)
                    aggregated_groups = json.loads(fixed_text)
                    logger.info("成功修复截断的JSON")
                except:
                    raise APIException(f"AI返回结果格式错误，无法修复: {e}")
            except ValueError as e:
                logger.error(f"AI返回的数据结构错误: {e}\n原始数据: {aggregated_groups}")
                raise APIException(f"AI返回数据结构错误: {e}")

        except APIException as e:
            logger.error(f"AI聚合调用失败: {e.message}")
            return {"status": "ai_error", "message": f"AI聚合失败: {e.message}"}
        except Exception as e:
            logger.error(f"调用AI聚合时发生未知错误: {str(e)}", exc_info=True)
            return {"status": "error", "message": f"聚合过程中发生错误: {str(e)}"}

        # 4. 处理并存储聚合结果
        unified_topics_to_create = []
        processed_topic_hashes = set()

        for group in aggregated_groups:
            # 验证组数据结构
            if not all(k in group for k in ["unified_title", "related_topic_ids", "source_platforms"]):
                logger.warning(f"AI返回的组数据不完整，跳过: {group}")
                continue
            
            # 确保 keywords 字段存在
            keywords = group.get("keywords", [])
            if not keywords or not isinstance(keywords, list):
                keywords = []
                logger.warning(f"聚合组 '{group.get('unified_title')}' 没有生成关键词，使用空列表。")

            # 确保 category 字段存在
            category = group.get("category", "其他")
            if not category:
                category = "其他"
            
            # 将中文分类转换为英文代码
            category_mapping = {
                "政治": "politics", "经济": "economy", "科技": "technology", 
                "军事": "military", "社会": "society", "文化": "culture", 
                "体育": "sports", "健康": "health", "教育": "education", 
                "环境": "environment", "国际": "international", "灾难": "disaster", 
                "法律": "law", "旅游": "travel", "生活": "lifestyle", "其他": "other"
            }
            category_code = category_mapping.get(category, "other")

            # 将ID转换为哈希
            related_ids = group.get("related_topic_ids", [])
            related_hashes = []
            valid_ids = []
            representative_url = None
            
            for topic_id in related_ids:
                if topic_id in id_to_hash_map:
                    related_hashes.append(id_to_hash_map[topic_id])
                    valid_ids.append(topic_id)
                    # 获取代表性URL
                    if not representative_url and topic_id in id_to_topic_map:
                        topic_url = id_to_topic_map[topic_id].get("topic_url")
                        if topic_url:
                            representative_url = topic_url
            
            if not related_hashes:
                logger.warning(f"聚合组 '{group.get('unified_title')}' 没有找到有效的关联ID，跳过")
                continue

            unified_data = {
                "topic_date": topic_date,
                "unified_title": group["unified_title"],
                "unified_summary": group.get("unified_summary"),
                "keywords": keywords,
                "category": category_code,  # 添加分类字段
                "related_topic_hashes": related_hashes,  # 使用稳定哈希
                "related_topic_ids": valid_ids,  # 保留原ID作为备用
                "source_platforms": list(set(group.get("source_platforms", []))),
                "topic_count": len(related_hashes),
                "representative_url": representative_url,
                "ai_model_used": getattr(self.llm_provider, "default_model", "Unknown"),
                "ai_processing_time": ai_processing_time / len(aggregated_groups) if aggregated_groups else 0
            }
            unified_topics_to_create.append(unified_data)
            processed_topic_hashes.update(related_hashes)

        # 5. 删除旧数据
        logger.info(f"准备删除日期 {topic_date.isoformat()} 的旧统一热点数据...")
        self.unified_topic_repo.delete_by_date(topic_date)

        # 6. 批量创建新数据
        if unified_topics_to_create:
            logger.info(f"准备创建 {len(unified_topics_to_create)} 个新的统一热点...")
            success = self.unified_topic_repo.create_unified_topics_batch(unified_topics_to_create)
            if not success:
                logger.error(f"批量创建统一热点失败，日期: {topic_date.isoformat()}")
                return {"status": "db_error", "message": "存储统一热点失败"}
        else:
            logger.info(f"日期 {topic_date.isoformat()} 没有生成有效的聚合热点组。")

        # 7. 返回结果
        total_time = time.time() - start_time
        logger.info(f"日期 {topic_date.isoformat()} 热点聚合完成，共生成 {len(unified_topics_to_create)} 个统一热点，总耗时: {total_time:.2f} 秒。")

        return {
            "status": "success",
            "unified_topics_created": len(unified_topics_to_create),
            "raw_topics_processed": len(processed_topic_hashes),
            "total_time_seconds": round(total_time, 2),
            "ai_model_used": getattr(self.llm_provider, "default_model", "Unknown"),
            "provider_used": self.llm_provider.get_provider_name() if self.llm_provider else "Unknown"
        }

    def _try_fix_truncated_json(self, json_text: str) -> str:
        """尝试修复被截断的JSON"""
        # 移除最后一个不完整的对象
        last_complete_brace = json_text.rfind('}')
        if last_complete_brace != -1:
            # 找到最后一个完整对象的结束位置
            truncated = json_text[:last_complete_brace + 1]
            # 确保数组正确闭合
            if not truncated.rstrip().endswith(']'):
                truncated += '\n]'
            return truncated
        raise ValueError("无法修复截断的JSON")