# 在 app/utils/swagger_helper.py 创建这个文件

import os
from flask import current_app
from flasgger import swag_from

def get_swagger_path(yaml_filename):
    """
    获取Swagger YAML文件的完整路径
    
    Args:
        yaml_filename: YAML文件名，如 'crawler.yml'
    
    Returns:
        str: YAML文件的完整路径
    """
    base_dir = os.getcwd()

    swagger_dir = os.path.join(base_dir, 'docs', 'swagger')


    return os.path.join(swagger_dir, yaml_filename)

def api_doc(yaml_filename):

    return swag_from(get_swagger_path(yaml_filename))