"""数据库初始化模块"""
from app.extensions import db

def init_db(app):
    """初始化数据库表结构(不使用迁移)
    
    Args:
        app: Flask应用实例
    """
    with app.app_context():
        # 创建所有表
        db.create_all()
        
        # 可以在这里添加初始数据
        print("数据库表已创建成功")
        
        # 提交事务
        db.session.commit()