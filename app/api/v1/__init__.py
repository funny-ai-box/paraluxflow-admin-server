# app/api/v1/__init__.py
from flask import Blueprint

# 创建API v1主蓝图
api_v1_bp = Blueprint("api_v1", __name__)

# 导入认证相关蓝图
from app.api.v1.auth.auth import auth_bp
# 导入Feed相关蓝图
from app.api.v1.rss.feed import feed_bp

# 注册认证蓝图
api_v1_bp.register_blueprint(auth_bp, url_prefix="/auth")
# 注册Feed蓝图
api_v1_bp.register_blueprint(feed_bp, url_prefix="/feed")