# app/infrastructure/llm_providers/factory.py
"""AI提供商工厂模块，负责创建和管理AI提供商实例"""
import logging
from typing import Dict, Any, Optional

from app.infrastructure.llm_providers.base import LLMProviderInterface
from app.infrastructure.llm_providers.openai_provider import OpenLLMProvider
from app.infrastructure.llm_providers.anthropic_provider import AnthropicProvider
from app.infrastructure.llm_providers.volcano_provider import VolcanoProvider
from app.infrastructure.llm_providers.gemini_provider import GeminiProvider
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
        "volcano": VolcanoProvider,
        "gemini": GeminiProvider
    }

    @classmethod
    def _get_provider_config_from_db(cls, provider_name: Optional[str] = None) -> Dict[str, Any]:
        """从数据库获取指定或默认的活跃提供商配置

        Args:
            provider_name: 提供商类型名称(如"openai")。如果为None，则获取默认(第一个活跃)提供商。

        Returns:
            提供商配置信息字典。

        Raises:
            APIException: 如果找不到匹配或默认的提供商。
        """
        try:
            db_session = get_db_session()
            provider_repo = LLMProviderRepository(db_session)
            providers = provider_repo.get_all_providers() # 获取所有提供商

            target_provider = None
            if provider_name:
                # 查找指定的活跃提供商
                target_provider = next(
                    (p for p in providers if p["provider_type"].lower() == provider_name.lower() ),
                    None
                )
                if not target_provider:
                    raise APIException(
                        f"未找到可用的 {provider_name} 提供商配置，请先在管理后台配置",
                        PROVIDER_NOT_FOUND
                    )
            else:
                # 查找第一个活跃的提供商作为默认
                target_provider = next((p for p in providers if p.get("is_active")), None)
                if not target_provider:
                    raise APIException(
                        "未找到任何可用的默认提供商配置，请先在管理后台配置",
                        PROVIDER_NOT_FOUND
                    )
                logger.info(f"未指定provider_name，使用默认提供商: {target_provider.get('provider_type')}")


            # 返回配置，不包含app_key
            return {
                "provider_type": target_provider.get("provider_type"),
                "api_key": target_provider.get("api_key"),
                "api_secret": target_provider.get("api_secret"),
                "app_id": target_provider.get("app_id"),
                # "app_key": target_provider.get("app_key"), # 移除 app_key
                "app_secret": target_provider.get("app_secret"),
                "api_base_url": target_provider.get("api_base_url"),
                "api_version": target_provider.get("api_version"),
                "region": target_provider.get("region"),
                "request_timeout": target_provider.get("request_timeout"),
                "max_retries": target_provider.get("max_retries"),
                "default_model": target_provider.get("default_model"), # 保留 default_model
                "provider_id": target_provider.get("id")
            }

        except APIException:
             raise # 直接抛出已知的API异常
        except Exception as e:
            logger.error(f"获取提供商配置失败: {str(e)}")
            raise APIException(f"获取提供商配置失败: {str(e)}", EXTERNAL_API_ERROR)

    @classmethod
    def create_provider(cls, provider_name: Optional[str] = None, model_id: Optional[str] = None, **config) -> LLMProviderInterface:
        """创建AI提供商实例

        Args:
            provider_name: 提供商类型名称 (可选, 如 "openai"). 如果不提供, 使用数据库默认。
            model_id: 模型ID (可选, 如 "gpt-4o"). 如果不提供, 使用对应提供商的默认模型。
            **config: 其他配置参数, 会覆盖从数据库获取的同名配置。

        Returns:
            初始化好的AI提供商实例

        Raises:
            APIException: 如果提供商不支持、未找到或初始化失败。
        """
        final_provider_name = None
        final_model_id = None
        provider_config = {}

        try:
            # 1. 确定提供商和模型配置
            if provider_name:
                # 如果指定了 provider_name
                provider_config = cls._get_provider_config_from_db(provider_name)
                final_provider_name = provider_name.lower()
                # model_id 优先级: 传入 > DB默认
                final_model_id = model_id or provider_config.get("default_model")
                logger.info(f"使用指定提供商: {final_provider_name}, 模型: {final_model_id or 'DB默认'}")
            else:
                # 如果未指定 provider_name，获取默认提供商配置
                provider_config = cls._get_provider_config_from_db(None) # 获取默认配置
                final_provider_name = provider_config.get("provider_type").lower()
                # model_id 优先级: 传入 > DB默认
                final_model_id = model_id or provider_config.get("default_model")
                logger.info(f"使用默认提供商: {final_provider_name}, 模型: {final_model_id or 'DB默认'}")

            if not final_provider_name:
                 raise APIException("无法确定有效的AI提供商", PROVIDER_NOT_FOUND)

            if final_provider_name not in cls.PROVIDERS:
                logger.error(f"Unsupported AI provider: {final_provider_name}")
                raise APIException(
                    f"不支持的AI提供商: {final_provider_name}，支持的提供商: {', '.join(cls.PROVIDERS.keys())}",
                    EXTERNAL_API_ERROR
                )

            # 2. 准备最终的初始化配置
            # 合并配置：数据库配置 < 传入的**config
            merged_config = {}
            merged_config.update({k: v for k, v in provider_config.items() if v is not None}) # Start with DB config
            merged_config.update(config) # Override with explicitly passed config

            # 确保使用最终确定的模型ID (用于初始化，如设置默认模型)
            if final_model_id:
                merged_config["default_model"] = final_model_id # 设置/覆盖默认模型

            # 移除不应直接传递给 initialize 的内部键 (如果需要)
            # merged_config.pop("provider_type", None) # 根据 provider 的 initialize 方法决定是否移除
            merged_config.pop("provider_id", None)

            # 3. API Key 检查 (从 merged_config 获取，因为它包含了DB或传入的值)
            api_key = merged_config.get("api_key")
            # Anthropic 和 Volcano 可能有特殊处理（Volcano 的 initialize 内部会处理 api_key）
            if not api_key and final_provider_name not in ["anthropic", "volcano"]:
                 raise APIException(f"未找到 {final_provider_name} 提供商的API密钥", EXTERNAL_API_ERROR)

            # 4. 创建和初始化提供商实例
            provider = cls.PROVIDERS[final_provider_name]()
            # 使用合并后的配置进行初始化
            provider.initialize(**merged_config)

            logger.info(f"成功创建并初始化 {final_provider_name} provider (模型: {final_model_id or 'provider default'})")
            return provider

        except APIException as e:
            # 如果是已知APIException，直接抛出
            logger.error(f"创建AI提供商({provider_name or 'default'})失败: {str(e)}")
            raise
        except Exception as e:
            # 其他未知异常，包装成APIException抛出
            logger.error(f"创建AI提供商({provider_name or 'default'})时发生意外错误: {str(e)}", exc_info=True)
            raise APIException(f"创建AI提供商失败: {str(e)}", EXTERNAL_API_ERROR)