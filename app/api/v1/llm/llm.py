"""LLM配置API控制器"""
import logging
from typing import Dict, Any, List

from flask import Blueprint, request, g, jsonify

from app.api.middleware.auth import auth_required
from app.core.responses import success_response, error_response
from app.core.exceptions import ValidationException, NotFoundException
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.llm_repository import LLMModelRepository, LLMProviderConfigRepository, LLMProviderRepository
from app.infrastructure.llm_providers.factory import LLMProviderFactory

logger = logging.getLogger(__name__)

# 创建蓝图
llm_bp = Blueprint("llm", __name__)


@llm_bp.route("/providers", methods=["GET"])
@auth_required
def get_providers():
    """获取所有支持的LLM提供商
    
    Returns:
        提供商列表
    """
    try:
        # 创建会话和存储库
        db_session = get_db_session()
        provider_repo = LLMProviderRepository(db_session)
        
        # 获取所有提供商
        providers = provider_repo.get_all_providers()
        
        return success_response(providers)
    except Exception as e:
        logger.error(f"获取LLM提供商列表失败: {str(e)}")
        return error_response(50001, f"获取LLM提供商列表失败: {str(e)}")


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
            return error_response(50002, str(e))
        
        # 获取提供商的模型
        try:
            models = model_repo.get_all_by_provider(provider_id)
            return success_response(models)
        except Exception as e:
            return error_response(50003, f"获取模型列表失败: {str(e)}")
    except Exception as e:
        logger.error(f"获取提供商模型失败: {str(e)}")
        return error_response(50001, f"获取提供商模型失败: {str(e)}")


