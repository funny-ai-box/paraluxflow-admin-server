import os
from flask import Flask
from app.extensions import db, migrate, cors, jwt
from app.config import AppConfig as Config
from app.utils.rsa_util import init_rsa_keys
from flasgger import Swagger
import logging

logger = logging.getLogger(__name__)

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
    from app.api.admin.v1 import api_admin_v1_bp
    app.register_blueprint(api_admin_v1_bp, url_prefix='/api/admin/v1')
    
    from app.api.client.v1 import api_client_v1_bp
    app.register_blueprint(api_client_v1_bp, url_prefix='/api/client/v1')

    from app.api.jobs import jobs_bp
    app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
    return None

def register_errorhandlers(app):
    """注册错误处理器"""
    from app.api.middleware.error_handling import handle_exception
    app.register_error_handler(Exception, handle_exception)
    return None
def register_commands(app):
    """注册命令行命令"""
    # 在这里添加自定义Flask命令
    from app.commands.init_hot_topic_platforms import register_commands as register_hot_platform_commands
    register_hot_platform_commands(app)