# app/domains/rss/services/script_service.py
"""爬取脚本服务实现"""
import ast
import re
import threading
import logging
from typing import Dict, Any, List, Optional, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class ScriptService:
    """爬取脚本管理服务，处理RSS爬取脚本的管理与测试"""
    
    def __init__(self, script_repo, feed_repo=None):
        """初始化脚本服务
        
        Args:
            script_repo: 脚本仓库
            feed_repo: Feed仓库(可选)
        """
        self.script_repo = script_repo
        self.feed_repo = feed_repo
    
    def get_scripts(self, feed_id: str) -> List[Dict[str, Any]]:
        """获取Feed的爬取脚本列表
        
        Args:
            feed_id: Feed ID
            
        Returns:
            脚本列表
            
        Raises:
            Exception: 获取失败时抛出异常
        """
        err, scripts = self.script_repo.get_feed_scripts(feed_id)
        if err:
            raise Exception(f"获取脚本列表失败: {err}")
        
        return scripts
    
    def get_script(self, script_id: int) -> Dict[str, Any]:
        """获取脚本详情
        
        Args:
            script_id: 脚本ID
            
        Returns:
            脚本详情
            
        Raises:
            Exception: 获取失败时抛出异常
        """
        err, script = self.script_repo.get_script_by_id(script_id)
        if err:
            raise Exception(f"获取脚本失败: {err}")
        
        return script
    
    def add_script(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
      """添加爬取脚本
      
      Args:
            script_data: 脚本数据
                  
      Returns:
            添加的脚本
                  
      Raises:
            Exception: 添加失败时抛出异常
      """
      # 验证必填字段
      if "feed_id" not in script_data or "script" not in script_data:
            raise Exception("缺少必填字段: feed_id, script")
      
      # 检查脚本语法
      try:
            ast.parse(script_data["script"])
      except SyntaxError as e:
            raise Exception(f"脚本语法错误: {str(e)}")
      
      # 处理版本信息
      description = script_data.get("description", f"脚本版本 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
      
      # 获取当前最高版本号
      feed_id = script_data["feed_id"]
      current_scripts = self.get_scripts(feed_id)
      version = 1  # 默认从版本1开始
      
      if current_scripts:
            # 找出最高版本号并加1
            max_version = max([s.get("version", 0) for s in current_scripts]) if current_scripts else 0
            version = max_version + 1
      
      # 添加脚本
      err, result = self.script_repo.create_script(
            feed_id=feed_id,
            script=script_data["script"],
            version=version,
            description=description,
            is_published=script_data.get("is_published", False)
      )
      
      if err:
            raise Exception(f"添加脚本失败: {err}")
      
      return result
    
    def update_script(self, script_id: int, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新爬取脚本
        
        Args:
            script_id: 脚本ID
            script_data: 更新数据
            
        Returns:
            更新后的脚本
            
        Raises:
            Exception: 更新失败时抛出异常
        """
        # 检查脚本语法
        if "script" in script_data:
            try:
                ast.parse(script_data["script"])
            except SyntaxError as e:
                raise Exception(f"脚本语法错误: {str(e)}")
        
        # 更新脚本
        err, result = self.script_repo.update_script(script_id, script_data)
        if err:
            raise Exception(f"更新脚本失败: {err}")
        
        return result
    
    def publish_script(self, feed_id: str) -> Dict[str, Any]:
        """发布脚本
        
        Args:
            feed_id: Feed ID
            
        Returns:
            发布结果
            
        Raises:
            Exception: 发布失败时抛出异常
        """
        err, result = self.script_repo.publish_script(feed_id)
        if err:
            raise Exception(f"发布脚本失败: {err}")
        
        return result
    
    def test_script(self, script: str, html_content: str) -> Dict[str, Any]:
        """测试爬取脚本
        
        Args:
            script: 脚本内容
            html_content: HTML内容
            
        Returns:
            测试结果
            
        Raises:
            Exception: 测试失败时抛出异常
        """
        # 检查脚本语法
        try:
            ast.parse(script)
        except SyntaxError as e:
            raise Exception(f"脚本语法错误: {str(e)}")
        
        # 执行脚本
        result = self._execute_script(script, html_content)
        
        return result
    
    def _execute_script(self, script: str, html_content: str) -> Dict[str, Any]:
        """执行爬取脚本
        
        Args:
            script: 脚本内容
            html_content: HTML内容
            
        Returns:
            执行结果
            
        Raises:
            Exception: 执行失败时抛出异常
        """
        # 受限执行环境
        local_vars = {}
        allowed_builtins = {
            "print": print,
            "range": range,
            "len": len,
            "int": int,
            "str": str,
            "__import__": __import__,
        }
        global_vars = {
            "__builtins__": allowed_builtins,
            "BeautifulSoup": BeautifulSoup,
            "re": re,
        }
        
        # 执行代码
        try:
            exec(script, global_vars, local_vars)
        except Exception as e:
            raise Exception(f"执行脚本失败: {str(e)}")
        
        # 调用函数获取结果
        if "process_data" in local_vars:
            try:
                # 使用超时装饰器
                process_data_with_timeout = self._timeout(5)(local_vars["process_data"])
                
                html_content_result, text_content = process_data_with_timeout(html_content)
                
                return {
                    "html_content": str(html_content_result),
                    "text_content": str(text_content)
                }
            except Exception as e:
                raise Exception(f"执行process_data函数失败: {str(e)}")
        else:
            raise Exception("脚本中未找到process_data函数")
    
    def _timeout(self, limit):
        """函数执行超时装饰器
        
        Args:
            limit: 超时时间(秒)
            
        Returns:
            装饰器函数
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                res = [
                    Exception(f"函数 [{func.__name__}] 执行超时 [{limit} 秒]!")
                ]

                def new_func():
                    try:
                        res[0] = func(*args, **kwargs)
                    except Exception as e:
                        res[0] = e

                t = threading.Thread(target=new_func)
                t.daemon = True
                t.start()
                t.join(limit)
                if isinstance(res[0], BaseException):
                    raise res[0]
                return res[0]

            return wrapper
        return decorator