"""LLM模型存储库"""
from datetime import datetime
import logging
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy import func, desc, and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.infrastructure.database.models.llm import  LLMModel, LLMProvider,LLMProviderConfig
from app.core.exceptions import NotFoundException
from app.core.status_codes import MODEL_NOT_FOUND,CONFIG_NOT_FOUND



logger = logging.getLogger(__name__)

class LLMModelRepository:
    """AI模型存储库"""
    
    def __init__(self, db_session: Session):
        """
        初始化存储库
        
        参数:
            db_session: 数据库会话
        """
        self.db = db_session
    
    def get_all_by_provider(self, provider_id: int) -> List[LLMModel]:
        """
        获取提供商的所有模型
        
        参数:
            provider_id: 提供商ID
            
        返回:
            模型列表
        """
        return self.db.query(LLMModel).filter(LLMModel.provider_id == provider_id).all()
    
    def get_by_model_id(self, model_id: str) -> LLMModel:
        """
        根据模型标识符获取模型
        
        参数:
            model_id: 模型标识符
            
        返回:
            模型实例
            
        异常:
            NotFoundException: 模型不存在
        """
        model = self.db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
        
        if not model:
            raise NotFoundException(f"未找到标识符为{model_id}的AI模型", MODEL_NOT_FOUND)
        
        return model
    
    def get_by_id(self, model_id: int, provider_id: int) -> LLMModel:
        """
        根据ID获取特定提供商的模型
        
        参数:
            model_id: 模型ID
            provider_id: 提供商ID
            
        返回:
            模型实例
            
        异常:
            NotFoundException: 模型不存在
        """
        model = self.db.query(LLMModel).filter(
            LLMModel.id == model_id,
            LLMModel.provider_id == provider_id
        ).first()
        
        if not model:
            raise NotFoundException(f"未找到ID为{model_id}的AI模型", MODEL_NOT_FOUND)
        
        return model

    
class LLMProviderRepository:
    """AI提供商存储库"""
    
    def __init__(self, db_session: Session):
        """
        初始化存储库
        
        参数:
            db_session: 数据库会话
        """
        self.db = db_session
    
    def get_all_providers(self) -> List[LLMProvider]:
        """
        获取用户的所有AI提供商

            
        返回:
            提供商列表
        """
        return self.db.query(LLMProvider).all()
    
    def get_by_id(self, provider_id: int) -> LLMProvider:
        """
        根据ID获取指定用户的AI提供商
        
        参数:
            provider_id: 提供商ID
  
            
        返回:
            提供商实例
            
        异常:
            NotFoundException: 提供商不存在
        """
        provider = self.db.query(LLMProvider).filter(
            LLMProvider.id == provider_id,
  
        ).first()
        
        if not provider:
            raise NotFoundException(f"未找到ID为{provider_id}的AI提供商")
        
        return provider
    

class LLMProviderConfigRepository:
    """用户LLM配置存储库"""

    def __init__(self, db_session: Session):
        """初始化存储库"""
        self.db = db_session

    def get_all_by_user(self, user_id: str) -> List[LLMProviderConfig]:
        """获取用户的所有LLM配置"""
        try:
            return (
                self.db.query(LLMProviderConfig).filter(LLMProviderConfig.user_id == user_id).all()
            )
        except SQLAlchemyError as e:
            logger.error(f"Error fetching configs: {str(e)}")
            self.db.rollback()
            raise

    def get_by_id(self, config_id: int, user_id: str) -> LLMProviderConfig:
        """根据ID获取特定用户的LLM配置"""
        try:
            config = (
                self.db.query(LLMProviderConfig)
                .filter(LLMProviderConfig.id == config_id, LLMProviderConfig.user_id == user_id)
                .first()
            )

            if not config:
                raise NotFoundException(f"未找到ID为{config_id}的配置", CONFIG_NOT_FOUND)

            return config
        except SQLAlchemyError as e:
            logger.error(f"Error fetching config: {str(e)}")
            self.db.rollback()
            raise

    def get_default(
        self, user_id: str, provider_type: Optional[str] = None
    ) -> Optional[LLMProviderConfig]:
        """获取用户的默认LLM配置"""
        try:
            query = self.db.query(LLMProviderConfig).filter(
                LLMProviderConfig.user_id == user_id, LLMProviderConfig.is_default == True
            )

            if provider_type:
                query = query.filter(LLMProviderConfig.provider_type == provider_type)

            return query.first()
        except SQLAlchemyError as e:
            logger.error(f"Error fetching default config: {str(e)}")
            self.db.rollback()
            raise

    def create(self, config_data: dict) -> LLMProviderConfig:
        """创建新配置"""
        try:
            # 开始事务
            config = LLMProviderConfig(**config_data)
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
            return config
        except SQLAlchemyError as e:
            logger.error(f"Error creating config: {str(e)}")
            self.db.rollback()
            raise

    def update(self, config_id: int, user_id: str, config_data: dict) -> LLMProviderConfig:
        """更新配置"""
        try:
            # 获取配置
            config = self.get_by_id(config_id, user_id)
            
            # 更新字段
            for key, value in config_data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            # 提交事务
            self.db.commit()
            self.db.refresh(config)
            return config
        except SQLAlchemyError as e:
            logger.error(f"Error updating config: {str(e)}")
            self.db.rollback()
            raise

    def delete(self, config_id: int, user_id: str) -> bool:
        """删除配置"""
        try:
            # 获取配置
            config = self.get_by_id(config_id, user_id)
            
            # 删除配置
            self.db.delete(config)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error deleting config: {str(e)}")
            self.db.rollback()
            raise

    def set_as_default(self, config_id: int, user_id: str) -> LLMProviderConfig:
        """设置配置为默认"""
        try:
            # 获取配置
            config = self.get_by_id(config_id, user_id)
            
            # 将所有同类型配置设为非默认
            self.db.query(LLMProviderConfig).filter(
                LLMProviderConfig.user_id == user_id,
                LLMProviderConfig.provider_type == config.provider_type,
                LLMProviderConfig.id != config_id
            ).update({"is_default": False})
            
            # 设置当前配置为默认
            config.is_default = True
            self.db.commit()
            self.db.refresh(config)
            return config
        except SQLAlchemyError as e:
            logger.error(f"Error setting default config: {str(e)}")
            self.db.rollback()
            raise