"""LLM提供商存储库"""
import logging
from datetime import datetime
import json
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy import func, desc, and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.infrastructure.database.models.llm import LLMModel, LLMProvider
from app.core.exceptions import NotFoundException, ValidationException
from app.core.status_codes import MODEL_NOT_FOUND, PROVIDER_NOT_FOUND, PROVIDER_VALIDATION_ERROR


logger = logging.getLogger(__name__)

class LLMModelRepository:
    """AI模型存储库"""
    
    def __init__(self, db_session: Session):
        """初始化存储库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session
    
    def get_all_by_provider(self, provider_id: int) -> List[Dict[str, Any]]:
        """获取提供商的所有模型
        
        Args:
            provider_id: 提供商ID
            
        Returns:
            模型列表
        """
        try:
            models = self.db.query(LLMModel).filter(LLMModel.provider_id == provider_id).all()
            return [self._model_to_dict(model) for model in models]
        except SQLAlchemyError as e:
            logger.error(f"获取提供商模型失败: {str(e)}")
            return []
    
    def get_by_model_id(self, model_id: str) -> Dict[str, Any]:
        """根据模型标识符获取模型
        
        Args:
            model_id: 模型标识符
            
        Returns:
            模型实例
            
        Raises:
            NotFoundException: 模型不存在
        """
        try:
            model = self.db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
            
            if not model:
                raise NotFoundException(f"未找到标识符为{model_id}的AI模型", MODEL_NOT_FOUND)
            
            return self._model_to_dict(model)
        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"获取模型失败: {str(e)}")
            raise
    
    def get_by_id(self, model_id: int) -> Dict[str, Any]:
        """根据ID获取模型
        
        Args:
            model_id: 模型ID
            
        Returns:
            模型实例
            
        Raises:
            NotFoundException: 模型不存在
        """
        try:
            model = self.db.query(LLMModel).filter(LLMModel.id == model_id).first()
            
            if not model:
                raise NotFoundException(f"未找到ID为{model_id}的AI模型", MODEL_NOT_FOUND)
            
            return self._model_to_dict(model)
        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"获取模型失败: {str(e)}")
            raise
    
    def _model_to_dict(self, model: LLMModel) -> Dict[str, Any]:
        """将模型对象转换为字典
        
        Args:
            model: 模型对象
            
        Returns:
            模型字典
        """
        result = {
            "id": model.id,
            "name": model.name,
            "model_id": model.model_id,
            "model_type": model.model_type,
            "description": model.description,
            "capabilities": model.capabilities,
            "context_window": model.context_window,
            "max_tokens": model.max_tokens,
            "token_price_input": model.token_price_input,
            "token_price_output": model.token_price_output,
            "supported_features": model.supported_features,
            "language_support": model.language_support,
            "training_data_cutoff": model.training_data_cutoff.isoformat() if model.training_data_cutoff else None,
            "version": model.version,
            "is_available": model.is_available,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
            "provider_id": model.provider_id
        }
        
        # 解析JSON字段
        if model.supported_features and isinstance(model.supported_features, str):
            try:
                result["supported_features"] = json.loads(model.supported_features)
            except:
                result["supported_features"] = model.supported_features
                
        if model.language_support and isinstance(model.language_support, str):
            try:
                result["language_support"] = json.loads(model.language_support)
            except:
                result["language_support"] = model.language_support
                
        return result


class LLMProviderRepository:
    """AI提供商存储库"""
    
    def __init__(self, db_session: Session):
        """初始化存储库
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session
    
    def get_all_providers(self) -> List[Dict[str, Any]]:
        """获取所有AI提供商
            
        Returns:
            提供商列表
        """
        try:
            providers = self.db.query(LLMProvider).all()
            return [self._provider_to_dict(provider) for provider in providers]
        except SQLAlchemyError as e:
            logger.error(f"获取所有AI提供商失败: {str(e)}")
            return []
    
    def get_by_id(self, provider_id: int) -> Dict[str, Any]:
        """根据ID获取AI提供商
        
        Args:
            provider_id: 提供商ID
            
        Returns:
            提供商实例
            
        Raises:
            NotFoundException: 提供商不存在
        """
        try:
            provider = self.db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
            
            if not provider:
                raise NotFoundException(f"未找到ID为{provider_id}的AI提供商", PROVIDER_NOT_FOUND)
            
            return self._provider_to_dict(provider)
        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"获取AI提供商失败: {str(e)}")
            raise
    
    def update_provider_config(self, provider_id: int, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新AI提供商配置信息
        
        Args:
            provider_id: 提供商ID
            config_data: 配置数据
            
        Returns:
            更新后的提供商
            
        Raises:
            NotFoundException: 提供商不存在
            SQLAlchemyError: 数据库错误
        """
        try:
            # 获取提供商
            provider = self.db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
            if not provider:
                raise NotFoundException(f"未找到ID为{provider_id}的AI提供商", PROVIDER_NOT_FOUND)
            
            # 更新配置字段
            for key, value in config_data.items():
                if hasattr(provider, key):
                    setattr(provider, key, value)
            
            self.db.commit()
            self.db.refresh(provider)
            
            return self._provider_to_dict(provider)
        except NotFoundException:
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"更新AI提供商配置失败: {str(e)}")
            raise

    def _provider_to_dict(self, provider: LLMProvider) -> Dict[str, Any]:
        """将提供商对象转换为字典
        
        Args:
            provider: 提供商对象
            
        Returns:
            提供商字典
        """
        return {
            "id": provider.id,
            "name": provider.name,
            "provider_type": provider.provider_type,
            "description": provider.description,
            "api_key": provider.api_key,
            "api_secret": provider.api_secret,
            "app_id": provider.app_id,
            "app_key": provider.app_key,
            "app_secret": provider.app_secret,
            "api_base_url": provider.api_base_url,
            "api_version": provider.api_version,
            "region": provider.region,
            "request_timeout": provider.request_timeout,
            "max_retries": provider.max_retries,
            "default_model": provider.default_model,
            "is_active": provider.is_active,
            "created_at": provider.created_at.isoformat() if provider.created_at else None,
            "updated_at": provider.updated_at.isoformat() if provider.updated_at else None
        }