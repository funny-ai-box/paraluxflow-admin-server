# app/api/client/v1/__init__.py
from flask import Blueprint

# 创建API v1客户端主蓝图
api_client_v1_bp = Blueprint("api_client_v1", __name__)

# 导入认证相关蓝图
from app.api.client.v1.auth.auth import auth_bp
# 导入RSS相关蓝图
from app.api.client.v1.rss.feed import feed_bp
from app.api.client.v1.rss.article import article_bp
# 导入用户相关蓝图
from app.api.client.v1.user.profile import profile_bp
# 导入订阅相关蓝图
from app.api.client.v1.subscription.subscription import subscription_bp
# 导入热点话题蓝图
from app.api.client.v1.hot_topics.hot_topics import client_hot_topics_bp

# 注册认证蓝图
api_client_v1_bp.register_blueprint(auth_bp, url_prefix="/auth")

# 注册RSS蓝图
api_client_v1_bp.register_blueprint(feed_bp, url_prefix="/feed")
api_client_v1_bp.register_blueprint(article_bp, url_prefix="/article")

# 注册用户蓝图
api_client_v1_bp.register_blueprint(profile_bp, url_prefix="/user")

# 注册订阅蓝图
api_client_v1_bp.register_blueprint(subscription_bp, url_prefix="/subscription")

# 注册热点话题蓝图
api_client_v1_bp.register_blueprint(client_hot_topics_bp, url_prefix="/hot_topics")