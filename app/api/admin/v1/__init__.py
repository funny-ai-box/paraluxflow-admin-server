# app/api/v1/__init__.py
from flask import Blueprint

# 创建API v1主蓝图
api_admin_v1_bp = Blueprint("api_v1", __name__)

# 导入认证相关蓝图
from app.api.admin.v1.auth.auth import auth_bp
# 导入RSS相关蓝图
from app.api.admin.v1.rss.feed import feed_bp
from app.api.admin.v1.rss.article import article_bp
from app.api.admin.v1.rss.script import script_bp
# 导入摘要相关蓝图
from app.api.admin.v1.digest.digest import digest_bp
# 导入LLM相关蓝图
from app.api.admin.v1.llm.llm import llm_bp

# 注册RSS蓝图组
from app.api.admin.v1.rss import rss_bp
api_admin_v1_bp.register_blueprint(rss_bp, url_prefix="/rss")

# 注册文章蓝图
api_admin_v1_bp.register_blueprint(article_bp, url_prefix="/article")

# 注册爬取脚本蓝图
api_admin_v1_bp.register_blueprint(script_bp, url_prefix="/script")

# 注册LLM蓝图
api_admin_v1_bp.register_blueprint(llm_bp, url_prefix="/llm")

# 注册认证蓝图
api_admin_v1_bp.register_blueprint(auth_bp, url_prefix="/auth")

# 注册摘要蓝图
api_admin_v1_bp.register_blueprint(digest_bp, url_prefix="/digest")