import os
from flask import Flask
from app.extensions import db, migrate, cors, jwt
from app.config import AppConfig as Config
from app.utils.rsa_util import init_rsa_keys
from flasgger import Swagger

def create_app(config_class=Config):
    """创建Flask应用实例"""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.config.from_pyfile('config.py', silent=True)

    # 初始化扩展
    register_extensions(app)
    
    # 初始化RSA密钥
    init_rsa_keys(app)
    
    # 注册蓝图
    register_blueprints(app)
    
    # 注册错误处理
    register_errorhandlers(app)
    
    # 注册命令
    register_commands(app)
    
    # 初始化Swagger

    base_dir = os.getcwd()
    swagger_dir = os.path.join(base_dir, 'docs', 'swagger')
    print(f"Swagger directory: {swagger_dir}")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"当前文件: {__file__}")
    
    # 确保swagger目录存在
    os.makedirs(swagger_dir, exist_ok=True)
    
    app.config['SWAGGER'] = {
        'title': 'IMP API',
        'description': 'Intelligent Middleware Platform API Documentation',
        'version': '1.0.0',
        'uiversion': 3,
        'doc_dir': swagger_dir,
        'termsOfService': '',
        'hide_top_bar': False,
        'openapi': '3.0.0',
        'specs': [
            {
                'endpoint': 'apispec',
                'route': '/apispec.json',
                'rule_filter': lambda rule: True,  # 所有接口
                'model_filter': lambda tag: True,  # 所有模型
            }
        ],
        'specs_route': '/api/docs/'
    }
    Swagger(app)
    

    return app

def register_extensions(app):
    """注册Flask扩展"""
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app)
    jwt.init_app(app)
    return None

def register_blueprints(app):
    """注册蓝图"""
    from app.api.v1 import api_v1_bp
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')
    return None

def register_errorhandlers(app):
    """注册错误处理器"""
    from app.api.middleware.error_handling import handle_exception
    app.register_error_handler(Exception, handle_exception)
    return None

def register_commands(app):
    """注册命令行命令"""
    # 在这里添加自定义Flask命令
    pass