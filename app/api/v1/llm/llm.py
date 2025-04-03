"""LLM配置API控制器"""
import logging
from typing import Dict, Any, List

from flask import Blueprint, request, g, jsonify

from app.api.middleware.auth import auth_required, admin_required
from app.core.responses import success_response, error_response
from app.core.exceptions import ValidationException, NotFoundException
from app.core.status_codes import PARAMETER_ERROR, PROVIDER_NOT_FOUND
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.llm_repository import LLMModelRepository, LLMProviderRepository
from app.infrastructure.llm_providers.factory import LLMProviderFactory

logger = logging.getLogger(__name__)

# 创建蓝图
llm_bp = Blueprint("llm", __name__)


@llm_bp.route("/providers", methods=["GET"])
@auth_required
def get_providers():
    """获取所有LLM提供商
    
    Returns:
        提供商列表
    """
    try:
        # 创建会话和存储库
        db_session = get_db_session()
        provider_repo = LLMProviderRepository(db_session)
        
        # 获取所有提供商
        providers = provider_repo.get_all_providers()
        
        # 屏蔽敏感信息
        masked_providers = []
        for provider in providers:
            masked_provider = provider.copy()
            # 屏蔽API密钥等敏感信息
            sensitive_fields = ["api_key", "api_secret", "app_key", "app_secret"]
            for field in sensitive_fields:
                if field in masked_provider and masked_provider[field]:
                    masked_provider[field] = "********"
            
            masked_providers.append(masked_provider)
        
        return success_response(masked_providers)
    except Exception as e:
        logger.error(f"获取LLM提供商列表失败: {str(e)}")
        return error_response(50001, f"获取LLM提供商列表失败: {str(e)}")


