"""Swagger工具函数"""
from functools import wraps
from flasgger import swag_from
import os
import yaml

def document_api(yaml_path, path=None):
    """API文档装饰器
    
    Args:
        yaml_path: YAML文件路径，相对于docs/swagger目录
        path: 具体的API路径（例如 '/register'），用于从YAML文件中提取对应文档
        
    Returns:
        装饰器函数
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            return f(*args, **kwargs)
        
        # 检查路径
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        full_path = os.path.join(base_dir, 'docs', 'swagger', yaml_path)
        
        if os.path.exists(full_path):
            # 加载 YAML 文件
            with open(full_path, 'r', encoding='utf-8') as file:
                swagger_doc = yaml.safe_load(file)
            
            # 如果提供了 path 参数，提取对应路径的文档
            if path and 'paths' in swagger_doc and path in swagger_doc['paths']:
                endpoint_doc = swagger_doc['paths'][path]
                print(f"Swagger doc for {path}: {endpoint_doc}")
                # 将提取的文档与函数关联
                wrapped.__doc__ = f.__doc__
                # 使用 swag_from 的 specs_dict 参数动态注入文档
                return swag_from(endpoint_doc)(wrapped)
            else:
                # 如果没有提供 path 或路径不存在，仅保留函数文档
                wrapped.__doc__ = f.__doc__
                return wrapped
        else:
            # 如果文件不存在，仅添加文档字符串
            wrapped.__doc__ = f.__doc__
            return wrapped
    
    return decorator