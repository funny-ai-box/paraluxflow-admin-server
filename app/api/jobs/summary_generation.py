# app/api/jobs/summary_generation.py
"""摘要生成API接口"""
import logging
from flask import Blueprint, request
from app.api.middleware.app_key_auth import app_key_required
from app.core.responses import success_response, error_response
from app.core.status_codes import PARAMETER_ERROR, EXTERNAL_API_ERROR
from app.infrastructure.database.session import get_db_session

# 仓库导入
from app.infrastructure.database.repositories.rss.rss_article_repository import RssFeedArticleRepository
from app.infrastructure.database.repositories.rss.rss_article_content_repository import RssFeedArticleContentRepository

# 服务导入
from app.domains.rss.services.summary_generation_service import SummaryGenerationService

logger = logging.getLogger(__name__)

# 创建摘要生成蓝图
summary_generation_bp = Blueprint("summary_generation", __name__)

@summary_generation_bp.route("/generate_summary", methods=["POST"])
@app_key_required
def generate_summary():
    """生成摘要接口
    
    请求参数:
        article_id: 文章ID
        provider_name: LLM提供商名称(可选)
        
    返回:
        chinese_summary: 中文摘要
        english_summary: 英文摘要
        original_summary_updated: 是否更新了原始摘要
    """
    try:
        data = request.get_json()
        if not data or "article_id" not in data:
            return error_response(PARAMETER_ERROR, "缺少article_id参数")
        
        article_id = data["article_id"]
        provider_name = data.get("provider_name")
        
        print(f"开始为文章 {article_id} 生成双语摘要...")
        
        # 创建数据库会话和仓库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        
        # 创建摘要生成服务
        summary_service = SummaryGenerationService(article_repo, content_repo)
        
        # 生成双语摘要
        err, result = summary_service.generate_article_summaries(article_id, provider_name)
        
        if err:
            return error_response(EXTERNAL_API_ERROR, err)
        
        return success_response(result, "双语摘要生成成功")
        
    except Exception as e:
        logger.error(f"生成摘要失败: {str(e)}")
        return error_response(EXTERNAL_API_ERROR, f"生成摘要失败: {str(e)}")


@summary_generation_bp.route("/update_article_step", methods=["POST"])
@app_key_required
def update_article_step():
    """更新文章处理步骤状态
    
    请求参数:
        article_id: 文章ID
        step: 处理步骤 (content_saved, summary_generated, vectorized)
        status: 状态 (success, failed)
        data: 相关数据
        error_message: 错误信息(如果失败)
    """
    try:
        data = request.get_json()
        if not data or "article_id" not in data or "step" not in data:
            return error_response(PARAMETER_ERROR, "缺少必要参数")
        
        article_id = data["article_id"]
        step = data["step"]
        status = data.get("status", "success")
        step_data = data.get("data", {})
        error_message = data.get("error_message")
        
        print(f"更新文章 {article_id} 的处理步骤: {step} - {status}")
        
        # 创建数据库会话和仓库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        
        # 创建摘要生成服务
        summary_service = SummaryGenerationService(article_repo, content_repo)
        
        # 更新步骤状态
        err, result = summary_service.update_article_processing_step(
            article_id, step, status, step_data, error_message
        )
        
        if err:
            return error_response(EXTERNAL_API_ERROR, err)
        
        return success_response(result, "步骤状态更新成功")
        
    except Exception as e:
        logger.error(f"更新文章步骤失败: {str(e)}")
        return error_response(EXTERNAL_API_ERROR, f"更新失败: {str(e)}")


