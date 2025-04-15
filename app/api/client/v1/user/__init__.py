from flask import Blueprint

profile_bp = Blueprint("profile_bp", __name__)

# 导入视图函数
from app.api.client.v1.user.profile import *