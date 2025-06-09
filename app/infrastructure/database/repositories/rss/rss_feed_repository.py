# app/infrastructure/database/repositories/rss_feed_repository.py
"""RSS Feed仓库"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, case, func, or_, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models.rss import RssFeed, RssFeedCategory

logger = logging.getLogger(__name__)

class RssFeedRepository:
    """RSS Feed仓库"""

    def __init__(self, db_session: Session):
        """初始化仓库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session

    def get_feeds_eligible_for_update(self) -> List[Dict[str, Any]]:
        """获取需要更新的Feed列表
        
        Returns:
            符合条件的Feed列表
        """
        try:
            # 获取超过6小时未更新且处于激活状态的Feed
            six_hours_ago = datetime.now() - timedelta(hours=6)
            
            eligible_feeds = self.db.query(RssFeed).filter(
                RssFeed.is_active == True,
                or_(
                    RssFeed.last_successful_fetch_at == None,
                    RssFeed.last_successful_fetch_at < six_hours_ago,
                )
            ).order_by(RssFeed.last_successful_fetch_at).all()
            
            return [self._feed_to_dict(feed) for feed in eligible_feeds]
        except SQLAlchemyError as e:
            logger.error(f"获取需要更新的Feed列表失败: {str(e)}")
            return []

    def get_all_feeds(self) -> List[Dict[str, Any]]:
        """获取所有Feed
        
        Returns:
            所有Feed列表
        """
        try:
            feeds = self.db.query(RssFeed).order_by(desc(RssFeed.created_at)).all()
            return [self._feed_to_dict(feed) for feed in feeds]
        except SQLAlchemyError as e:
            logger.error(f"获取所有Feed失败: {str(e)}")
            return []

    def get_filtered_feeds(self, filters: Dict[str, Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """根据条件筛选Feed，支持分页
        
        Args:
            filters: 筛选条件字典
            page: 页码，从1开始
            per_page: 每页记录数
                
        Returns:
            分页结果，包含列表和分页信息
        """
        try:
            query = self.db.query(RssFeed)
            
            # 应用筛选条件
            if filters:
                if filters.get("title"):
                    query = query.filter(RssFeed.title.like(f"%{filters['title']}%"))
                
                if filters.get("category_id"):
                    query = query.filter(RssFeed.category_id == filters["category_id"])
                    
                if filters.get("url"):
                    query = query.filter(RssFeed.url.like(f"%{filters['url']}%"))
                    
                if filters.get("description"):
                    query = query.filter(RssFeed.description.like(f"%{filters['description']}%"))
                    
                if "is_active" in filters:
                    query = query.filter(RssFeed.is_active == filters["is_active"])
            
            # 计算总记录数
            total = query.count()
            
            # 按ID降序排列
            query = query.order_by(desc(RssFeed.id))
            
            # 应用分页
            feeds = query.limit(per_page).offset((page - 1) * per_page).all()
            
            # 计算总页数
            pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            return {
                "list": [self._feed_to_dict(feed) for feed in feeds],
                "total": total,
                "pages": pages,
                "current_page": page,
                "per_page": per_page
            }
        except SQLAlchemyError as e:
            logger.error(f"筛选Feed失败: {str(e)}")
            return {
                "list": [],
                "total": 0,
                "pages": 0,
                "current_page": page,
                "per_page": per_page,
                "error": str(e)
            }

    def get_feed_by_id(self, feed_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """根据ID获取Feed
        
        Args:
            feed_id: Feed ID
            
        Returns:
            (错误信息, Feed信息)
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return f"未找到ID为{feed_id}的Feed", None
            
            return None, self._feed_to_dict(feed)
        except SQLAlchemyError as e:
            logger.error(f"获取Feed失败, ID={feed_id}: {str(e)}")
            return str(e), None

    def add_feed(self, feed_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """添加新Feed
        
        Args:
            feed_data: Feed数据
            
        Returns:
            (错误信息, 新增的Feed信息)
        """
        try:
            new_feed = RssFeed(**feed_data)
            self.db.add(new_feed)
            self.db.commit()
            self.db.refresh(new_feed)
            
            return None, self._feed_to_dict(new_feed)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"添加Feed失败: {str(e)}")
            return str(e), None

    def update_feed(self, feed_id: str, feed_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新Feed信息
        
        Args:
            feed_id: Feed ID
            feed_data: 更新的数据
            
        Returns:
            (错误信息, 更新后的Feed信息)
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return f"未找到ID为{feed_id}的Feed", None
            
            # 更新字段
            for key, value in feed_data.items():
                if hasattr(feed, key):
                    setattr(feed, key, value)
            
            self.db.commit()
            self.db.refresh(feed)
            
            return None, self._feed_to_dict(feed)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新Feed失败, ID={feed_id}: {str(e)}")
            return str(e), None

    def update_feed_status(self, feed_id: str, status: bool) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新Feed状态
        
        Args:
            feed_id: Feed ID
            status: 新状态
            
        Returns:
            (错误信息, 更新后的Feed信息)
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return f"未找到ID为{feed_id}的Feed", None
            
            feed.is_active = status
            self.db.commit()
            self.db.refresh(feed)
            
            return None, self._feed_to_dict(feed)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新Feed状态失败, ID={feed_id}: {str(e)}")
            return str(e), None

    def update_feed_fetch_status(
        self, feed_id: str, status: int, error_message: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """更新Feed获取状态
        
        Args:
            feed_id: Feed ID
            status: 状态(1=成功, 2=失败)
            error_message: 错误信息
            
        Returns:
            (错误信息, 更新后的Feed信息)
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return f"未找到ID为{feed_id}的Feed", None
            
            current_time = datetime.now()
            feed.last_fetch_at = current_time
            feed.last_fetch_status = status
            
            if status == 1:  # 成功
                feed.last_successful_fetch_at = current_time
                feed.consecutive_failures = 0
                feed.last_fetch_error = None
            else:  # 失败
                feed.consecutive_failures += 1
                feed.last_fetch_error = error_message
            
            self.db.commit()
            self.db.refresh(feed)
            
            return None, self._feed_to_dict(feed)
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新Feed获取状态失败, ID={feed_id}: {str(e)}")
            return str(e), None

    def bulk_update_feeds_fetch_time(self, feed_ids: List[str]) -> Optional[str]:
        """批量更新Feed获取时间
        
        Args:
            feed_ids: Feed ID列表
            
        Returns:
            错误信息
        """
        try:
            self.db.query(RssFeed).filter(RssFeed.id.in_(feed_ids)).update(
                {RssFeed.last_fetch_at: datetime.now()},
                synchronize_session=False
            )
            self.db.commit()
            return None
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"批量更新Feed获取时间失败: {str(e)}")
            return str(e)
        
    def get_feeds_for_sync(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取待同步的Feed列表
        
        Args:
            limit: 获取数量
            
        Returns:
            待同步Feed列表，按优先级排序
        """
        try:
   
            
            # MySQL兼容的查询：使用ISNULL()函数和条件排序
            query = self.db.query(RssFeed).filter(
                RssFeed.is_active == True,
                # 没有被其他爬虫锁定，或者锁定时间超过30分钟（防止死锁）
                or_(
                    RssFeed.last_sync_crawler_id.is_(None),
                    RssFeed.last_sync_started_at < datetime.now() - timedelta(minutes=30)
                )
            ).order_by(
                # 优先级：从未同步过的 > 同步失败的 > 最久未同步的
                case(
                    (RssFeed.last_sync_at.is_(None), 0),  # 从未同步过的优先级最高
                    (RssFeed.last_sync_status == 2, 1),   # 同步失败的次优先
                    else_=2                               # 其他情况
                ),
                # MySQL兼容：NULL值排在前面
                func.isnull(RssFeed.last_sync_at).desc(),
                RssFeed.last_sync_at.asc()
            ).limit(limit)
            
            feeds = []
            for feed in query.all():
                feed_dict = self._feed_to_dict(feed)
                # 添加同步相关信息
                feed_dict.update({
                    "last_sync_at": feed.last_sync_at.isoformat() if feed.last_sync_at else None,
                    "last_sync_status": feed.last_sync_status,
                    "last_sync_error": feed.last_sync_error,
                    "sync_priority": self._calculate_sync_priority(feed)
                })
                feeds.append(feed_dict)
            
            return feeds
        except Exception as e:
            logger.error(f"获取待同步Feed失败: {str(e)}")
            return []

    def mark_feed_syncing(self, feed_id: str, crawler_id: str) -> bool:
        """标记Feed正在同步
        
        Args:
            feed_id: Feed ID
            crawler_id: 爬虫ID
            
        Returns:
            是否成功
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return False
            
            # 检查是否已被其他爬虫锁定
            if (feed.last_sync_crawler_id and 
                feed.last_sync_crawler_id != crawler_id and
                feed.last_sync_started_at and 
                feed.last_sync_started_at > datetime.now() - timedelta(minutes=30)):
                logger.warning(f"Feed {feed_id} 已被爬虫 {feed.last_sync_crawler_id} 锁定")
                return False
            
            # 标记为正在同步
            feed.last_sync_started_at = datetime.now()
            feed.last_sync_crawler_id = crawler_id
            
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"标记Feed同步状态失败: {str(e)}")
            self.db.rollback()
            return False

    def update_feed_sync_status(self, feed_id: str, update_data: Dict[str, Any]) -> bool:
        """更新Feed同步状态
        
        Args:
            feed_id: Feed ID
            update_data: 更新数据
            
        Returns:
            是否成功
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return False
            
            # 更新字段
            for key, value in update_data.items():
                if hasattr(feed, key):
                    setattr(feed, key, value)
            
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"更新Feed同步状态失败: {str(e)}")
            self.db.rollback()
            return False

    def count_active_feeds(self) -> int:
        """统计激活的Feed数量"""
        try:
            return self.db.query(RssFeed).filter(RssFeed.is_active == True).count()
        except Exception as e:
            logger.error(f"统计激活Feed数量失败: {str(e)}")
            return 0

    def count_pending_sync_feeds(self) -> int:
        """统计待同步的Feed数量"""
        try:
            return self.db.query(RssFeed).filter(
                RssFeed.is_active == True,
                or_(
                    RssFeed.last_sync_at.is_(None),  # 从未同步过
                    RssFeed.last_sync_at < datetime.now() - timedelta(hours=1)  # 超过1小时未同步
                ),
                or_(
                    RssFeed.last_sync_crawler_id.is_(None),
                    RssFeed.last_sync_started_at < datetime.now() - timedelta(minutes=30)
                )
            ).count()
        except Exception as e:
            logger.error(f"统计待同步Feed数量失败: {str(e)}")
            return 0

    def count_syncing_feeds(self) -> int:
        """统计正在同步的Feed数量"""
        try:
            return self.db.query(RssFeed).filter(
                RssFeed.is_active == True,
                RssFeed.last_sync_crawler_id.isnot(None),
                RssFeed.last_sync_started_at > datetime.now() - timedelta(minutes=30)
            ).count()
        except Exception as e:
            logger.error(f"统计正在同步Feed数量失败: {str(e)}")
            return 0

    def _calculate_sync_priority(self, feed) -> int:
        """计算Feed同步优先级（数字越小优先级越高）
        
        Args:
            feed: Feed对象
            
        Returns:
            优先级数字
        """
        if not feed.last_sync_at:
            return 0  # 从未同步过，最高优先级
        
        if feed.last_sync_status == 2:
            return 1  # 同步失败，高优先级
        
        # 根据最后同步时间计算优先级
        hours_since_sync = (datetime.now() - feed.last_sync_at).total_seconds() / 3600
        
        if hours_since_sync > 24:
            return 2  # 超过24小时，高优先级
        elif hours_since_sync > 12:
            return 3  # 超过12小时，中等优先级
        elif hours_since_sync > 6:
            return 4  # 超过6小时，较低优先级
        else:
            return 5  # 6小时内，低优先级
        
    def auto_disable_failed_feeds(self, max_failures: int = 20) -> List[Dict[str, Any]]:
        """自动关闭连续失败过多的Feed
        
        Args:
            max_failures: 最大失败次数
            
        Returns:
            被关闭的Feed列表
        """
        try:
            # 查找连续失败过多的激活Feed
            failed_feeds = self.db.query(RssFeed).filter(
                RssFeed.is_active == True,
                RssFeed.consecutive_failures >= max_failures
            ).all()
            
            disabled_feeds = []
            for feed in failed_feeds:
                # 关闭Feed
                feed.is_active = False
                # 如果数据库模型中有这些字段，则设置它们
                if hasattr(feed, 'disabled_at'):
                    feed.disabled_at = datetime.now()
                if hasattr(feed, 'disabled_reason'):
                    feed.disabled_reason = f"连续失败{feed.consecutive_failures}次自动关闭"
                if hasattr(feed, 'auto_disabled'):
                    feed.auto_disabled = True
                if hasattr(feed, 'health_status'):
                    feed.health_status = "disabled"
                
                disabled_feeds.append({
                    "id": feed.id,
                    "title": feed.title,
                    "consecutive_failures": feed.consecutive_failures,
                    "last_sync_error": getattr(feed, 'last_sync_error', None),
                    "disabled_at": datetime.now().isoformat()
                })
            
            if disabled_feeds:
                self.db.commit()
                logger.info(f"自动关闭了 {len(disabled_feeds)} 个连续失败的Feed")
            
            return disabled_feeds
        except Exception as e:
            self.db.rollback()
            logger.error(f"自动关闭失败Feed失败: {str(e)}")
            return []

    def get_feeds_for_sync_improved(
        self, 
        limit: int = 10, 
        skip_recent_success: bool = True,
        success_interval_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """获取待同步的Feed列表 - 改进版本
        
        逻辑改进：
        1. 30分钟内成功过的不再获取
        2. 连续失败20次的源已被自动关闭
        3. 按失败次数优先级排序（失败少的优先）
        
        Args:
            limit: 获取数量
            skip_recent_success: 是否跳过最近成功的
            success_interval_minutes: 成功间隔分钟数
            
        Returns:
            待同步Feed列表，按优先级排序
        """
        try:
            # 计算时间阈值
            success_threshold = datetime.now() - timedelta(minutes=success_interval_minutes)
            sync_lock_threshold = datetime.now() - timedelta(minutes=30)  # 同步锁定超时时间
            
            query = self.db.query(RssFeed).filter(
                RssFeed.is_active == True,
                RssFeed.consecutive_failures < 20,  # 排除连续失败过多的
                # 没有被其他爬虫锁定，或者锁定时间超过30分钟（防止死锁）
                or_(
                    RssFeed.last_sync_crawler_id.is_(None),
                    RssFeed.last_sync_started_at < sync_lock_threshold
                )
            )
            
            # 如果跳过最近成功的
            if skip_recent_success:
                # 检查字段是否存在
                if hasattr(RssFeed, 'last_successful_sync_at'):
                    query = query.filter(
                        or_(
                            RssFeed.last_successful_sync_at.is_(None),  # 从未成功过
                            RssFeed.last_successful_sync_at < success_threshold  # 超过指定时间未成功
                        )
                    )
                else:
                    # 如果没有 last_successful_sync_at 字段，使用 last_successful_fetch_at
                    query = query.filter(
                        or_(
                            RssFeed.last_successful_fetch_at.is_(None),
                            RssFeed.last_successful_fetch_at < success_threshold
                        )
                    )
            
            # 优先级排序：
            # 1. 从未同步过的（最高优先级）
            # 2. 按连续失败次数升序（失败少的优先）
            # 3. 按最后同步时间升序（最久未同步的优先）
            query = query.order_by(
                case(
                    (RssFeed.last_sync_at.is_(None), 0),  # 从未同步过的优先级最高
                    else_=1
                ),
                RssFeed.consecutive_failures.asc(),  # 失败次数少的优先
                func.isnull(RssFeed.last_sync_at).desc(),  # NULL值排在前面
                RssFeed.last_sync_at.asc()  # 最久未同步的优先
            ).limit(limit)
            
            feeds = []
            for feed in query.all():
                feed_dict = self._feed_to_dict(feed)
                # 添加同步相关信息
                feed_dict.update({
                    "last_sync_at": feed.last_sync_at.isoformat() if feed.last_sync_at else None,
                    "last_sync_status": feed.last_sync_status,
                    "last_sync_error": feed.last_sync_error,
                    "last_successful_sync_at": getattr(feed, 'last_successful_sync_at', None),
                    "consecutive_failures": feed.consecutive_failures,
                    "sync_priority": self._calculate_sync_priority_improved(feed),
                    "estimated_next_sync": self._estimate_next_sync_time(feed, success_interval_minutes)
                })
                feeds.append(feed_dict)
            
            return feeds
        except Exception as e:
            logger.error(f"获取待同步Feed失败: {str(e)}")
            return []

    def update_feed_sync_status_improved(self, feed_id: str, update_data: Dict[str, Any]) -> bool:
        """更新Feed同步状态 - 改进版本
        
        Args:
            feed_id: Feed ID
            update_data: 更新数据，支持特殊操作：
                - consecutive_failures_increment: 增加连续失败次数
                - total_sync_success: 增加成功次数
                - total_sync_failures: 增加失败次数
            
        Returns:
            是否成功
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                return False
            
            # 处理特殊操作
            if "consecutive_failures_increment" in update_data:
                increment = update_data.pop("consecutive_failures_increment")
                feed.consecutive_failures = (feed.consecutive_failures or 0) + increment
            
            if "total_sync_success" in update_data:
                increment = update_data.pop("total_sync_success")
                # 检查字段是否存在
                if hasattr(feed, 'total_sync_success_count'):
                    feed.total_sync_success_count = (feed.total_sync_success_count or 0) + increment
            
            if "total_sync_failures" in update_data:
                increment = update_data.pop("total_sync_failures")
                # 检查字段是否存在
                if hasattr(feed, 'total_sync_failure_count'):
                    feed.total_sync_failure_count = (feed.total_sync_failure_count or 0) + increment
            
            # 更新其他字段
            for key, value in update_data.items():
                if hasattr(feed, key):
                    setattr(feed, key, value)
            
            # 更新健康状态（如果有相关方法）
            if hasattr(feed, 'update_health_status'):
                feed.update_health_status()
            
            # 检查是否需要自动关闭
            if feed.consecutive_failures >= 20:
                feed.is_active = False
                if hasattr(feed, 'disabled_at'):
                    feed.disabled_at = datetime.now()
                if hasattr(feed, 'disabled_reason'):
                    feed.disabled_reason = f"连续失败{feed.consecutive_failures}次自动关闭"
                if hasattr(feed, 'auto_disabled'):
                    feed.auto_disabled = True
                if hasattr(feed, 'health_status'):
                    feed.health_status = "disabled"
            
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"更新Feed同步状态失败: {str(e)}")
            self.db.rollback()
            return False

    def count_feeds_near_disable(self, threshold: int = 15) -> int:
        """统计接近被关闭的Feed数量（连续失败次数接近阈值）"""
        try:
            return self.db.query(RssFeed).filter(
                RssFeed.is_active == True,
                RssFeed.consecutive_failures >= threshold,
                RssFeed.consecutive_failures < 20
            ).count()
        except Exception as e:
            logger.error(f"统计接近关闭的Feed数量失败: {str(e)}")
            return 0

    def count_recently_disabled_feeds(self, hours: int = 24) -> int:
        """统计最近被关闭的Feed数量"""
        try:
            since_time = datetime.now() - timedelta(hours=hours)
            # 检查字段是否存在
            if hasattr(RssFeed, 'disabled_at'):
                return self.db.query(RssFeed).filter(
                    RssFeed.is_active == False,
                    RssFeed.disabled_at >= since_time
                ).count()
            else:
                # 如果没有 disabled_at 字段，返回0
                return 0
        except Exception as e:
            logger.error(f"统计最近被关闭的Feed数量失败: {str(e)}")
            return 0

    def count_high_failure_feeds(self, min_failures: int = 10) -> int:
        """统计高失败率的Feed数量"""
        try:
            return self.db.query(RssFeed).filter(
                RssFeed.is_active == True,
                RssFeed.consecutive_failures >= min_failures
            ).count()
        except Exception as e:
            logger.error(f"统计高失败率Feed数量失败: {str(e)}")
            return 0

    def reset_feed_failures(self, feed_id: str, reactivate: bool = False) -> Dict[str, Any]:
        """重置特定Feed的失败计数
        
        Args:
            feed_id: Feed ID
            reactivate: 是否重新激活Feed
            
        Returns:
            重置结果
        """
        try:
            feed = self.db.query(RssFeed).filter(RssFeed.id == feed_id).first()
            if not feed:
                raise Exception(f"未找到Feed: {feed_id}")
            
            old_failures = feed.consecutive_failures
            was_active = feed.is_active
            
            # 重置失败计数
            feed.consecutive_failures = 0
            if hasattr(feed, 'last_sync_error'):
                feed.last_sync_error = None
            if hasattr(feed, 'error_type'):
                feed.error_type = None
            
            # 如果需要重新激活
            if reactivate and not feed.is_active:
                feed.is_active = True
                if hasattr(feed, 'disabled_at'):
                    feed.disabled_at = None
                if hasattr(feed, 'disabled_reason'):
                    feed.disabled_reason = None
                if hasattr(feed, 'auto_disabled'):
                    feed.auto_disabled = False
            
            self.db.commit()
            
            return {
                "feed_id": feed_id,
                "old_failures": old_failures,
                "new_failures": 0,
                "was_active": was_active,
                "is_active": feed.is_active,
                "reactivated": reactivate and not was_active
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"重置Feed失败计数失败: {str(e)}")
            raise

    def reset_all_feed_failures(self, reactivate: bool = False) -> Dict[str, Any]:
        """重置所有Feed的失败计数
        
        Args:
            reactivate: 是否重新激活被关闭的Feed
            
        Returns:
            重置结果
        """
        try:
            # 统计重置前的数据
            total_feeds = self.db.query(RssFeed).count()
            high_failure_feeds = self.db.query(RssFeed).filter(
                RssFeed.consecutive_failures > 0
            ).count()
            disabled_feeds = self.db.query(RssFeed).filter(
                RssFeed.is_active == False
            ).count()
            
            # 重置所有Feed的失败计数
            update_data = {RssFeed.consecutive_failures: 0}
            if hasattr(RssFeed, 'last_sync_error'):
                update_data[RssFeed.last_sync_error] = None
            if hasattr(RssFeed, 'error_type'):
                update_data[RssFeed.error_type] = None
                
            self.db.query(RssFeed).update(update_data)
            
            reactivated_count = 0
            if reactivate:
                # 重新激活所有被关闭的Feed
                reactivate_data = {RssFeed.is_active: True}
                if hasattr(RssFeed, 'disabled_at'):
                    reactivate_data[RssFeed.disabled_at] = None
                if hasattr(RssFeed, 'disabled_reason'):
                    reactivate_data[RssFeed.disabled_reason] = None
                if hasattr(RssFeed, 'auto_disabled'):
                    reactivate_data[RssFeed.auto_disabled] = False
                    
                result = self.db.query(RssFeed).filter(
                    RssFeed.is_active == False
                ).update(reactivate_data)
                reactivated_count = result
            
            self.db.commit()
            
            return {
                "total_feeds": total_feeds,
                "reset_failure_count": high_failure_feeds,
                "disabled_feeds": disabled_feeds,
                "reactivated_count": reactivated_count,
                "operation_time": datetime.now().isoformat()
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"重置所有Feed失败计数失败: {str(e)}")
            raise

    def _calculate_sync_priority_improved(self, feed) -> int:
        """计算Feed同步优先级（数字越小优先级越高） - 改进版本
        
        主要考虑因素：
        1. 连续失败次数（失败少的优先级高）
        2. 最后同步时间（久未同步的优先级高）
        3. 是否从未同步过（最高优先级）
        
        Args:
            feed: Feed对象
            
        Returns:
            优先级数字（0-100，越小优先级越高）
        """
        base_priority = 0
        
        # 从未同步过，最高优先级
        if not feed.last_sync_at:
            return 0
        
        # 连续失败次数影响优先级
        failure_penalty = min(feed.consecutive_failures * 2, 40)  # 最多40分扣除
        base_priority += failure_penalty
        
        # 最后同步时间影响优先级
        hours_since_sync = (datetime.now() - feed.last_sync_at).total_seconds() / 3600
        if hours_since_sync > 24:
            base_priority += 5  # 超过24小时，加5分
        elif hours_since_sync > 12:
            base_priority += 10  # 超过12小时，加10分
        elif hours_since_sync > 6:
            base_priority += 15  # 超过6小时，加15分
        elif hours_since_sync > 1:
            base_priority += 20  # 超过1小时，加20分
        else:
            base_priority += 30  # 1小时内，加30分（低优先级）
        
        return min(base_priority, 100)  # 最大不超过100

    def _estimate_next_sync_time(self, feed, success_interval_minutes: int) -> Optional[str]:
        """估算下次同步时间
        
        Args:
            feed: Feed对象
            success_interval_minutes: 成功间隔分钟数
            
        Returns:
            估算的下次同步时间（ISO格式字符串）
        """
        # 检查字段是否存在
        last_success_time = None
        if hasattr(feed, 'last_successful_sync_at') and feed.last_successful_sync_at:
            last_success_time = feed.last_successful_sync_at
        elif hasattr(feed, 'last_successful_fetch_at') and feed.last_successful_fetch_at:
            last_success_time = feed.last_successful_fetch_at
        
        if not last_success_time:
            return "立即可同步"
        
        next_sync = last_success_time + timedelta(minutes=success_interval_minutes)
        
        if next_sync <= datetime.now():
            return "立即可同步"
        else:
            return next_sync.isoformat()

    def _feed_to_dict(self, feed: RssFeed) -> Dict[str, Any]:
        """将Feed对象转换为字典
        
        Args:
            feed: Feed对象
            
        Returns:
            Feed字典
        """
        return {
            "id": feed.id,
            "url": feed.url,
            "category_id": feed.category_id,
            "logo": feed.logo,
            "title": feed.title,
            "description": feed.description,
            "is_active": feed.is_active,
            "last_fetch_at": feed.last_fetch_at.isoformat() if feed.last_fetch_at else None,
            "last_fetch_status": feed.last_fetch_status,
            "last_fetch_error": feed.last_fetch_error,
            "last_successful_fetch_at": feed.last_successful_fetch_at.isoformat() if feed.last_successful_fetch_at else None,
            "total_articles_count": feed.total_articles_count,
            "consecutive_failures": feed.consecutive_failures,
            # 抓取控制
            "crawl_with_js": feed.crawl_with_js,
            "crawl_delay": feed.crawl_delay,
            "custom_headers": feed.custom_headers,
            # 代理配置
            "use_proxy": feed.use_proxy,
      
    }