# app/api/client/v1/auth/__init__.py
from flask import Blueprint

auth_bp = Blueprint("auth_bp", __name__)

# 导入视图函数
from app.api.client.v1.auth.auth import *