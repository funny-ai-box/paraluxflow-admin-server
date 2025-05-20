"""应用配置"""
import os
from datetime import timedelta

class Config:
    """基础配置"""
    # Flask配置
    SECRET_KEY = "dev-secret-key"
    DEBUG = False
    TESTING = False
    SQLALCHEMY_ECHO = False
    
    # 数据库配置
    # SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI", "mysql+pymysql://root:UnDHt45VJd21akebR08fpqiT639AG7XF@mysql.zeabur.internal/paraluxflow")
    SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI", "mysql+pymysql://root:123456@127.0.0.1:3306/paraluxflow")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT配置
    JWT_SECRET_KEY = "jwt-secret-key"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # 文件上传配置
    UPLOAD_FOLDER = "uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # API超时配置
    API_TIMEOUT = 60
    
    # AI模型配置
    OPENAI_API_KEY = None
    ANTHROPIC_API_KEY = None
    
    # 向量数据库配置
    PINECONE_API_KEY = None
    PINECONE_ENVIRONMENT = None
    QDRANT_URL = "http://localhost:6333"
    
    # Redis配置
    REDIS_URL = "redis://localhost:6379/0"
    
    # 日志配置
    LOG_LEVEL = "INFO"
    
    # 密码加密相关配置
    PASSWORD_SALT = os.environ.get('PASSWORD_SALT', 'default-salt-change-in-production')
    
    # RSA配置
    RSA_KEY_SIZE = 2048
    RSA_PRIVATE_KEY = None  # 将在应用初始化时设置
    RSA_PUBLIC_KEY = None   # 将在应用初始化时设置

    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "your-client-id")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "your-client-secret")
    # Firebase配置
    FIREBASE_CONFIG = os.environ.get("FIREBASE_CONFIG_FILE",'firebase.json')  # 服务账号密钥文件路径
    FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY")     # Firebase Web API密钥
    FIREBASE_AUTH_DOMAIN = os.environ.get("FIREBASE_AUTH_DOMAIN")
    FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")
    FIREBASE_APP_ID = os.environ.get("FIREBASE_APP_ID")

    # 前端回调配置
    FRONTEND_CALLBACK_URL = os.environ.get("FRONTEND_CALLBACK_URL", "app://auth-callback")

    MILVUS_HOST = os.environ.get("MILVUS_HOST", "115.159.79.130")
    MILVUS_PORT = os.environ.get("MILVUS_PORT", "19530") 
    MILVUS_COLLECTION = os.environ.get("MILVUS_COLLECTION", "rss_articles")
    MILVUS_USER = os.environ.get("MILVUS_USER", "")
    MILVUS_PASSWORD = os.environ.get("MILVUS_PASSWORD", "")
    
    # 从环境变量加载配置
    @classmethod
    def init_app(cls, app):
        app.config.from_mapping(
            {k: v for k, v in cls.__dict__.items() 
             if not k.startswith('__') and k.isupper()}
        )
        app.config.from_envvar('FLASK_CONFIG_FILE', silent=True)

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:123456@127.0.0.1:3306/paraluxflow"

class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://1"

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False

# 配置映射
config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}

# 默认使用开发环境配置
AppConfig = config_by_name[os.getenv("FLASK_ENV", "development")]