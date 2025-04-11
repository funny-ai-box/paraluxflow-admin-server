"""数据库配置模块，用于从环境变量获取数据库连接信息"""
import os

def get_database_url():
    """从环境变量获取数据库URL"""
    # 直接使用提供的数据库URL
    if "SQLALCHEMY_DATABASE_URI" in os.environ:
        return os.environ["SQLALCHEMY_DATABASE_URI"]
    
    # 使用特定的Zeabur数据库配置
    # 公共访问
    PUBLIC_HOST = "sfo1.clusters.zeabur.com"
    PUBLIC_PORT = "30465"
    
    # 内部访问
    INTERNAL_HOST = "mysql.zeabur.internal"
    INTERNAL_PORT = "3306"
    
    # 优先使用内部连接（更安全更快）
    host = INTERNAL_HOST
    port = INTERNAL_PORT
    
    # 从环境变量获取用户名、密码和数据库名
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "")
    database = os.environ.get("MYSQL_DATABASE", "paraluxflow")
    
    # 不需要URL编码，Zeabur处理好了环境变量
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

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