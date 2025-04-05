"""Swagger工具函数"""
from functools import wraps
from flasgger import swag_from
import os

def document_api(yaml_path):
    """API文档装饰器
    
    Args:
        yaml_path: YAML文件路径，相对于docs/swagger目录
        
    Returns:
        装饰器函数
    """
    def decorator(f):
        # 检查是否存在docs/swagger目录
        if not os.path.exists("docs/swagger"):
            # 如果不存在，则直接返回原函数
            return f
        
        # 构建完整路径
        full_path = os.path.join("docs/swagger", yaml_path)
        
        # 检查文件是否存在
        if not os.path.exists(full_path):
            # 如果不存在，则直接返回原函数
            return f
        
        # 应用swagger装饰器
        return swag_from(full_path)(f)
    
    return decorator
