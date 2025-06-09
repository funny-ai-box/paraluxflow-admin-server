from flask import Blueprint

# 创建RSS主蓝图
rss_bp = Blueprint("rss", __name__)

# 导入各个子模块蓝图
from app.api.admin.v1.rss.feed import feed_bp
from app.api.admin.v1.rss.article import article_bp
from app.api.admin.v1.rss.script import script_bp
from app.api.admin.v1.rss.crawler import crawler_bp

from app.api.admin.v1.rss.sync import sync_bp
from app.api.admin.v1.rss.vectorization import vectorization_bp

# 注册各个子模块蓝图
rss_bp.register_blueprint(feed_bp, url_prefix="/feed")
rss_bp.register_blueprint(article_bp, url_prefix="/article")
rss_bp.register_blueprint(script_bp, url_prefix="/script")
rss_bp.register_blueprint(crawler_bp, url_prefix="/crawler")

rss_bp.register_blueprint(sync_bp, url_prefix="/sync")
rss_bp.register_blueprint(vectorization_bp, url_prefix="/vectorization")