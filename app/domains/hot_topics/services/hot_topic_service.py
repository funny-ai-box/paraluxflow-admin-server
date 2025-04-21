# app/domains/hot_topics/services/hot_topic_service.py
"""热点话题服务实现"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class HotTopicService:
    """热点话题服务"""
    
    def __init__(self, task_repo, topic_repo, log_repo=None):
        """初始化服务
        
        Args:
            task_repo: 任务仓库
            topic_repo: 话题仓库
            log_repo: 日志仓库，可选
        """
        self.task_repo = task_repo
        self.topic_repo = topic_repo
        self.log_repo = log_repo
    
    def create_task(self, user_id: str, platforms: List[str], schedule_time: Optional[str] = None) -> Dict[str, Any]:
        """创建热点爬取任务
        
        Args:
            user_id: 用户ID
            platforms: 平台列表
            schedule_time: 计划执行时间，可选
            
        Returns:
            创建的任务
            
        Raises:
            Exception: 创建失败时抛出异常
        """
        # 验证平台
        valid_platforms = ["weibo", "zhihu", "baidu", "toutiao", "douyin"]
        platforms = [p for p in platforms if p in valid_platforms]
        
        if not platforms:
            raise ValueError("无有效的平台")
        
        # 创建任务数据
        task_data = {
            "task_id": str(uuid.uuid4()),
            "status": 0,  # 待爬取
            "platforms": platforms,
            "trigger_type": "manual",
            "triggered_by": user_id
        }
        
        # 如果指定了计划时间
        if schedule_time:
            try:
                scheduled_time = datetime.fromisoformat(schedule_time)
                task_data["scheduled_time"] = scheduled_time
                task_data["trigger_type"] = "scheduled"
            except ValueError:
                raise ValueError("无效的时间格式，请使用ISO格式 (YYYY-MM-DDTHH:MM:SS)")
        
        # 创建任务
        err, task = self.task_repo.create_task(task_data)
        if err:
            raise Exception(f"创建任务失败: {err}")
        
        return task
    
    def schedule_task(self, user_id: str, platforms: List[str], schedule_time: str, 
                    recurrence: Optional[str] = None) -> Dict[str, Any]:
        """创建定时任务
        
        Args:
            user_id: 用户ID
            platforms: 平台列表
            schedule_time: 计划执行时间，ISO格式
            recurrence: 重复类型，可选值: daily, weekly, monthly, none
            
        Returns:
            创建的任务
            
        Raises:
            Exception: 创建失败时抛出异常
        """
        # 验证平台
        valid_platforms = ["weibo", "zhihu", "baidu", "toutiao", "douyin"]
        platforms = [p for p in platforms if p in valid_platforms]
        
        if not platforms:
            raise ValueError("无有效的平台")
        
        # 验证并转换时间
        try:
            scheduled_time = datetime.fromisoformat(schedule_time)
        except ValueError:
            raise ValueError("无效的时间格式，请使用ISO格式 (YYYY-MM-DDTHH:MM:SS)")
        
        # 验证重复类型
        valid_recurrence = ["daily", "weekly", "monthly", "none", None]
        if recurrence not in valid_recurrence:
            raise ValueError(f"无效的重复类型，可选值: {', '.join(valid_recurrence[:-1])}")
        
        # 创建任务数据
        task_data = {
            "task_id": str(uuid.uuid4()),
            "status": 0,  # 待爬取
            "platforms": platforms,
            "scheduled_time": scheduled_time,
            "trigger_type": "scheduled",
            "triggered_by": user_id,
            "recurrence": recurrence or "none"  # 存储重复类型
        }
        
        # 创建任务
        err, task = self.task_repo.create_task(task_data)
        if err:
            raise Exception(f"创建定时任务失败: {err}")
        
        return task
    
    def get_tasks(self, page: int = 1, per_page: int = 20, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取任务列表
        
        Args:
            page: 页码
            per_page: 每页数量
            filters: 筛选条件，可选
            
        Returns:
            分页的任务列表
        """
        return self.task_repo.get_tasks(filters or {}, page, per_page)
    
    def get_task_detail(self, task_id: str) -> Dict[str, Any]:
        """获取任务详情
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务详情
            
        Raises:
            Exception: 获取失败时抛出异常
        """
        err, task = self.task_repo.update_task(task_id, {})  # 使用空更新来获取详情
        if err:
            raise Exception(f"获取任务详情失败: {err}")
        
        return task
    
    def save_crawl_results(self, task_id: str, platform: str, result_data: Dict[str, Any]) -> bool:
        """保存爬取结果
        
        Args:
            task_id: 任务ID
            platform: 平台
            result_data: 结果数据
            
        Returns:
            是否保存成功
        """
        return self.process_task_result(task_id, platform, result_data)
    
    def process_task_result(self, task_id: str, platform: str, result_data: Dict[str, Any]) -> bool:
        try:
            logger.info(f"开始处理任务 {task_id} 的结果，平台: {platform}")
            logger.info(f"结果数据: {result_data}")
            
            batch_id = result_data.get("batch_id", str(uuid.uuid4()))
            status = result_data.get("status", 2)  # 默认失败
            topics = result_data.get("topics", [])
            
            logger.info(f"话题数量: {len(topics)}")
            
            # 获取任务的爬取日期（默认为今天）
            topic_date = datetime.now().date()
            logger.info(f"初始话题日期: {topic_date}")
            
            # 如果结果数据中包含日期信息，优先使用结果数据中的日期
            if "topic_date" in result_data and result_data["topic_date"]:
                try:
                    # 尝试解析日期字符串
                    if isinstance(result_data["topic_date"], str):
                        topic_date = datetime.fromisoformat(result_data["topic_date"].rstrip('Z')).date()
                        logger.info(f"从请求获取到话题日期: {topic_date}")
                    elif isinstance(result_data["topic_date"], datetime):
                        topic_date = result_data["topic_date"].date()
                        logger.info(f"从请求获取到话题日期: {topic_date}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"解析话题日期失败，使用当前日期: {str(e)}")
            
            # 记录日志
            if self.log_repo:
                logger.info("创建日志记录...")
                # 代码省略...
            
            # 处理话题数据
            if status == 1 and topics:
                logger.info(f"开始处理话题数据，数量: {len(topics)}")
                # 准备话题数据
                topics_to_save = []
                for idx, topic in enumerate(topics):
                    topic_data = {
                        "task_id": task_id,
                        "batch_id": batch_id,
                        "platform": platform,
                        "topic_title": topic.get("title", ""),
                        "topic_url": topic.get("url", ""),
                        "hot_value": topic.get("hot_value", ""),
                        "topic_description": topic.get("desc", "") or topic.get("excerpt", ""),
                        "is_hot": topic.get("is_hot", False),
                        "is_new": topic.get("is_new", False),
                        "rank": idx + 1,  # 使用列表索引作为排名
                        "heat_level": self._calculate_heat_level(topic.get("hot_value", "")),
                        "crawler_id": result_data.get("crawler_id"),
                        "crawl_time": datetime.now(),
                        "topic_date": topic_date,  # 设置话题日期
                        "status": 1  # 有效
                    }
                    topics_to_save.append(topic_data)
                    logger.info(f"准备保存话题: {topic_data['topic_title']}, 日期: {topic_date}")
                
                # 保存话题数据
                if topics_to_save:
                    logger.info(f"开始保存 {len(topics_to_save)} 个话题到数据库")
                    save_result = self.topic_repo.create_topics(topics_to_save)
                    logger.info(f"保存话题结果: {'成功' if save_result else '失败'}")
                else:
                    logger.warning("没有话题需要保存")
            else:
                logger.info(f"不需要处理话题数据: status={status}, topics数量={len(topics)}")
            
            # 检查任务是否完成
            logger.info("检查任务是否完成...")
            self._check_task_completion(task_id)
            
            logger.info(f"任务 {task_id} 结果处理完成")
            return True
        except Exception as e:
            logger.error(f"处理爬取结果失败: {str(e)}", exc_info=True)  # 添加完整堆栈
            return False
        
    def get_hot_topics(self, platform: Optional[str] = None, page: int = 1, per_page: int = 20, 
                      filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取热点话题列表
        
        Args:
            platform: 平台筛选，可选
            page: 页码
            per_page: 每页数量
            filters: 其他筛选条件，可选
            
        Returns:
            分页的热点话题列表
        """
        filters = filters or {}
        if platform:
            filters["platform"] = platform
        
        return self.topic_repo.get_topics(filters, page, per_page)
    
    def get_latest_hot_topics(self, platform: Optional[str] = None, limit: int = 50, topic_date: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
        """获取最新热点话题
        
        Args:
            platform: 平台筛选，可选
            limit: 获取数量
            topic_date: 指定日期，可选
            
        Returns:
            最新热点话题列表
        """
        return self.topic_repo.get_latest_hot_topics(platform, limit, topic_date)
    
    def get_hot_topic_stats(self) -> Dict[str, Any]:
        """获取热点话题统计信息
        
        Returns:
            统计信息
        """
        # 获取各平台的最新热点
        platforms = ["weibo", "zhihu", "baidu", "toutiao", "douyin"]
        stats = {
            "total_tasks": 0,
            "total_topics": 0,
            "platform_stats": {}
        }
        
        for platform in platforms:
            topics = self.topic_repo.get_latest_hot_topics(platform, 1)
            stats["platform_stats"][platform] = {
                "topic_count": len(topics),
                "latest_update": topics[0]["created_at"] if topics else None
            }
            stats["total_topics"] += len(topics)
        
        # 获取最近的任务数
        tasks = self.task_repo.get_tasks({}, page=1, per_page=1)
        stats["total_tasks"] = tasks["total"]
        
        return stats
    
    def _check_task_completion(self, task_id: str) -> None:
        """检查任务是否完成
        
        Args:
            task_id: 任务ID
        """
        try:
            # 获取任务详情
            err, task = self.task_repo.update_task(task_id, {})
            if err:
                logger.error(f"获取任务详情失败: {err}")
                return
            
            # 获取任务的平台
            platforms = task.get("platforms", [])
            
            # 查询是否每个平台都有对应的日志
            all_platforms_processed = True
            if self.log_repo:
                for platform in platforms:
                    logs = self.log_repo.get_logs({"task_id": task_id, "platform": platform})
                    if not logs.get("list"):
                        all_platforms_processed = False
                        break
            
            # 如果所有平台都已处理，更新任务状态为已完成
            if all_platforms_processed:
                self.task_repo.update_task(task_id, {"status": 2})  # 已完成
        except Exception as e:
            logger.error(f"检查任务完成状态失败: {str(e)}")
    
    def _calculate_heat_level(self, hot_value: str) -> int:
        """计算热度等级
        
        Args:
            hot_value: 热度值字符串
            
        Returns:
            热度等级 (1-5)
        """
        try:
            # 移除非数字字符
            num_only = ''.join(c for c in hot_value if c.isdigit())
            if not num_only:
                return 1
            
            # 转换为数字
            value = int(num_only)
            
            # 热度划分规则
            if value > 1000000:  # 超过100万
                return 5
            elif value > 500000:  # 超过50万
                return 4
            elif value > 100000:  # 超过10万
                return 3
            elif value > 10000:  # 超过1万
                return 2
            else:
                return 1
        except Exception:
            return 1