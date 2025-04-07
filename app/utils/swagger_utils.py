"""Swagger工具函数"""
from functools import wraps
from flasgger import swag_from
import os
import yaml
import logging

logger = logging.getLogger(__name__)

def document_api(yaml_path, path=None):
    """API文档装饰器
    
    Args:
        yaml_path: YAML文件路径，相对于docs/swagger目录
        path: 具体的API路径（例如 '/logs'），用于从YAML文件中提取对应文档
        
    Returns:
        装饰器函数
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
            
        # 检查路径
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        full_path = os.path.join(base_dir, 'docs', 'swagger', yaml_path)
        
        if os.path.exists(full_path):
            try:
                # 读取YAML文件
                with open(full_path, 'r', encoding='utf-8') as file:
                    swagger_doc = yaml.safe_load(file)
                
                # 如果指定了路径，只使用该路径的API文档
                if path:
                    # 创建一个新的规范副本，保留所有必要的元数据
                    specs = {
                        'openapi': swagger_doc.get('openapi', '3.0.0'),
                        'info': swagger_doc.get('info', {}),
                        'paths': {}
                    }
                    
                    # 复制标签和其他顶级元素
                    for key in ['tags', 'components', 'security', 'servers']:
                        if key in swagger_doc:
                            specs[key] = swagger_doc[key]
                    
                    # 查找路径
                    path_found = False
                    
                    # 1. 尝试直接匹配路径（路径不带前缀）
                    if 'paths' in swagger_doc and path in swagger_doc['paths']:
                        specs['paths'][path] = swagger_doc['paths'][path]
                        path_found = True
                        logger.debug(f"找到直接路径: {path}")
                    
                    # 2. 尝试查找完整路径（带前缀的路径）
                    if not path_found and 'paths' in swagger_doc:
                        # 获取蓝图前缀
                        blueprint_obj = None
                        for var_name, var_value in f.__globals__.items():
                            if var_name.endswith('_bp') and hasattr(var_value, 'url_prefix') and var_value.url_prefix:
                                blueprint_obj = var_value
                                break
                        
                        # 构建可能的前缀
                        prefix = ''
                        if blueprint_obj and blueprint_obj.url_prefix:
                            prefix = blueprint_obj.url_prefix
                        
                        # 构建完整路径（带前缀）
                        full_path_key = f"{prefix}{path}"
                        
                        # 检查是否存在完整路径
                        if full_path_key in swagger_doc['paths']:
                            specs['paths'][path] = swagger_doc['paths'][full_path_key]
                            path_found = True
                            logger.debug(f"找到完整路径: {full_path_key}")
                        # 检查是否存在修改后的完整路径
                        elif full_path_key.rstrip('/') in swagger_doc['paths']:
                            specs['paths'][path] = swagger_doc['paths'][full_path_key.rstrip('/')]
                            path_found = True
                            logger.debug(f"找到修改后的完整路径: {full_path_key.rstrip('/')}")
                        # 检查是否存在带前缀但不带前导斜杠的路径
                        elif prefix.lstrip('/') + path.lstrip('/') in swagger_doc['paths']:
                            modified_path = prefix.lstrip('/') + path.lstrip('/')
                            specs['paths'][path] = swagger_doc['paths'][modified_path]
                            path_found = True
                            logger.debug(f"找到不带前导斜杠的路径: {modified_path}")
                    
                    # 3. 尝试匹配任何以路径结尾的键
                    if not path_found and 'paths' in swagger_doc:
                        for doc_path in swagger_doc['paths']:
                            if doc_path.endswith(path):
                                specs['paths'][path] = swagger_doc['paths'][doc_path]
                                path_found = True
                                logger.debug(f"找到以路径结尾的键: {doc_path}")
                                break
                    
                    # 打印调试信息
                    if not path_found:
                        available_paths = list(swagger_doc['paths'].keys()) if 'paths' in swagger_doc else []
                        logger.warning(f"在文件'{yaml_path}'中未找到路径'{path}'")
                        logger.warning(f"可用路径: {available_paths}")
                    
                    if path_found:
                        # 应用swagger装饰器
                        decorated_function = swag_from(specs)(decorated_function)
                    else:
                        # 如果找不到特定路径，使用整个文档
                        logger.warning(f"将使用整个文档文件: {yaml_path}")
                        decorated_function = swag_from(full_path)(decorated_function)
                else:
                    # 使用整个YAML文件
                    decorated_function = swag_from(full_path)(decorated_function)
            except Exception as e:
                import traceback
                logger.error(f"加载Swagger文档时出错: {str(e)}")
                logger.error(traceback.format_exc())
        else:
            logger.warning(f"Swagger文档文件'{full_path}'不存在")
        
        return decorated_function
    
    return decorator