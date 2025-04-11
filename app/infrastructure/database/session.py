"""数据库会话管理"""
from flask import _app_ctx_stack, current_app
from flask.globals import app_ctx
from app.extensions import db

def get_db_session():
    """获取数据库会话

    返回:
        SQLAlchemy会话对象
    """
    # 检查是否已有激活的应用上下文
    if _app_ctx_stack.top is not None:
        # 在应用上下文中获取会话
        return db.session
    else:
        # 如果没有应用上下文，创建一个临时会话
        return db.create_scoped_session(options={"expire_on_commit": False})

def close_db_session(exception=None):
    """关闭数据库会话"""
    if hasattr(app_ctx, 'db_session'):
        app_ctx.db_session.close()