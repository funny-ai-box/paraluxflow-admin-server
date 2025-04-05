"""安装Swagger到Flask应用"""
import os
import sys

def add_swagger_to_app():
    """将Swagger添加到Flask应用"""
    # 检查app/__init__.py文件是否存在
    if not os.path.exists("app/__init__.py"):
        print("未找到app/__init__.py文件，请确保您在正确的项目根目录下运行此脚本")
        return False
    
    # 读取文件内容
    with open("app/__init__.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # 检查是否已经安装了Swagger
    if "flasgger" in content:
        print("已经安装了Swagger，无需重复安装")
        return True
    
    # 添加导入语句
    import_statement = "from flasgger import Swagger\n"
    if "from flask import Flask" in content:
        content = content.replace("from flask import Flask", "from flask import Flask\n" + import_statement)
    else:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "import" in line:
                lines.insert(i + 1, import_statement)
                content = "\n".join(lines)
                break
    
    # 添加Swagger初始化代码
    swagger_config = """
    # 初始化Swagger
    app.config['SWAGGER'] = {
        'title': 'IMP API',
        'description': 'Intelligent Middleware Platform API Documentation',
        'version': '1.0.0',
        'uiversion': 3,
        'doc_dir': './docs/swagger/',
        'termsOfService': '',
        'hide_top_bar': False,
        'specs': [
            {
                'endpoint': 'apispec',
                'route': '/apispec.json',
                'rule_filter': lambda rule: True,  # 所有接口
                'model_filter': lambda tag: True,  # 所有模型
            },
            {
                'endpoint': 'auth_apispec',
                'route': '/auth/apispec.json',
                'rule_filter': lambda rule: rule.endpoint.startswith('auth'),
                'model_filter': lambda tag: True,
            },
            {
                'endpoint': 'rss_apispec',
                'route': '/rss/apispec.json',
                'rule_filter': lambda rule: rule.endpoint.startswith('rss'),
                'model_filter': lambda tag: True,
            },
            {
                'endpoint': 'digest_apispec',
                'route': '/digest/apispec.json',
                'rule_filter': lambda rule: rule.endpoint.startswith('digest'),
                'model_filter': lambda tag: True,
            },
            {
                'endpoint': 'llm_apispec',
                'route': '/llm/apispec.json',
                'rule_filter': lambda rule: rule.endpoint.startswith('llm'),
                'model_filter': lambda tag: True,
            }
        ],
        'specs_route': '/api/docs/'
    }
    Swagger(app)
    """
    
    # 在return app前添加Swagger初始化代码
    if "return app" in content:
        content = content.replace("return app", swagger_config + "\n    return app")
    else:
        content += "\n" + swagger_config
    
    # 写回文件
    with open("app/__init__.py", "w", encoding="utf-8") as f:
        f.write(content)
    
    print("成功添加Swagger到Flask应用")
    return True

def create_api_wrapper():
    """创建API装饰器工具"""
    # 创建目录
    os.makedirs("app/utils", exist_ok=True)
    
    # 创建文件
    with open("app/utils/swagger_utils.py", "w", encoding="utf-8") as f:
        f.write('''"""Swagger工具函数"""
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
''')
    
    print("成功创建API装饰器工具")
    return True

def add_requirements():
    """添加依赖到项目"""
    # 检查pyproject.toml是否存在
    if os.path.exists("pyproject.toml"):
        with open("pyproject.toml", "r", encoding="utf-8") as f:
            content = f.read()
        
        if "flasgger" not in content:
            # 找到[tool.poetry.dependencies]部分并添加flasgger
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "[tool.poetry.dependencies]" in line:
                    lines.insert(i + 1, 'flasgger = "^0.9.5"')
                    break
            
            with open("pyproject.toml", "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            
            print("已将flasgger添加到pyproject.toml文件")
            print("请运行 'poetry install' 安装新依赖")
    else:
        print("未找到pyproject.toml文件")
        print("请手动添加flasgger依赖: pip install flasgger")

if __name__ == "__main__":
    print("开始安装Swagger到Flask应用...")
    if add_swagger_to_app():
        create_api_wrapper()
        add_requirements()
        print("\n安装完成！")
        print("请运行以下命令安装依赖:")
        print("  pip install flasgger")
        print("\n使用方法:")
        print("1. 在API函数上添加装饰器:")
        print("   from app.utils.swagger_utils import document_api")
        print("   @auth_bp.route('/login', methods=['POST'])")
        print("   @document_api('auth/login.yml')")
        print("   def login():")
        print("       # 实现代码")
        print("\n2. 访问API文档:")
        print("   http://your-domain/api/docs/")
    else:
        print("安装失败")
