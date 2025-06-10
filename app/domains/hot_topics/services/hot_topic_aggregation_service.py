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
    负责使用AI聚合不同平台的热点话题服务，优先使用火山引擎，并使用稳定哈希关联
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
        """准备用于AI聚合的Prompt，包含稳定哈希信息"""

        # 选取关键信息，包含稳定哈希
        simplified_topics = [
            {
                "id": topic["id"],
                "stable_hash": topic.get("stable_hash", ""),  # 添加稳定哈希
                "platform": topic["platform"],
                "title": topic["topic_title"],
                "description": topic.get("topic_description", "")[:100]
            }
            for topic in topics if topic.get("topic_title")
        ]

        topics_json_str = json.dumps(simplified_topics, ensure_ascii=False, indent=2)

        prompt = f"""
        任务：请分析以下来自不同平台在 {target_date.isoformat()} 的热点列表，将描述**同一核心事件或话题**的热点归为一组。

        要求：
        1. 识别相似的热点并将它们分组。
        2. 为每一个识别出的组生成一个简洁、准确、中立的统一标题 (unified_title)，不超过30个字。
        3. 为每个组生成一个50字以内的统一摘要 (unified_summary)。
        4. 为每个组提取2-3个关键词 (keywords)，用于后续检索相关文章。
        5. 在每个组中，必须包含所有被归入该组的原始热点的稳定哈希列表 (related_topic_hashes)。
        6. 在每个组中，必须包含所有涉及的平台名称列表 (source_platforms)。

        原始热点数据 (JSON格式):
        ```json
        {topics_json_str}
        ```

        输出格式要求：
        请严格按照以下JSON格式返回结果，返回一个包含多个组对象的列表。每个组对象包含 unified_title, unified_summary, keywords, related_topic_hashes, source_platforms。

        ```json
        [
        {{
            "unified_title": "统一标题1",
            "unified_summary": "统一摘要1",
            "keywords": ["关键词1", "关键词2", "关键词3"],
            "related_topic_hashes": ["hash1", "hash2", "hash3"],
            "source_platforms": ["平台A", "平台B"]
        }},
        {{
            "unified_title": "统一标题2",
            "unified_summary": "统一摘要2",
            "keywords": ["关键词1", "关键词2"],
            "related_topic_hashes": ["hash4", "hash5"],
            "source_platforms": ["平台C"]
        }}
        ]
        ```
        
        确保 related_topic_hashes 中的哈希值是来自上方提供的原始热点数据中的 stable_hash。
        确保 source_platforms 中的名称是来自原始热点数据的平台名称。
        确保每个组都有2-3个关键词，每个关键词应该是单个词或短语，不超过10个字。
        如果某些热点无法与其他热点合并成组，则它们**不应**出现在最终的输出中。只输出包含**至少两个**原始热点的聚合组。
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
        执行指定日期的热点聚合任务，使用稳定哈希进行关联

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

        # 2. 准备Prompt
        prompt = self._prepare_prompt(raw_topics, topic_date)

        try:
            ai_start_time = time.time()

            # 调用AI聚合
            ai_response = self.llm_provider.generate_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4000
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
                raise APIException(f"AI返回结果格式错误: {e}")
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
            if not all(k in group for k in ["unified_title", "related_topic_hashes", "source_platforms"]):
                logger.warning(f"AI返回的组数据不完整，跳过: {group}")
                continue
            
            # 确保 keywords 字段存在
            keywords = group.get("keywords", [])
            if not keywords or not isinstance(keywords, list):
                keywords = []
                logger.warning(f"聚合组 '{group.get('unified_title')}' 没有生成关键词，使用空列表。")

            # 验证稳定哈希并提取代表性URL
            related_hashes = group.get("related_topic_hashes", [])
            representative_url = None
            valid_hashes = []
            
            # 从原始热点中查找匹配的哈希
            for topic in raw_topics:
                topic_hash = topic.get("stable_hash", "")
                if topic_hash in related_hashes:
                    valid_hashes.append(topic_hash)
                    if not representative_url and topic.get("topic_url"):
                        representative_url = topic.get("topic_url")
            
            if not valid_hashes:
                logger.warning(f"聚合组 '{group.get('unified_title')}' 没有找到有效的关联哈希，跳过")
                continue

            # 为了向后兼容，也收集对应的topic_ids
            related_ids = []
            for topic in raw_topics:
                if topic.get("stable_hash", "") in valid_hashes:
                    related_ids.append(topic["id"])

            unified_data = {
                "topic_date": topic_date,
                "unified_title": group["unified_title"],
                "unified_summary": group.get("unified_summary"),
                "keywords": keywords,
                "related_topic_hashes": valid_hashes,  # 使用稳定哈希
                "related_topic_ids": related_ids,  # 保留原ID作为备用
                "source_platforms": list(set(group.get("source_platforms", []))),
                "topic_count": len(valid_hashes),
                "representative_url": representative_url,
                "ai_model_used": getattr(self.llm_provider, "default_model", "Unknown"),
                "ai_processing_time": ai_processing_time / len(aggregated_groups) if aggregated_groups else 0
            }
            unified_topics_to_create.append(unified_data)
            processed_topic_hashes.update(valid_hashes)

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