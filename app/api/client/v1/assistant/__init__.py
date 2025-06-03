# app/api/client/v1/assistant/__init__.py
from flask import Blueprint

# 创建各个子模块蓝图
assistant_article_bp = Blueprint("assistant_article_bp", __name__)
assistant_general_bp = Blueprint("assistant_general_bp", __name__)

# 导入视图函数
from app.api.client.v1.assistant.article import *
from app.api.client.v1.assistant.general import *

# 创建主蓝图并注册子模块
assistant_bp = Blueprint("assistant_bp", __name__)

# 注册子模块蓝图
assistant_bp.register_blueprint(assistant_article_bp, url_prefix="/article")
assistant_bp.register_blueprint(assistant_general_bp, url_prefix="/general")