# app/domains/hot_topics/services/hot_topic_aggregation_service.py
import logging
import json
import time
from datetime import date
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.infrastructure.database.repositories.hot_topic_repository import HotTopicRepository,UnifiedHotTopicRepository

from app.infrastructure.llm_providers.factory import LLMProviderFactory # 假设已有
from app.infrastructure.llm_providers.base import LLMProviderInterface
from app.core.exceptions import APIException

logger = logging.getLogger(__name__)

class HotTopicAggregationService:
    """
    负责使用AI聚合不同平台的热点话题服务
    """
    def __init__(
        self,
        db_session: Session,
        hot_topic_repo: HotTopicRepository,
        unified_topic_repo: UnifiedHotTopicRepository,
        llm_provider: LLMProviderInterface # 需要注入配置好的LLM Provider
    ):
        self.db_session = db_session
        self.hot_topic_repo = hot_topic_repo
        self.unified_topic_repo = unified_topic_repo
        self.llm_provider = llm_provider # 示例：需要通过工厂和配置创建

    def _prepare_prompt(self, topics: List[Dict[str, Any]], target_date: date) -> str:
        """准备用于AI聚合的Prompt"""
        
        # 仅选取关键信息减少 token 消耗
        simplified_topics = [
            {
                "id": topic["id"], # 必须包含原始ID
                "platform": topic["platform"],
                "title": topic["topic_title"],
                "description": topic.get("topic_description", "")[:100] # 限制描述长度
            } 
            for topic in topics if topic.get("topic_title") # 确保有标题
        ]

        # 将列表转换为JSON字符串以便放入Prompt
        topics_json_str = json.dumps(simplified_topics, ensure_ascii=False, indent=2)

        # 构建Prompt
        prompt = f"""
        任务：请分析以下来自不同平台在 {target_date.isoformat()} 的热点列表，将描述**同一核心事件或话题**的热点归为一组。

        要求：
        1. 识别相似的热点并将它们分组。
        2. 为每一个识别出的组生成一个简洁、准确、中立的统一标题 (unified_title)，不超过30个字。
        3. 为每个组生成一个50字以内的统一摘要 (unified_summary)。
        4. 为每个组提取2-3个关键词 (keywords)，这些关键词应能准确代表该热点的核心内容，用于后续检索相关文章。
        5. 在每个组中，必须包含所有被归入该组的原始热点的 ID 列表 (related_topic_ids)。
        6. 在每个组中，必须包含所有涉及的平台名称列表 (source_platforms)。

        原始热点数据 (JSON格式):
        ```json
        {topics_json_str}
        ```

        输出格式要求：
        请严格按照以下JSON格式返回结果，返回一个包含多个组对象的列表。每个组对象包含 unified_title, unified_summary, keywords, related_topic_ids, source_platforms。

        ```json
        [
        {{
            "unified_title": "统一标题1",
            "unified_summary": "统一摘要1",
            "keywords": ["关键词1", "关键词2", "关键词3"],
            "related_topic_ids": [原始ID1, 原始ID5, 原始ID10],
            "source_platforms": ["平台A", "平台B"]
        }},
        {{
            "unified_title": "统一标题2",
            "unified_summary": "统一摘要2",
            "keywords": ["关键词1", "关键词2"],
            "related_topic_ids": [原始ID2, 原始ID8],
            "source_platforms": ["平台C"]
        }}
        // ... 更多组
        ]
        ```
        确保 related_topic_ids 中的 ID 是来自上方提供的原始热点数据中的 ID。
        确保 source_platforms 中的名称是来自原始热点数据的平台名称。
        确保每个组都有2-3个关键词，每个关键词应该是单个词或短语，不超过5个字。
        如果某些热点无法与其他热点合并成组，则它们**不应**出现在最终的输出中。只输出包含**至少两个**原始热点的聚合组。
        """
        return prompt.strip()

    def aggregate_topics_for_date(self, topic_date: date, model_id: Optional[str] = None) -> Dict[str, Any]:
        """
        执行指定日期的热点聚合任务

        Args:
            topic_date: 需要聚合的热点日期
            model_id: (可选) 指定使用的LLM模型ID

        Returns:
            聚合结果摘要，例如 {"status": "success", "unified_topics_created": 5}
        """
        start_time = time.time()
        logger.info(f"开始聚合日期 {topic_date.isoformat()} 的热点话题...")

        # 1. 获取当天的所有有效热点
        # 注意：可能需要分页获取如果数据量很大，这里简化为一次获取
        raw_topics_result = self.hot_topic_repo.get_topics(filters={"topic_date": topic_date.isoformat(), "status": 1}, page=1, per_page=500) # 假设每页500条能获取完
        raw_topics = raw_topics_result.get("list", [])

        if not raw_topics:
            logger.info(f"日期 {topic_date.isoformat()} 没有找到需要聚合的热点话题。")
            return {"status": "no_topics", "message": "没有找到需要聚合的热点话题"}
        
        logger.info(f"为日期 {topic_date.isoformat()} 获取到 {len(raw_topics)} 条原始热点。")

        # 2. 准备并调用AI进行聚合
        prompt = self._prepare_prompt(raw_topics, topic_date)
        ai_model_to_use = model_id or self.llm_provider.default_model # 获取模型ID

        try:
            logger.info(f"调用AI模型 {ai_model_to_use} 进行聚合...")
            ai_start_time = time.time()
            # 注意：实际调用可能需要根据你使用的LLM Provider调整参数
            ai_response = self.llm_provider.generate_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=ai_model_to_use,
                temperature=0.2, # 低温以获取更确定的分组
                max_tokens=4000 # 根据模型和预期输出调整
            )
            ai_processing_time = time.time() - ai_start_time
            logger.info(f"AI模型调用完成，耗时: {ai_processing_time:.2f} 秒")

            # 提取AI生成的聚合结果文本
            aggregated_result_text = ai_response.get("message", {}).get("content")
            if not aggregated_result_text:
                raise APIException("AI未能返回有效的聚合结果。")

            # 清理和解析AI返回的JSON文本
            # AI 可能返回被 markdown 包裹的 JSON，需要提取
            if "```json" in aggregated_result_text:
                 aggregated_result_text = aggregated_result_text.split("```json")[1].split("```")[0].strip()

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

        # 3. 处理并存储聚合结果
        unified_topics_to_create = []
        processed_raw_topic_ids = set()
        
        for group in aggregated_groups:
            # 验证组数据结构
            if not all(k in group for k in ["unified_title", "related_topic_ids", "source_platforms"]):
                logger.warning(f"AI返回的组数据不完整，跳过: {group}")
                continue
            
            # 确保 keywords 字段存在
            keywords = group.get("keywords", [])
            if not keywords or not isinstance(keywords, list):
                # 如果 AI 没有生成关键词，创建一个默认的空列表
                keywords = []
                logger.warning(f"聚合组 '{group.get('unified_title')}' 没有生成关键词，使用空列表。")
            
            unified_data = {
                "topic_date": topic_date,
                "unified_title": group["unified_title"],
                "unified_summary": group.get("unified_summary"), # 可选
                "keywords": keywords,  # 添加关键词
                "related_topic_ids": group.get("related_topic_ids", []),
                "source_platforms": list(set(group.get("source_platforms", []))), # 去重
                "topic_count": len(group.get("related_topic_ids", [])),
                "ai_model_used": ai_model_to_use,
                "ai_processing_time": ai_processing_time / len(aggregated_groups) if aggregated_groups else 0
                # 可以增加 representative_url 和 aggregated_hotness_score 的逻辑
            }
            unified_topics_to_create.append(unified_data)
            processed_raw_topic_ids.update(group.get("related_topic_ids", []))


        # 4. 先删除旧的聚合数据（如果需要重新生成当天的）
        logger.info(f"准备删除日期 {topic_date.isoformat()} 的旧统一热点数据...")
        self.unified_topic_repo.delete_by_date(topic_date)

        # 5. 批量创建新的聚合数据
        if unified_topics_to_create:
            logger.info(f"准备创建 {len(unified_topics_to_create)} 个新的统一热点...")
            success = self.unified_topic_repo.create_unified_topics_batch(unified_topics_to_create)
            if not success:
                logger.error(f"批量创建统一热点失败，日期: {topic_date.isoformat()}")
                return {"status": "db_error", "message": "存储统一热点失败"}
        else:
            logger.info(f"日期 {topic_date.isoformat()} 没有生成有效的聚合热点组。")
            
        total_time = time.time() - start_time
        logger.info(f"日期 {topic_date.isoformat()} 热点聚合完成，共生成 {len(unified_topics_to_create)} 个统一热点，总耗时: {total_time:.2f} 秒。")

        return {
            "status": "success",
            "unified_topics_created": len(unified_topics_to_create),
            "raw_topics_processed": len(processed_raw_topic_ids),
            "total_time_seconds": round(total_time, 2)
        }