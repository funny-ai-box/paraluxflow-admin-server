# app/api/jobs/__init__.py
from flask import Blueprint

# 创建任务调度主蓝图
jobs_bp = Blueprint("jobs", __name__)

# 导入子模块蓝图
from app.api.jobs.rss import rss_jobs_bp
from app.api.jobs.crawler import crawler_jobs_bp
from app.api.jobs.hot_topics import hot_topics_jobs_bp
from app.api.jobs.vectorization import vectorization_jobs_bp
from app.api.jobs.feed_sync import feed_sync_jobs_bp



# 注册子模块蓝图
jobs_bp.register_blueprint(rss_jobs_bp, url_prefix="/rss")
jobs_bp.register_blueprint(crawler_jobs_bp, url_prefix="/crawler")
jobs_bp.register_blueprint(hot_topics_jobs_bp, url_prefix="/hot_topics")
jobs_bp.register_blueprint(feed_sync_jobs_bp,url_prefix='/feed_sync')
jobs_bp.register_blueprint(vectorization_jobs_bp, url_prefix="/vectorization")