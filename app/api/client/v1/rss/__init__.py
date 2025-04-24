from flask import Blueprint

feed_bp = Blueprint("feed_bp", __name__)
article_bp = Blueprint("article_bp", __name__)

# 导入视图函数
from app.api.client.v1.rss.feed import *
from app.api.client.v1.rss.article import *

rss_bp = Blueprint("rss_bp", __name__)
# 注册各个子模块蓝图
rss_bp.register_blueprint(feed_bp, url_prefix="/feed")
rss_bp.register_blueprint(article_bp, url_prefix="/article")