@llm_bp.route("/configs", methods=["GET"])
@auth_required
def get_configs():
    """获取用户的所有LLM配置
    
    Returns:
        配置列表
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 创建会话和存储库
        db_session = get_db_session()
        config_repo = LLMProviderConfigRepository(db_session)
        
        # 获取用户的所有配置
        configs = config_repo.get_all_by_user(user_id)
        
        # 隐藏敏感信息
        masked_configs = []
        for config in configs:
            # 创建配置的浅拷贝
            masked_config = config.copy() if isinstance(config, dict) else config.__dict__.copy()
            
            # 隐藏敏感字段
            sensitive_fields = ["api_key", "api_secret", "app_secret"]
            for field in sensitive_fields:
                if field in masked_config and masked_config[field]:
                    masked_config[field] = "********"
            
            masked_configs.append(masked_config)
        
        return success_response(masked_configs)
    except Exception as e:
        logger.error(f"获取LLM配置列表失败: {str(e)}")
        return error_response(50001, f"获取LLM配置列表失败: {str(e)}")


@llm_bp.route("/config/detail", methods=["GET"])
@auth_required
def get_config_detail():
    """获取配置详情
    
    查询参数:
    - config_id: 配置ID
    
    Returns:
        配置详情
    """
    try:
        user_id = g.user_id
        
        # 获取配置ID
        config_id = request.args.get("config_id")
        if not config_id:
            return error_response(50001, "缺少config_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        config_repo = LLMProviderConfigRepository(db_session)
        
        # 获取配置详情
        try:
            config = config_repo.get_by_id(config_id, user_id)
            
            # 隐藏敏感信息
            masked_config = config.copy() if isinstance(config, dict) else config.__dict__.copy()
            sensitive_fields = ["api_key", "api_secret", "app_secret"]
            for field in sensitive_fields:
                if field in masked_config and masked_config[field]:
                    masked_config[field] = "********"
            
            return success_response(masked_config)
        except NotFoundException as e:
            return error_response(50002, str(e))
    except Exception as e:
        logger.error(f"获取LLM配置详情失败: {str(e)}")
        return error_response(50001, f"获取LLM配置详情失败: {str(e)}")


@llm_bp.route("/config/add", methods=["POST"])
@auth_required
def add_config():
    """添加LLM配置
    
    请求体:
    {
        "name": "配置名称", // 必填
        "provider_type": "openai", // 必填
        "api_key": "sk-...", // 必填
        "api_secret": "...", // 可选
        "app_id": "...", // 可选
        "app_key": "...", // 可选
        "app_secret": "...", // 可选
        "api_base_url": "...", // 可选
        "api_version": "...", // 可选
        "region": "...", // 可选
        "is_default": true/false, // 可选，是否设为默认
        "request_timeout": 60, // 可选，超时时间
        "max_retries": 3, // 可选，最大重试次数
        "remark": "..." // 可选，备注
    }
    
    Returns:
        创建的配置
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(50001, "请求数据不能为空")
        
        # 验证必填字段
        required_fields = ["name", "provider_type", "api_key"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return error_response(50001, f"缺少必填字段: {', '.join(missing_fields)}")
        
        # 创建会话和存储库
        db_session = get_db_session()
        config_repo = LLMProviderConfigRepository(db_session)
        
        # 准备配置数据
        config_data = {
            "user_id": user_id,
            "name": data["name"],
            "provider_type": data["provider_type"],
            "api_key": data["api_key"],
            "is_active": True
        }
        
        # 添加可选字段
        optional_fields = [
            "api_secret", "app_id", "app_key", "app_secret", "api_base_url", 
            "api_version", "region", "is_default", "request_timeout", 
            "max_retries", "remark"
        ]
        for field in optional_fields:
            if field in data:
                config_data[field] = data[field]
        
        # 创建配置
        try:
            config = config_repo.create(config_data)
            
            # 如果设置为默认，需要更新其他配置
            if config_data.get("is_default", False):
                config_repo.set_as_default(config.id, user_id)
            
            # 隐藏敏感信息
            masked_config = config.__dict__.copy()
            sensitive_fields = ["api_key", "api_secret", "app_secret"]
            for field in sensitive_fields:
                if hasattr(config, field) and getattr(config, field):
                    masked_config[field] = "********"
            
            return success_response(masked_config)
        except Exception as e:
            return error_response(50003, f"创建配置失败: {str(e)}")
    except Exception as e:
        logger.error(f"添加LLM配置失败: {str(e)}")
        return error_response(50001, f"添加LLM配置失败: {str(e)}")


@llm_bp.route("/config/update", methods=["POST"])
@auth_required
def update_config():
    """更新LLM配置
    
    请求体:
    {
        "id": "config_id", // 必填
        "name": "配置名称", // 可选
        "api_key": "sk-...", // 可选
        "api_secret": "...", // 可选
        "app_id": "...", // 可选
        "app_key": "...", // 可选
        "app_secret": "...", // 可选
        "api_base_url": "...", // 可选
        "api_version": "...", // 可选
        "region": "...", // 可选
        "is_active": true/false, // 可选
        "request_timeout": 60, // 可选
        "max_retries": 3, // 可选
        "remark": "..." // 可选
    }
    
    Returns:
        更新后的配置
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(50001, "请求数据不能为空")
        
        # 验证必填字段
        if "id" not in data:
            return error_response(50001, "缺少id字段")
        
        # 创建会话和存储库
        db_session = get_db_session()
        config_repo = LLMProviderConfigRepository(db_session)
        
        # 更新配置
        try:
            # 移除不可修改字段
            if "user_id" in data:
                del data["user_id"]
            if "provider_type" in data:
                del data["provider_type"]
            
            config = config_repo.update(data["id"], user_id, data)
            
            # 隐藏敏感信息
            masked_config = config.__dict__.copy()
            sensitive_fields = ["api_key", "api_secret", "app_secret"]
            for field in sensitive_fields:
                if hasattr(config, field) and getattr(config, field):
                    masked_config[field] = "********"
            
            return success_response(masked_config)
        except NotFoundException as e:
            return error_response(50002, str(e))
        except Exception as e:
            return error_response(50003, f"更新配置失败: {str(e)}")
    except Exception as e:
        logger.error(f"更新LLM配置失败: {str(e)}")
        return error_response(50001, f"更新LLM配置失败: {str(e)}")


@llm_bp.route("/config/delete", methods=["POST"])
@auth_required
def delete_config():
    """删除LLM配置
    
    请求体:
    {
        "id": "config_id" // 必填
    }
    
    Returns:
        删除结果
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取请求数据
        data = request.get_json()
        if not data or "id" not in data:
            return error_response(50001, "缺少id字段")
        
        # 创建会话和存储库
        db_session = get_db_session()
        config_repo = LLMProviderConfigRepository(db_session)
        
        # 删除配置
        try:
            result = config_repo.delete(data["id"], user_id)
            return success_response({"success": result})
        except NotFoundException as e:
            return error_response(50002, str(e))
        except Exception as e:
            return error_response(50003, f"删除配置失败: {str(e)}")
    except Exception as e:
        logger.error(f"删除LLM配置失败: {str(e)}")
        return error_response(50001, f"删除LLM配置失败: {str(e)}")


@llm_bp.route("/config/set_default", methods=["POST"])
@auth_required
def set_default_config():
    """设置默认LLM配置
    
    请求体:
    {
        "id": "config_id" // 必填
    }
    
    Returns:
        设置结果
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取请求数据
        data = request.get_json()
        if not data or "id" not in data:
            return error_response(50001, "缺少id字段")
        
        # 创建会话和存储库
        db_session = get_db_session()
        config_repo = LLMProviderConfigRepository(db_session)
        
        # 设置默认配置
        try:
            config = config_repo.set_as_default(data["id"], user_id)
            
            # 隐藏敏感信息
            masked_config = config.__dict__.copy()
            sensitive_fields = ["api_key", "api_secret", "app_secret"]
            for field in sensitive_fields:
                if hasattr(config, field) and getattr(config, field):
                    masked_config[field] = "********"
            
            return success_response(masked_config)
        except NotFoundException as e:
            return error_response(50002, str(e))
        except Exception as e:
            return error_response(50003, f"设置默认配置失败: {str(e)}")
    except Exception as e:
        logger.error(f"设置默认LLM配置失败: {str(e)}")
        return error_response(50001, f"设置默认LLM配置失败: {str(e)}")


@llm_bp.route("/config/test", methods=["POST"])
@auth_required
def test_config():
    """测试LLM配置连接
    
    请求体:
    {
        "id": "config_id" // 已存在的配置ID，或者
        "provider_type": "openai", // 新配置提供商类型
        "api_key": "sk-...", // 新配置API密钥
        ... // 其他配置参数
    }
    
    Returns:
        测试结果
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(50001, "请求数据不能为空")
        
        # 创建会话和存储库
        db_session = get_db_session()
        config_repo = LLMProviderConfigRepository(db_session)
        
        # 确定测试方式
        config_to_test = None
        
        if "id" in data:
            # 测试已存在的配置
            try:
                config_to_test = config_repo.get_by_id(data["id"], user_id)
            except NotFoundException as e:
                return error_response(50002, str(e))
        elif "provider_type" in data and "api_key" in data:
            # 测试新配置
            config_to_test = data
        else:
            return error_response(50001, "需要提供配置ID或提供商类型和API密钥")
        
        # 提取配置信息
        provider_type = config_to_test.get("provider_type")
        api_key = config_to_test.get("api_key")
        
        # 其他配置参数
        config_params = {}
        optional_params = [
            "api_base_url", "api_version", "request_timeout", 
            "max_retries", "default_model"
        ]
        for param in optional_params:
            if param in config_to_test:
                config_params[param] = config_to_test[param]
        
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
            })
        except Exception as e:
            return error_response(50003, f"连接测试失败: {str(e)}")
    except Exception as e:
        logger.error(f"测试LLM配置失败: {str(e)}")
        return error_response(50001, f"测试LLM配置失败: {str(e)}")