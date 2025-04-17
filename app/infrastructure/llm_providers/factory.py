"""AI提供商工厂模块，负责创建和管理AI提供商实例"""
import logging
from typing import Dict, Any, Optional

from app.infrastructure.llm_providers.base import LLMProviderInterface
from app.infrastructure.llm_providers.openai_provider import OpenLLMProvider
from app.infrastructure.llm_providers.anthropic_provider import AnthropicProvider
from app.infrastructure.llm_providers.volcano_provider import VolcanoProvider
from app.core.exceptions import APIException
from app.core.status_codes import EXTERNAL_API_ERROR, PROVIDER_NOT_FOUND
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.llm_repository import LLMProviderRepository

logger = logging.getLogger(__name__)

class LLMProviderFactory:
    """AI提供商工厂类，负责创建和管理AI提供商实例"""
    
    # 支持的提供商映射
    PROVIDERS = {
        "openai": OpenLLMProvider,
        "anthropic": AnthropicProvider,
        "volcano": VolcanoProvider
    }
    
    @classmethod
    def _get_provider_config_from_db(cls, provider_name: str) -> Dict[str, Any]:
        """从数据库获取提供商配置
        
        Args:
            provider_name: 提供商名称，如"openai"、"anthropic"
            
        Returns:
            提供商配置信息
            
        Raises:
            APIException: 如果提供商不存在或获取失败
        """
        try:
            # 获取数据库会话
            db_session = get_db_session()
            
            # 初始化提供商仓库
            provider_repo = LLMProviderRepository(db_session)
            
            # 查询所有提供商
            providers = provider_repo.get_all_providers()
            
            # 查找匹配的提供商
            for provider in providers:
                if provider["provider_type"].lower() == provider_name.lower() and provider["is_active"]:
                    # 返回提供商配置
                    return {
                        "api_key": provider.get("api_key"),
                        "api_secret": provider.get("api_secret"),
                        "app_id": provider.get("app_id"),
                        "app_key": provider.get("app_key"),
                        "app_secret": provider.get("app_secret"),
                        "api_base_url": provider.get("api_base_url"),
                        "api_version": provider.get("api_version"),
                        "region": provider.get("region"),
                        "request_timeout": provider.get("request_timeout"),
                        "max_retries": provider.get("max_retries"),
                        "default_model": provider.get("default_model"),
                        "provider_id": provider.get("id")
                    }
            print(providers)
            # 未找到匹配的提供商
            raise APIException(
                f"未找到可用的{provider_name}提供商配置，请先在管理后台配置", 
                PROVIDER_NOT_FOUND
            )
            
        except Exception as e:
            if isinstance(e, APIException):
                raise
            logger.error(f"获取提供商配置失败: {str(e)}")
            raise APIException(f"获取提供商配置失败: {str(e)}", EXTERNAL_API_ERROR)
    
    @classmethod
    def create_provider(cls, provider_name: str, api_key: str = None, **config) -> LLMProviderInterface:
        """创建AI提供商实例
        
        Args:
            provider_name: 提供商名称，如"openai"、"anthropic"
            api_key: API密钥，可选，如果不提供则从数据库获取
            **config: 其他配置参数
            
        Returns:
            初始化好的AI提供商实例
            
        Raises:
            APIException: 如果提供商不支持或初始化失败
        """
        provider_name = provider_name.lower()
        
        if provider_name not in cls.PROVIDERS:
            logger.error(f"Unsupported AI provider: {provider_name}")
            raise APIException(
                f"不支持的AI提供商: {provider_name}，支持的提供商: {', '.join(cls.PROVIDERS.keys())}", 
                EXTERNAL_API_ERROR
            )
        
        try:
            # 如果没有提供API密钥，则从数据库获取配置
            if api_key is None:
                provider_config = cls._get_provider_config_from_db(provider_name)
                print(provider_config)
                
                # 合并传入的配置和数据库配置
                for key, value in provider_config.items():
                    if key not in config and value is not None:
                        config[key] = value
                
                # 使用数据库中的API密钥
                api_key = provider_config.get("api_key")

                
                if not api_key and provider_name != "anthropic":
                    raise APIException(f"未找到{provider_name}提供商的API密钥", EXTERNAL_API_ERROR)
            
            # 创建提供商实例
            provider = cls.PROVIDERS[provider_name]()
            
            # 初始化提供商
            provider.initialize( **config)
            
            logger.info(f"Successfully created and initialized {provider_name} provider")
            return provider
        except Exception as e:
            logger.error(f"Failed to create {provider_name} provider: {str(e)}")
            if isinstance(e, APIException):
                raise
            raise APIException(f"创建AI提供商失败: {str(e)}", EXTERNAL_API_ERROR)