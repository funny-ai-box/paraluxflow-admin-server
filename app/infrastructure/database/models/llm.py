from datetime import datetime
from app.core.security import generate_uuid
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, Float

from app.extensions import db


class LLMProvider(db.Model):
    """AI提供商模型"""
    __tablename__ = "llm_providers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, comment="提供商名称")
    provider_type = Column(String(20), nullable=False, comment="提供商类型，如OpenAI, Claude, Volcano")
    description = Column(Text, nullable=True, comment="提供商描述")
    # 鉴权需求字段
    auth_type = Column(String(50), nullable=False, comment="鉴权类型，如api_key, key_secret, id_key_secret")
    required_fields = Column(JSON, nullable=False, comment="必填字段列表")
    optional_fields = Column(JSON, nullable=True, comment="可选字段列表")
    auth_description = Column(Text, nullable=True, comment="鉴权描述")
    # 通用字段
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    
    def __repr__(self):
        return f"<LLMProvider {self.name} - {self.provider_type}>"
    
    def to_auth_dict(self):
        """返回鉴权需求字典格式"""
        return {
            "auth_type": self.auth_type,
            "required_fields": self.required_fields,
            "optional_fields": self.optional_fields,
            "description": self.auth_description
        }



class ModelType:
    """LLM模型类型枚举 - 使用常量而非Enum以便于扩展"""
    CHAT = "chat"                    # 对话型模型
    COMPLETION = "completion"        # 文本补全型模型
    EMBEDDING = "embedding"          # 嵌入向量模型
    MULTIMODAL = "multimodal"        # 多模态模型（处理图像和文本）
    CODE = "code"                    # 代码生成模型
    VISION = "vision"                # 视觉识别模型
    FINE_TUNED = "fine_tuned"        # 微调模型
    INSTRUCTION_TUNED = "instruction_tuned"  # 指令微调模型
    RAG = "rag"                      # 检索增强生成模型
    REASONING = "reasoning"          # 推理增强型模型


class LLMModel(db.Model):
    """LLM模型模型"""
    __tablename__ = "llm_models"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="模型名称")
    model_id = Column(String(100), nullable=False, comment="模型标识符，如gpt-4-turbo")
    model_type = Column(String(50), nullable=False, comment="模型类型")
    description = Column(Text, nullable=True, comment="模型描述")
    capabilities = Column(Text, nullable=True, comment="模型能力描述")
    context_window = Column(Integer, nullable=True, comment="上下文窗口大小")
    max_tokens = Column(Integer, nullable=True, comment="最大生成令牌数")
    token_price_input = Column(Float, nullable=True, comment="输入令牌价格")
    token_price_output = Column(Float, nullable=True, comment="输出令牌价格")
    supported_features = Column(JSON, nullable=True, comment="支持的特性列表")
    language_support = Column(JSON, nullable=True, comment="支持的语言列表")
    training_data_cutoff = Column(DateTime, nullable=True, comment="训练数据截止日期")
    version = Column(String(50), nullable=True, comment="模型版本")
    is_available = Column(Boolean, default=True, comment="是否可用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    provider_id = Column(Integer, nullable=False, comment="所属提供商ID")
    
    def __repr__(self):
        return f"<LLMModel {self.name}>"
    

class LLMProviderConfig(db.Model):
    """用户LLM配置模型"""

    __tablename__ = "llm_provider_configs"

    id = Column(String(32), primary_key=True,default=generate_uuid)
    user_id = Column(String(32), nullable=False, comment="所属用户ID")
    provider_type = Column(
        String(50), nullable=False, comment="提供商类型，如OpenAI, Claude, Volcano"
    )
    name = Column(String(100), nullable=False, comment="配置名称")

    # 鉴权信息
    api_key = Column(Text, nullable=True, comment="API密钥")
    api_secret = Column(Text, nullable=True, comment="API密钥密文")
    app_id = Column(String(100), nullable=True, comment="应用ID")
    app_key = Column(String(100), nullable=True, comment="应用Key")
    app_secret = Column(Text, nullable=True, comment="应用密钥")

    # 服务配置
    api_base_url = Column(String(255), nullable=True, comment="API基础URL(可选)")
    api_version = Column(String(50), nullable=True, comment="API版本(可选)")
    region = Column(String(50), nullable=True, comment="区域设置")

    # 运行配置
    is_default = Column(Boolean, default=False, comment="是否为默认配置")
    is_active = Column(Boolean, default=True, comment="是否启用")
    request_timeout = Column(Integer, default=60, comment="请求超时时间(秒)")
    max_retries = Column(Integer, default=3, comment="最大重试次数")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
    remark = Column(Text, nullable=True, comment="备注")

    def __repr__(self):
        return f"<LLMProviderConfig {self.name} - {self.provider_type}>"
