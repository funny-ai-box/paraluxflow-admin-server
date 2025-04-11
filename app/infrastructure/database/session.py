"""数据库会话管理"""
from flask import current_app
from flask.globals import g, app_ctx
from app.extensions import db

def get_db_session():
    """获取数据库会话

    返回:
        SQLAlchemy会话对象
    """
    # 检查是否已有激活的应用上下文
    try:
        # 直接使用 g 对象
        if hasattr(g, 'db_session'):
            return g.db_session
        
        # 创建一个新的会话并存储在 g 对象中
        g.db_session = db.session
        return g.db_session
    except RuntimeError:
        # 如果没有应用上下文，创建一个临时会话
        return db.create_scoped_session(options={"expire_on_commit": False})

def close_db_session(exception=None):
    """关闭数据库会话"""
    if hasattr(g, 'db_session'):
        g.db_session.close()