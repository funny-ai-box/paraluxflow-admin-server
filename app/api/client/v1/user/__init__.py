# app/api/client/v1/user/__init__.py (更新版本)
from flask import Blueprint

# 用户资料蓝图
profile_bp = Blueprint("profile_bp", __name__)

# 用户偏好设置蓝图  
preferences_bp = Blueprint("preferences_bp", __name__)

# 导入视图函数
from app.api.client.v1.user.profile import *
from app.api.client.v1.user.preferences import *

# 创建用户主蓝图
user_bp = Blueprint("user_bp", __name__)

# 注册子蓝图
user_bp.register_blueprint(profile_bp,url_prefix="profile")  # profile 路由直接在 /user 下
user_bp.register_blueprint(preferences_bp,url_prefix="preferences")  # preferences 路由直接在 /user 下

