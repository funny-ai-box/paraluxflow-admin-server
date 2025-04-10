# app/domains/rss/services/feed_service.py
"""RSS Feed服务实现"""
import os
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse

from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

class FeedService:
    """Feed管理服务，处理RSS Feed的增删改查"""
    
    def __init__(self, feed_repo, category_repo):
        """初始化Feed服务
        
        Args:
            feed_repo: Feed仓库
            category_repo: 分类仓库
        """
        self.feed_repo = feed_repo
        self.category_repo = category_repo
    
    def get_feeds(self, page: int = 1, per_page: int = 20, filters: Dict = None) -> Dict[str, Any]:
        """获取Feed列表
        
        Args:
            page: 页码
            per_page: 每页数量
            filters: 筛选条件
            
        Returns:
            Feed列表及分页信息
        """
        # 获取分页Feed列表
        result = self.feed_repo.get_filtered_feeds(filters, page, per_page)
        
        # 获取所有分类
        all_categories = self.category_repo.get_all_categories()
        
        # 关联数据
        for feed in result["list"]:
            # 关联分类
            category = next(
                (cat for cat in all_categories if cat["id"] == feed["category_id"]), None
            )
            feed["category"] = category
        
        return result
    
    def get_feed(self, feed_id: str) -> Dict[str, Any]:
        """获取Feed详情
        
        Args:
            feed_id: Feed ID
            
        Returns:
            Feed详情
            
        Raises:
            Exception: 获取失败时抛出异常
        """
        err, feed = self.feed_repo.get_feed_by_id(feed_id)
        if err:
            raise Exception(f"获取Feed信息失败: {err}")
        
        return feed
    
    def add_feed(self, feed_data: Dict[str, Any]) -> Dict[str, Any]:
        """添加新Feed
        
        Args:
            feed_data: Feed数据
                    
        Returns:
            新增的Feed详情
                    
        Raises:
            Exception: 添加失败时抛出异常
        """
        # 验证必填字段
        required_fields = ["title", "logo", "url", "category_id"]
        missing_fields = [field for field in required_fields if field not in feed_data]
        if missing_fields:
            raise Exception(f"缺少必填字段: {', '.join(missing_fields)}")
        
        # 处理自定义请求头
        if "custom_headers" in feed_data and isinstance(feed_data["custom_headers"], dict):
            import json
            feed_data["custom_headers"] = json.dumps(feed_data["custom_headers"])
        
        
        
        # 添加Feed
        err, result = self.feed_repo.add_feed(feed_data)
        if err:
            raise Exception(f"添加Feed失败: {err}")
        
        return result

    def update_feed(self, feed_id: str, feed_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新Feed
        
        Args:
            feed_id: Feed ID
            feed_data: 更新数据
            
        Returns:
            更新后的Feed详情
            
        Raises:
            Exception: 更新失败时抛出异常
        """
        # 获取当前Feed
        err, current_feed = self.feed_repo.get_feed_by_id(feed_id)
        if err:
            raise Exception(f"获取Feed信息失败: {err}")
        
        # 处理自定义请求头
        if "custom_headers" in feed_data and isinstance(feed_data["custom_headers"], dict):
            import json
            feed_data["custom_headers"] = json.dumps(feed_data["custom_headers"])
        
        
        
        # 更新Feed
        err, result = self.feed_repo.update_feed(feed_id, feed_data)
        if err:
            raise Exception(f"更新Feed失败: {err}")
        
        return result
    
    def set_feed_status(self, feed_id: str, is_active: bool) -> Dict[str, Any]:
        """设置Feed状态
        
        Args:
            feed_id: Feed ID
            is_active: 是否启用
            
        Returns:
            更新后的Feed详情
            
        Raises:
            Exception: 更新失败时抛出异常
        """
        # 更新状态
        err, result = self.feed_repo.update_feed_status(feed_id, is_active)
        if err:
            raise Exception(f"更新Feed状态失败: {err}")
        
        return result
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """获取所有Feed分类
        
        Returns:
            分类列表
        """
        return self.category_repo.get_all_categories()
    
    def handle_logo_upload(self, file, upload_folder: str = None) -> str:
        """处理Logo上传
        
        Args:
            file: 上传的文件对象
            upload_folder: 上传目录，默认为None (使用临时目录)
            
        Returns:
            文件URL
            
        Raises:
            Exception: 上传失败时抛出异常
        """
        # 检查文件扩展名
        allowed_extensions = {"png", "jpg", "jpeg"}
        filename = file.filename
        if not filename or "." not in filename:
            raise Exception("无效的文件名")
        
        ext = filename.rsplit(".", 1)[1].lower()
        if ext not in allowed_extensions:
            raise Exception(f"不支持的文件类型，只支持: {', '.join(allowed_extensions)}")
        
        # 生成安全的文件名
        secure_name = secure_filename(filename)
        unique_filename = f"{int(time.time())}_{secure_name}"
        
        # 使用临时目录
        if upload_folder is None:
            upload_folder = "/tmp"
        
        # 确保目录存在
        os.makedirs(upload_folder, exist_ok=True)
        
        # 保存文件
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        # 返回文件URL (实际应用中可能需要上传到对象存储)
        return f"/static/uploads/{unique_filename}"