# app/api/client/v1/assistant/general.py
"""AI助手通用API接口 - 提供通用AI对话和处理功能"""
import logging
from flask import Blueprint, request, g

from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR
from app.core.exceptions import ValidationException
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.user_preferences_repository import UserPreferencesRepository
from app.domains.user.services.preferences_service import UserPreferencesService
from app.infrastructure.llm_providers.factory import LLMProviderFactory
from app.api.middleware.client_auth import client_auth_required

assistant_general_bp = Blueprint("assistant_general_bp", __name__)

logger = logging.getLogger(__name__)

@assistant_general_bp.route("/chat", methods=["POST"])
@client_auth_required
def chat_with_assistant():
    """与AI助手对话
    
    请求体:
    {
        "message": "你好，请帮我分析一下今天的新闻",
        "context": [  // 可选，对话上下文
            {"role": "user", "content": "之前的消息"},
            {"role": "assistant", "content": "之前的回复"}
        ],
        "language": "zh-CN",  // 可选，对话语言
        "temperature": 0.7,   // 可选，创造性程度 0-1
        "max_tokens": 1000    // 可选，最大回复长度
    }
    
    Returns:
        AI助手回复
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        message = data.get("message")
        if not message or not message.strip():
            return error_response(PARAMETER_ERROR, "消息内容不能为空")
        
        context = data.get("context", [])
        language = data.get("language")
        temperature = data.get("temperature", 0.7)
        max_tokens = data.get("max_tokens", 1000)
        
        # 验证参数
        if not isinstance(context, list):
            return error_response(PARAMETER_ERROR, "context必须是数组类型")
        
        if not (0 <= temperature <= 1):
            return error_response(PARAMETER_ERROR, "temperature必须在0-1之间")
        
        if not (1 <= max_tokens <= 4000):
            return error_response(PARAMETER_ERROR, "max_tokens必须在1-4000之间")
        
        # 获取用户语言偏好
        db_session = get_db_session()
        preferences_repo = UserPreferencesRepository(db_session)
        preferences_service = UserPreferencesService(preferences_repo)
        
        if not language:
            language = preferences_service.get_user_preference(
                user_id, "language", "preferred_language"
            ) or "zh-CN"
        
        # 构建消息历史
        messages = []
        
        # 添加系统提示
        system_prompt = f"""你是一个智能的RSS阅读助手，主要帮助用户处理和分析新闻文章。你的能力包括：
1. 文章概括和翻译
2. 新闻分析和解读
3. 热点话题讨论
4. 阅读建议和推荐

