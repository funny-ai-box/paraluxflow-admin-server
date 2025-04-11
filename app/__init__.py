import os
from flask import Flask
from app.extensions import db, migrate, cors, jwt
from app.config import AppConfig as Config
from app.utils.rsa_util import init_rsa_keys
import logging

logger = logging.getLogger(__name__)

def create_app(config_class=Config):
    """创建Flask应用实例"""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.config.from_pyfile('config.py', silent=True)

    # 初始化扩展
    register_extensions(app)
    
    try:
        # 初始化RSA密钥
        init_rsa_keys(app)
    except Exception as e:
        app.logger.error(f"初始化RSA密钥失败: {str(e)}")
    
    try:
        # 注册蓝图
        register_blueprints(app)
    except Exception as e:
        app.logger.error(f"注册蓝图失败: {str(e)}")
    
    try:
        # 注册错误处理
        register_errorhandlers(app)
    except Exception as e:
        app.logger.error(f"注册错误处理器失败: {str(e)}")
    
    try:
        # 注册命令
        register_commands(app)
    except Exception as e:
        app.logger.error(f"注册命令失败: {str(e)}")
    

    
    @app.route('/health')
    def health_check():
        """健康检查路由"""
        return {'status': 'ok'}, 200
        
    return app

def register_extensions(app):
    """注册Flask扩展"""
    db.init_app(app)
    # 注释掉Migrate初始化，显式禁用迁移
    # migrate.init_app(app, db)
    cors.init_app(app)
    jwt.init_app(app)
    return None

def register_blueprints(app):
    """注册蓝图"""
    try:
        from app.api.v1 import api_v1_bp
        app.register_blueprint(api_v1_bp, url_prefix='/api/v1')
    except Exception as e:
        app.logger.error(f"注册API v1蓝图失败: {str(e)}")

    try:
        from app.api.jobs import jobs_bp
        app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
    except Exception as e:
        app.logger.error(f"注册Jobs蓝图失败: {str(e)}")
    
    return None

def register_errorhandlers(app):
    """注册错误处理器"""
    try:
        from app.api.middleware.error_handling import handle_exception
        app.register_error_handler(Exception, handle_exception)
    except Exception as e:
        app.logger.error(f"注册错误处理器失败: {str(e)}")
    return None

def register_commands(app):
    """注册命令行命令"""
    # 在这里添加自定义Flask命令
    try:
        from app.db_init import init_db
        
        @app.cli.command("init-db")
        def init_db_command():
            """初始化数据库表结构"""
            init_db(app)
            print("数据库初始化完成")
    except Exception as e:
        app.logger.error(f"注册数据库初始化命令失败: {str(e)}")
    
    pass