@llm_bp.route("/provider/detail", methods=["GET"])
@auth_required
def get_provider_detail():
    """获取LLM提供商详情
    
    查询参数:
    - provider_id: 提供商ID
    
    Returns:
        提供商详情
    """
    try:
        # 获取提供商ID
        provider_id = request.args.get("provider_id", type=int)
        if not provider_id:
            return error_response(50001, "缺少provider_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        provider_repo = LLMProviderRepository(db_session)
        
        # 获取提供商详情
        try:
            provider = provider_repo.get_by_id(provider_id)
            
            # 屏蔽敏感信息
            masked_provider = provider.copy()
            sensitive_fields = ["api_key", "api_secret", "app_key", "app_secret"]
            for field in sensitive_fields:
                if field in masked_provider and masked_provider[field]:
                    masked_provider[field] = "********"
            
            return success_response(masked_provider)
        except NotFoundException as e:
            return error_response(PROVIDER_NOT_FOUND, str(e))
    except Exception as e:
        logger.error(f"获取LLM提供商详情失败: {str(e)}")
        return error_response(50001, f"获取LLM提供商详情失败: {str(e)}")


@llm_bp.route("/provider/models", methods=["GET"])
@auth_required
def get_provider_models():
    """获取指定提供商支持的模型
    
    查询参数:
    - provider_id: 提供商ID
    
    Returns:
        模型列表
    """
    try:
        # 获取提供商ID
        provider_id = request.args.get("provider_id", type=int)
        if not provider_id:
            return error_response(50001, "缺少provider_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        provider_repo = LLMProviderRepository(db_session)
        model_repo = LLMModelRepository(db_session)
        
        # 验证提供商存在
        try:
            provider = provider_repo.get_by_id(provider_id)
        except NotFoundException as e:
            return error_response(PROVIDER_NOT_FOUND, str(e))
        
        # 获取提供商的模型
        try:
            models = model_repo.get_all_by_provider(provider_id)
            return success_response(models)
        except Exception as e:
            return error_response(50003, f"获取模型列表失败: {str(e)}")
    except Exception as e:
        logger.error(f"获取提供商模型失败: {str(e)}")
        return error_response(50001, f"获取提供商模型失败: {str(e)}")


@llm_bp.route("/provider/update_config", methods=["POST"])
@admin_required
def update_provider_config():
    """更新LLM提供商配置信息(仅管理员)
    
    请求体:
    {
        "id": 1, // 必填
        "api_key": "sk-...", // 可选，API密钥
        "api_secret": "...", // 可选，API密钥密文
        "app_id": "...", // 可选，应用ID
        "app_key": "...", // 可选，应用Key
        "app_secret": "...", // 可选，应用密钥
        "api_base_url": "...", // 可选，API基础URL
        "api_version": "...", // 可选，API版本
        "region": "...", // 可选，区域设置
        "request_timeout": 60, // 可选，请求超时时间(秒)
        "max_retries": 3, // 可选，最大重试次数
        "default_model": "gpt-4" // 可选，默认模型
    }
    
    Returns:
        更新结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(50001, "请求数据不能为空")
        
        # 验证必填字段
        if "id" not in data:
            return error_response(50001, "缺少id字段")
        
        # 创建会话和存储库
        db_session = get_db_session()
        provider_repo = LLMProviderRepository(db_session)
        
        # 只保留配置相关字段
        config_fields = [
            "api_key", "api_secret", "app_id", "app_key", "app_secret",
            "api_base_url", "api_version", "region", "request_timeout",
            "max_retries", "default_model"
        ]
        
        config_data = {k: v for k, v in data.items() if k in config_fields}
        
        # 至少需要提供一个配置字段
        if not config_data:
            return error_response(50001, "至少需要提供一个配置字段")
        
        # 更新提供商配置
        try:
            provider = provider_repo.update_provider_config(data["id"], config_data)
            
            # 屏蔽敏感信息
            masked_provider = provider.copy()
            sensitive_fields = ["api_key", "api_secret", "app_key", "app_secret"]
            for field in sensitive_fields:
                if field in masked_provider and masked_provider[field]:
                    masked_provider[field] = "********"
            
            return success_response(masked_provider, "提供商配置更新成功")
        except NotFoundException as e:
            return error_response(PROVIDER_NOT_FOUND, str(e))
        except Exception as e:
            return error_response(50003, f"更新提供商配置失败: {str(e)}")
    except Exception as e:
        logger.error(f"更新LLM提供商配置失败: {str(e)}")
        return error_response(50001, f"更新LLM提供商配置失败: {str(e)}")


@llm_bp.route("/provider/test", methods=["POST"])
@auth_required
def test_provider():
    """测试LLM提供商连接
    
    请求体:
    {
        "id": 1, // 必填，提供商ID
        "api_key": "sk-...", // 可选，API密钥(不提供则使用数据库中的)
        "api_base_url": "...", // 可选，覆盖API基础URL
        ... // 其他可选配置参数
    }
    
    Returns:
        测试结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(50001, "请求数据不能为空")
        
        # 验证必填字段
        if "id" not in data:
            return error_response(50001, "缺少id字段")
        
        # 创建会话和存储库
        db_session = get_db_session()
        provider_repo = LLMProviderRepository(db_session)
        
        # 获取提供商信息
        try:
            provider = provider_repo.get_by_id(data["id"])
        except NotFoundException as e:
            return error_response(PROVIDER_NOT_FOUND, str(e))
        
        # 提取配置信息，允许请求参数覆盖数据库值
        provider_type = provider.get("provider_type")
        api_key = data.get("api_key") or provider.get("api_key")
        
        if not api_key:
            return error_response(50001, "缺少API密钥")
        
        # 其他配置参数
        config_params = {}
        optional_params = [
            "api_base_url", "api_version", "request_timeout", 
            "max_retries", "default_model", "app_id", "app_key", "app_secret"
        ]
        
        # 优先使用请求中的参数，其次使用数据库中的值
        for param in optional_params:
            if param in data:
                config_params[param] = data[param]
            elif param in provider and provider[param]:
                config_params[param] = provider[param]
        
        # 创建LLM提供商客户端
        try:
            llm_provider = LLMProviderFactory.create_provider(
                provider_type, 
                api_key, 
                **config_params
            )
            
            # 测试连接
            health_check = llm_provider.health_check()
            if not health_check:
                return error_response(50003, "连接测试失败")
            
            # 获取可用模型
            models = llm_provider.get_available_models()
            
            return success_response({
                "success": True,
                "provider": llm_provider.get_provider_name(),
                "models": models
            }, "连接测试成功")
        except Exception as e:
            return error_response(50003, f"连接测试失败: {str(e)}")
    except Exception as e:
        logger.error(f"测试LLM提供商失败: {str(e)}")
        return error_response(50001, f"测试LLM提供商失败: {str(e)}")