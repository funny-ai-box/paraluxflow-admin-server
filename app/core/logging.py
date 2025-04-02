"""日志配置模块"""
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request

def setup_logging(app: Flask):
    """设置应用日志

    参数:
        app: Flask应用实例
    """
    # 获取日志级别
    log_level_name = app.config.get('LOG_LEVEL', 'INFO')
    log_level = getattr(logging, log_level_name)
    
    # 创建日志格式
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    
    
    # 确保日志目录存在
    log_dir = os.path.join(app.root_path, '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 配置文件处理器
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'imp.log'),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # 配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # 添加处理器到应用
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
    
    # 设置第三方库的日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
    
    # 请求日志中间件
    @app.before_request
    def log_request_info():
        app.logger.debug('Request: %s %s', request.method, request.path)
    
    @app.after_request
    def log_response_info(response):
        app.logger.debug('Response: %s %s %s', request.method, request.path, response.status)
        return response
    
    app.logger.info('Logging setup completed')