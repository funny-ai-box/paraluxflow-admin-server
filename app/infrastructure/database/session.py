"""数据库会话管理"""
from flask import current_app
from flask.globals import g, app_ctx
from app.extensions import db
from flask_sqlalchemy import SQLAlchemy
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

class ExtendedSQLAlchemy(SQLAlchemy):
    def create_session(self, options=None):
        """创建一个独立的SQLAlchemy会话，适用于后台线程
        
        Args:
            options: 会话选项
            
        Returns:
            SQLAlchemy会话实例
        """
        if options is None:
            options = {}
            
        # 使用引擎创建一个新的会话
        return self.create_engine().connect().session_factory(**options)

# 如果已经创建了db实例，可以通过猴子补丁添加方法
if not hasattr(SQLAlchemy, 'create_session'):
    SQLAlchemy.create_session = ExtendedSQLAlchemy.create_session

# 创建数据库实例
# 注意：如果代码中已经有这一行，请确保替换为这个扩展版本
db = SQLAlchemy()