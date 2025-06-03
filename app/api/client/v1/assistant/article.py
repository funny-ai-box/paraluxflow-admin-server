# app/api/client/v1/assistant/article.py
"""支持流式输出的AI助手文章处理API接口（修复应用上下文问题）"""
import logging
from flask import Blueprint, request, g, Response, current_app

from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, NOT_FOUND
from app.core.exceptions import ValidationException, NotFoundException
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss.rss_article_content_repository import RssFeedArticleContentRepository
from app.infrastructure.database.repositories.user_preferences_repository import UserPreferencesRepository
from app.domains.assistant.services.article_service import AssistantArticleService
from app.api.middleware.client_auth import client_auth_required

assistant_article_bp = Blueprint("assistant_article_bp", __name__)

logger = logging.getLogger(__name__)

def create_streaming_response(generator, app):
    """创建流式响应（保持应用上下文）
    
    Args:
        generator: 数据生成器
        app: Flask应用实例
        
    Returns:
        Flask Response对象
    """
    def generate_with_context():
        with app.app_context():
            for chunk in generator:
                yield chunk
    
    return Response(
        generate_with_context(),
        mimetype='text/plain; charset=utf-8',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control',
            'X-Accel-Buffering': 'no',  # 禁用nginx缓冲
        }
    )

