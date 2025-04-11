"""数据库配置模块，用于从环境变量获取数据库连接信息"""
import os
from urllib.parse import quote_plus

def get_database_url():
    """从环境变量获取数据库URL"""
    # 直接使用提供的数据库URL
    if "SQLALCHEMY_DATABASE_URI" in os.environ:
        return os.environ["SQLALCHEMY_DATABASE_URI"]
    
    # 从Zeabur的MySQL服务获取连接参数
    if "MYSQL_HOST" in os.environ:
        host = os.environ.get("MYSQL_HOST", "localhost")
        port = os.environ.get("MYSQL_PORT", "3306")
        user = os.environ.get("MYSQL_USER", "root")
        password = os.environ.get("MYSQL_PASSWORD", "")
        database = os.environ.get("MYSQL_DATABASE", "paraluxflow")
        
        # 对密码进行URL编码
        encoded_password = quote_plus(password)
        
        return f"mysql+pymysql://{user}:{encoded_password}@{host}:{port}/{database}"
    
    # 使用SQLite作为降级选项
    return "sqlite:///instance/imp.db"

def get_redis_url():
    """从环境变量获取Redis URL"""
    # 直接使用提供的Redis URL
    if "REDIS_URL" in os.environ:
        return os.environ["REDIS_URL"]
    
    # 从Zeabur的Redis服务获取连接参数
    if "REDIS_HOST" in os.environ:
        host = os.environ.get("REDIS_HOST", "localhost")
        port = os.environ.get("REDIS_PORT", "6379")
        password = os.environ.get("REDIS_PASSWORD", "")
        db = os.environ.get("REDIS_DB", "0")
        
        # 构建Redis URL
        if password:
            return f"redis://:{password}@{host}:{port}/{db}"
        else:
            return f"redis://{host}:{port}/{db}"
    
    # 默认Redis URL
    return "redis://localhost:6379/0"