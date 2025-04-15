from flask import Blueprint

feed_bp = Blueprint("feed_bp", __name__)
article_bp = Blueprint("article_bp", __name__)

# 导入视图函数
from app.api.client.v1.rss.feed import *
from app.api.client.v1.rss.article import *