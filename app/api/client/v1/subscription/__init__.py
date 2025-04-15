# app/api/client/v1/subscription/__init__.py
from flask import Blueprint

subscription_bp = Blueprint("subscription_bp", __name__)

# 导入视图函数
from app.api.client.v1.subscription.subscription import *