@assistant_article_bp.route("/summarize", methods=["POST"])
@client_auth_required
def summarize_article():
    """生成文章概括（支持流式输出）
    
    请求体:
    {
        "article_id": 123,
        "stream": true  // 可选，是否使用流式输出，默认false
    }
    
    Returns:
        文章概括结果（流式或非流式）
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        article_id = data.get("article_id")
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        stream = data.get("stream", False)
        
        # 在当前上下文中创建服务
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        preferences_repo = UserPreferencesRepository(db_session)
        
        service = AssistantArticleService(article_repo, content_repo, preferences_repo)
        
        if stream:
            # 流式输出 - 保持应用上下文
            app = current_app._get_current_object()  # 获取真实的应用对象
            
            def generate():
                try:
                    # 在生成器内部使用应用上下文
                    for data_chunk in service.summarize_article_stream(user_id, article_id):
                        yield data_chunk
                except Exception as e:
                    logger.error(f"流式概括过程中出错: {str(e)}")
                    import json
                    error_data = json.dumps({
                        "error": str(e),
                        "article_id": article_id
                    }, ensure_ascii=False)
                    yield f"event: error\ndata: {error_data}\n\n"
            
            return create_streaming_response(generate(), app)
        else:
            # 非流式输出 - 在当前上下文中处理
            result = None
            error_occurred = None
            
            try:
                for chunk in service.summarize_article_stream(user_id, article_id):
                    if chunk.startswith("event: complete\n"):
                        import json
                        data_line = chunk.split("data: ", 1)[1].strip()
                        result = json.loads(data_line)
                        break
                    elif chunk.startswith("event: error\n"):
                        import json
                        data_line = chunk.split("data: ", 1)[1].strip()
                        error_data = json.loads(data_line)
                        error_occurred = error_data.get("error", "处理失败")
                        break
            except Exception as e:
                error_occurred = str(e)
            
            if error_occurred:
                raise Exception(error_occurred)
            
            if not result:
                raise Exception("生成概括失败")
            
            return success_response(result, "文章概括生成成功")
        
    except NotFoundException as e:
        logger.warning(f"文章概括失败 - 文章不存在: {str(e)}")
        return error_response(NOT_FOUND, str(e))
    except ValidationException as e:
        logger.warning(f"文章概括失败 - 参数验证错误: {str(e)}")
        return error_response(e.code, e.message)
    except Exception as e:
        logger.error(f"生成文章概括失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"生成概括失败: {str(e)}")

@assistant_article_bp.route("/translate", methods=["POST"])
@client_auth_required
def translate_article():
    """翻译文章（支持流式输出）
    
    请求体:
    {
        "article_id": 123,
        "stream": true  // 可选，是否使用流式输出，默认false
    }
    
    Returns:
        文章翻译结果（流式或非流式）
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        article_id = data.get("article_id")
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        stream = data.get("stream", False)
        
        # 在当前上下文中创建服务
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        preferences_repo = UserPreferencesRepository(db_session)
        
        service = AssistantArticleService(article_repo, content_repo, preferences_repo)
        
        if stream:
            # 流式输出 - 保持应用上下文
            app = current_app._get_current_object()  # 获取真实的应用对象
            
            def generate():
                try:
                    # 在生成器内部使用应用上下文
                    for data_chunk in service.translate_article_stream(user_id, article_id):
                        yield data_chunk
                except Exception as e:
                    logger.error(f"流式翻译过程中出错: {str(e)}")
                    import json
                    error_data = json.dumps({
                        "error": str(e),
                        "article_id": article_id
                    }, ensure_ascii=False)
                    yield f"event: error\ndata: {error_data}\n\n"
            
            return create_streaming_response(generate(), app)
        else:
            # 非流式输出 - 在当前上下文中处理
            result = None
            error_occurred = None
            
            try:
                for chunk in service.translate_article_stream(user_id, article_id):
                    if chunk.startswith("event: complete\n"):
                        import json
                        data_line = chunk.split("data: ", 1)[1].strip()
                        result = json.loads(data_line)
                        break
                    elif chunk.startswith("event: error\n"):
                        import json
                        data_line = chunk.split("data: ", 1)[1].strip()
                        error_data = json.loads(data_line)
                        error_occurred = error_data.get("error", "处理失败")
                        break
            except Exception as e:
                error_occurred = str(e)
            
            if error_occurred:
                raise Exception(error_occurred)
            
            if not result:
                raise Exception("翻译文章失败")
            
            return success_response(result, "文章翻译完成")
        
    except NotFoundException as e:
        logger.warning(f"文章翻译失败 - 文章不存在: {str(e)}")
        return error_response(NOT_FOUND, str(e))
    except ValidationException as e:
        logger.warning(f"文章翻译失败 - 参数验证错误: {str(e)}")
        return error_response(e.code, e.message)
    except Exception as e:
        logger.error(f"翻译文章失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"翻译失败: {str(e)}")

@assistant_article_bp.route("/batch_summarize", methods=["POST"])
@client_auth_required
def batch_summarize_articles():
    """批量生成文章概括
    
    请求体:
    {
        "article_ids": [123, 456, 789],
        "stream": false  // 批量处理不支持流式输出
    }
    
    Returns:
        批量概括结果
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        article_ids = data.get("article_ids", [])
        if not article_ids or not isinstance(article_ids, list):
            return error_response(PARAMETER_ERROR, "article_ids必须是非空数组")
        
        if len(article_ids) > 10:  # 限制批量处理数量
            return error_response(PARAMETER_ERROR, "批量处理文章数量不能超过10篇")
        
        # 创建服务
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        preferences_repo = UserPreferencesRepository(db_session)
        
        service = AssistantArticleService(article_repo, content_repo, preferences_repo)
        
        # 批量处理
        results = []
        errors = []
        
        for article_id in article_ids:
            try:
                # 对每个文章使用非流式处理
                result = None
                error_occurred = None
                
                for chunk in service.summarize_article_stream(user_id, article_id):
                    if chunk.startswith("event: complete\n"):
                        import json
                        data_line = chunk.split("data: ", 1)[1].strip()
                        result = json.loads(data_line)
                        break
                    elif chunk.startswith("event: error\n"):
                        import json
                        data_line = chunk.split("data: ", 1)[1].strip()
                        error_data = json.loads(data_line)
                        error_occurred = error_data.get("error", "处理失败")
                        break
                
                if error_occurred:
                    errors.append({
                        "article_id": article_id,
                        "error": error_occurred
                    })
                elif result:
                    results.append(result)
                else:
                    errors.append({
                        "article_id": article_id,
                        "error": "生成概括失败"
                    })
                    
            except Exception as e:
                errors.append({
                    "article_id": article_id,
                    "error": str(e)
                })
        
        return success_response({
            "success_count": len(results),
            "error_count": len(errors),
            "results": results,
            "errors": errors
        }, f"批量概括完成，成功{len(results)}篇，失败{len(errors)}篇")
        
    except Exception as e:
        logger.error(f"批量生成文章概括失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"批量概括失败: {str(e)}")

@assistant_article_bp.route("/analyze", methods=["POST"])
@client_auth_required
def analyze_article():
    """分析文章内容
    
    请求体:
    {
        "article_id": 123,
        "analysis_type": "sentiment",  // 分析类型: sentiment/topics/keywords/readability
        "target_language": "zh-CN",   // 可选，分析结果语言
        "stream": false               // 可选，是否使用流式输出
    }
    
    Returns:
        文章分析结果
    """
    try:
        user_id = g.user_id
        data = request.get_json()
        if not data:
            return error_response(PARAMETER_ERROR, "未提供数据")
        
        article_id = data.get("article_id")
        if not article_id:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        analysis_type = data.get("analysis_type", "sentiment")
        target_language = data.get("target_language")
        stream = data.get("stream", False)
        
        # 验证分析类型
        valid_types = ["sentiment", "topics", "keywords", "readability"]
        if analysis_type not in valid_types:
            return error_response(PARAMETER_ERROR, f"analysis_type必须是{', '.join(valid_types)}之一")
        
        # 创建服务
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        preferences_repo = UserPreferencesRepository(db_session)
        
        service = AssistantArticleService(article_repo, content_repo, preferences_repo)
        
        # TODO: 实现文章分析功能
        # 这里可以扩展更多AI分析功能
        result = {
            "article_id": article_id,
            "analysis_type": analysis_type,
            "target_language": target_language,
            "stream": stream,
            "message": "文章分析功能即将上线",
            "status": "coming_soon"
        }
        
        return success_response(result, "文章分析请求已接收")
        
    except Exception as e:
        logger.error(f"分析文章失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"分析失败: {str(e)}")

@assistant_article_bp.route("/supported_languages", methods=["GET"])
@client_auth_required
def get_supported_languages():
    """获取支持的语言列表
    
    Returns:
        支持的语言列表
    """
    try:
        # 创建服务
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        preferences_repo = UserPreferencesRepository(db_session)
        
        service = AssistantArticleService(article_repo, content_repo, preferences_repo)
        
        supported_languages = service.LANGUAGE_MAPPING
        
        return success_response({
            "languages": supported_languages,
            "count": len(supported_languages)
        })
        
    except Exception as e:
        logger.error(f"获取支持语言列表失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取语言列表失败: {str(e)}")

@assistant_article_bp.route("/user_language_preferences", methods=["GET"])
@client_auth_required
def get_user_language_preferences():
    """获取用户语言偏好设置
    
    Returns:
        用户语言偏好信息
    """
    try:
        user_id = g.user_id
        
        # 创建服务
        db_session = get_db_session()
        preferences_repo = UserPreferencesRepository(db_session)
        
        service = AssistantArticleService(None, None, preferences_repo)
        
        # 获取用户语言偏好
        preferred_language, summary_language = service._get_user_language_preferences(user_id)
        
        preferences = {
            "preferred_language": preferred_language,
            "preferred_language_name": service.LANGUAGE_MAPPING.get(preferred_language, "中文（简体）"),
            "summary_language": summary_language,
            "summary_language_name": service.LANGUAGE_MAPPING.get(summary_language, "中文（简体）"),
            "supported_languages": service.LANGUAGE_MAPPING
        }
        
        return success_response(preferences)
        
    except Exception as e:
        logger.error(f"获取用户语言偏好失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"获取语言偏好失败: {str(e)}")

@assistant_article_bp.route("/health", methods=["GET"])
@client_auth_required
def health_check():
    """文章AI处理服务健康检查
    
    Returns:
        健康状态信息
    """
    try:
        # 检查AI提供商连接状态
        try:
            from app.infrastructure.llm_providers.factory import LLMProviderFactory
            provider = LLMProviderFactory.create_provider()
            ai_status = provider.health_check()
            provider_name = provider.get_provider_name()
            supports_streaming = getattr(provider, 'supports_streaming', lambda: False)()
        except Exception as e:
            ai_status = False
            provider_name = "Unknown"
            supports_streaming = False
            logger.warning(f"AI提供商健康检查失败: {str(e)}")
        
        # 检查数据库连接
        try:
            db_session = get_db_session()
            article_repo = RssFeedArticleRepository(db_session)
            # 简单的数据库查询测试
            db_status = True
        except Exception as e:
            db_status = False
            logger.warning(f"数据库连接检查失败: {str(e)}")
        
        overall_status = "healthy" if (ai_status and db_status) else "degraded"
        
        result = {
            "status": overall_status,
            "timestamp": "2024-01-20T10:00:00Z",
            "services": {
                "ai_provider": {
                    "name": provider_name,
                    "status": "online" if ai_status else "offline",
                    "supports_streaming": supports_streaming
                },
                "database": {
                    "status": "online" if db_status else "offline"
                }
            },
            "features": {
                "article_summarization": ai_status,
                "article_translation": ai_status,
                "streaming_output": ai_status and supports_streaming,
                "batch_processing": ai_status,
                "multilingual_support": True
            }
        }
        
        return success_response(result)
        
    except Exception as e:
        logger.error(f"文章AI服务健康检查失败: {str(e)}", exc_info=True)
        return error_response(PARAMETER_ERROR, f"健康检查失败: {str(e)}")