@summary_generation_bp.route("/batch_generate_summary", methods=["POST"])
@app_key_required
def batch_generate_summary():
    """批量生成摘要接口
    
    请求参数:
        article_ids: 文章ID列表
        provider_name: LLM提供商名称(可选)
        
    返回:
        success_count: 成功数量
        failed_count: 失败数量
        results: 详细结果列表
    """
    try:
        data = request.get_json()
        if not data or "article_ids" not in data:
            return error_response(PARAMETER_ERROR, "缺少article_ids参数")
        
        article_ids = data["article_ids"]
        provider_name = data.get("provider_name")
        
        if not isinstance(article_ids, list) or len(article_ids) == 0:
            return error_response(PARAMETER_ERROR, "article_ids必须是非空列表")
        
        if len(article_ids) > 50:  # 限制批量处理数量
            return error_response(PARAMETER_ERROR, "单次最多处理50篇文章")
        
        print(f"开始批量生成摘要，文章数量: {len(article_ids)}")
        
        # 创建数据库会话和仓库
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        
        # 创建摘要生成服务
        summary_service = SummaryGenerationService(article_repo, content_repo)
        
        # 批量处理
        results = []
        success_count = 0
        failed_count = 0
        
        for article_id in article_ids:
            try:
                err, result = summary_service.generate_article_summaries(article_id, provider_name)
                
                if err:
                    results.append({
                        "article_id": article_id,
                        "status": "failed",
                        "error": err
                    })
                    failed_count += 1
                else:
                    results.append({
                        "article_id": article_id,
                        "status": "success",
                        "chinese_summary": result.get("chinese_summary"),
                        "english_summary": result.get("english_summary"),
                        "original_summary_updated": result.get("original_summary_updated")
                    })
                    success_count += 1
                    
            except Exception as e:
                results.append({
                    "article_id": article_id,
                    "status": "failed",
                    "error": str(e)
                })
                failed_count += 1
        
        response_data = {
            "total_count": len(article_ids),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results,
            "provider_used": provider_name or "default"
        }
        
        return success_response(response_data, f"批量处理完成，成功{success_count}篇，失败{failed_count}篇")
        
    except Exception as e:
        logger.error(f"批量生成摘要失败: {str(e)}")
        return error_response(EXTERNAL_API_ERROR, f"批量处理失败: {str(e)}")


@summary_generation_bp.route("/validate_summary", methods=["POST"])
@app_key_required
def validate_summary():
    """验证摘要有效性接口
    
    请求参数:
        summary: 摘要内容
        
    返回:
        is_valid: 是否有效
        reason: 无效原因(如果无效)
    """
    try:
        data = request.get_json()
        if not data or "summary" not in data:
            return error_response(PARAMETER_ERROR, "缺少summary参数")
        
        summary = data["summary"]
        
        # 创建摘要生成服务
        db_session = get_db_session()
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        summary_service = SummaryGenerationService(article_repo, content_repo)
        
        # 验证摘要
        is_valid = not summary_service.is_invalid_summary(summary)
        
        result = {
            "summary": summary,
            "is_valid": is_valid,
            "length": len(summary) if summary else 0
        }
        
        if not is_valid:
            # 分析无效原因
            if not summary or not isinstance(summary, str):
                result["reason"] = "摘要为空或类型错误"
            elif len(summary.strip()) < 10:
                result["reason"] = "摘要长度过短（少于10字符）"
            else:
                result["reason"] = "包含无效内容模式（如'查看原文'等）"
        
        return success_response(result, "摘要验证完成")
        
    except Exception as e:
        logger.error(f"验证摘要失败: {str(e)}")
        return error_response(EXTERNAL_API_ERROR, f"验证失败: {str(e)}")


@summary_generation_bp.route("/health", methods=["GET"])
@app_key_required
def health_check():
    """摘要生成服务健康检查"""
    try:
        # 创建数据库会话测试连接
        db_session = get_db_session()
        
        # 测试LLM提供商连接
        from app.infrastructure.llm_providers.factory import LLMProviderFactory
        try:
            llm_provider = LLMProviderFactory.create_provider()
            llm_healthy = llm_provider.health_check()
        except Exception as e:
            llm_healthy = False
            logger.warning(f"LLM提供商健康检查失败: {str(e)}")
        
        health_status = {
            "service": "summary_generation",
            "status": "healthy" if llm_healthy else "degraded",
            "database": "connected",
            "llm_provider": "healthy" if llm_healthy else "unhealthy",
            "timestamp": request.json.get("timestamp") if request.json else None
        }
        
        return success_response(health_status, "健康检查完成")
        
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return error_response(EXTERNAL_API_ERROR, f"健康检查失败: {str(e)}")