请用{language}语言回复用户。保持友好、专业、有帮助的语调。"""
        
        messages.append({"role": "system", "content": system_prompt})
        
        # 添加对话历史
        for ctx_msg in context:
            if isinstance(ctx_msg, dict) and "role" in ctx_msg and "content" in ctx_msg:
                if ctx_msg["role"] in ["user", "assistant"]:
                    messages.append(ctx_msg)
        
        # 添加当前消息
        messages.append({"role": "user", "content": message})
        
        # 调用AI生成回复
        provider = LLMProviderFactory.create_provider()
        
        response = provider.generate_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        assistant_reply = response.get("message", {}).get("content", "").strip()
        
        if not assistant_reply:
            return error_response(PARAMETER_ERROR, "AI助手回复生成失败")
        
        result = {
            "message": assistant_reply,
            "language": language,
            "model": response.get("model"),
            "usage": response.get("usage", {}),
            "finish_reason": response.get("finish_reason")
        }
        
        return success_response(result, "对话成功")
        
    except ValidationException as e:
        logger.warning(f"AI助手对话失败 - 参数验证错误: {str(e)}")
        return error_response(e.code, e.message)
    except Exception as e:
        logger.error(f"AI助手对话失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"对话失败: {str(e)}")

@assistant_general_bp.route("/capabilities", methods=["GET"])
@client_auth_required
def get_assistant_capabilities():
    """获取AI助手能力列表
    
    Returns:
        AI助手能力信息
    """
    try:
        capabilities = {
            "article_processing": {
                "name": "文章处理",
                "description": "提供文章概括、翻译、分析等功能",
                "features": [
                    {"key": "summarize", "name": "文章概括", "description": "生成文章摘要"},
                    {"key": "translate", "name": "文章翻译", "description": "翻译文章内容"},
                    {"key": "analyze", "name": "文章分析", "description": "分析文章情感、主题等"}
                ]
            },
            "general_chat": {
                "name": "智能对话",
                "description": "与AI助手进行自然语言对话",
                "features": [
                    {"key": "chat", "name": "对话交流", "description": "自然语言对话"},
                    {"key": "context", "name": "上下文理解", "description": "维持对话上下文"},
                    {"key": "multilingual", "name": "多语言支持", "description": "支持多种语言对话"}
                ]
            },
            "news_analysis": {
                "name": "新闻分析",
                "description": "分析和解读新闻内容",
                "features": [
                    {"key": "trend_analysis", "name": "趋势分析", "description": "分析新闻趋势"},
                    {"key": "topic_extraction", "name": "主题提取", "description": "提取新闻主题"},
                    {"key": "sentiment_analysis", "name": "情感分析", "description": "分析新闻情感倾向"}
                ]
            }
        }
        
        # 获取支持的语言
        from app.domains.assistant.services.article_service import AssistantArticleService
        supported_languages = AssistantArticleService.LANGUAGE_MAPPING
        
        result = {
            "capabilities": capabilities,
            "supported_languages": supported_languages,
            "version": "1.0.0",
            "last_updated": "2024-01-20"
        }
        
        return success_response(result)
        
    except Exception as e:
        logger.error(f"获取AI助手能力失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取能力信息失败: {str(e)}")

@assistant_general_bp.route("/quick_actions", methods=["GET"])
@client_auth_required
def get_quick_actions():
    """获取快捷操作列表
    
    Returns:
        快捷操作列表
    """
    try:
        user_id = g.user_id
        
        # 获取用户语言偏好
        db_session = get_db_session()
        preferences_repo = UserPreferencesRepository(db_session)
        preferences_service = UserPreferencesService(preferences_repo)
        
        preferred_language = preferences_service.get_user_preference(
            user_id, "language", "preferred_language"
        ) or "zh-CN"
        
        # 根据语言提供不同的快捷操作
        if preferred_language.startswith("zh"):
            quick_actions = [
                {
                    "id": "daily_summary",
                    "title": "今日要闻概览",
                    "description": "生成今天的新闻摘要",
                    "icon": "📰",
                    "action": "chat",
                    "message": "请帮我总结今天的重要新闻"
                },
                {
                    "id": "trend_analysis",
                    "title": "热点趋势分析",
                    "description": "分析当前热点话题",
                    "icon": "📈",
                    "action": "chat",
                    "message": "请分析当前的热点趋势"
                },
                {
                    "id": "reading_recommendation",
                    "title": "阅读推荐",
                    "description": "根据兴趣推荐文章",
                    "icon": "🎯",
                    "action": "chat",
                    "message": "根据我的阅读历史，推荐一些有趣的文章"
                },
                {
                    "id": "explain_complex",
                    "title": "深度解读",
                    "description": "解释复杂新闻事件",
                    "icon": "🔍",
                    "action": "chat",
                    "message": "请帮我深度解读最近的重要新闻事件"
                }
            ]
        else:
            quick_actions = [
                {
                    "id": "daily_summary",
                    "title": "Daily News Overview",
                    "description": "Generate today's news summary",
                    "icon": "📰",
                    "action": "chat",
                    "message": "Please help me summarize today's important news"
                },
                {
                    "id": "trend_analysis",
                    "title": "Trend Analysis",
                    "description": "Analyze current hot topics",
                    "icon": "📈",
                    "action": "chat",
                    "message": "Please analyze current trending topics"
                },
                {
                    "id": "reading_recommendation",
                    "title": "Reading Recommendation",
                    "description": "Recommend articles based on interests",
                    "icon": "🎯",
                    "action": "chat",
                    "message": "Based on my reading history, recommend some interesting articles"
                },
                {
                    "id": "explain_complex",
                    "title": "In-depth Analysis",
                    "description": "Explain complex news events",
                    "icon": "🔍",
                    "action": "chat",
                    "message": "Please help me understand recent important news events in depth"
                }
            ]
        
        return success_response({
            "quick_actions": quick_actions,
            "language": preferred_language
        })
        
    except Exception as e:
        logger.error(f"获取快捷操作失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取快捷操作失败: {str(e)}")

@assistant_general_bp.route("/health", methods=["GET"])
@client_auth_required
def health_check():
    """AI助手健康检查
    
    Returns:
        健康状态信息
    """
    try:
        # 检查AI提供商连接状态
        try:
            provider = LLMProviderFactory.create_provider()
            ai_status = provider.health_check()
            provider_name = provider.get_provider_name()
        except Exception as e:
            ai_status = False
            provider_name = "Unknown"
            logger.warning(f"AI提供商健康检查失败: {str(e)}")
        
        result = {
            "status": "healthy" if ai_status else "degraded",
            "ai_provider": {
                "name": provider_name,
                "status": "online" if ai_status else "offline"
            },
            "features": {
                "article_processing": True,
                "general_chat": ai_status,
                "multilingual": True
            },
            "timestamp": "2024-01-20T10:00:00Z"
        }
        
        return success_response(result)
        
    except Exception as e:
        logger.error(f"AI助手健康检查失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"健康检查失败: {str(e)}")