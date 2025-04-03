"""摘要API控制器"""
# 更新digest.py的内容，移除对LLMProviderConfigRepository的引用
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from flask import Blueprint, request, g, jsonify
from werkzeug.exceptions import BadRequest

from app.api.middleware.auth import auth_required
from app.core.responses import success_response, error_response
from app.core.exceptions import ValidationException, NotFoundException
from app.core.status_codes import PARAMETER_ERROR
from app.infrastructure.database.session import get_db_session
from app.infrastructure.database.repositories.digest_repository import DigestRepository
from app.infrastructure.database.repositories.rss_repository import RssFeedArticleRepository, RssFeedArticleContentRepository
from app.domains.digest.services.digest_service import DigestService

logger = logging.getLogger(__name__)

# 创建蓝图
digest_bp = Blueprint("digest", __name__)


@digest_bp.route("/list", methods=["GET"])
@auth_required
def get_digest_list():
    """获取摘要列表
    
    支持的查询参数:
    - page: 页码，默认1
    - per_page: 每页数量，默认10
    - digest_type: 摘要类型，如daily, weekly
    - status: 状态
    - start_date: 开始日期
    - end_date: 结束日期
    - title: 标题关键词
    
    Returns:
        摘要列表和分页信息
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取分页参数
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        
        # 构建筛选条件
        filters = {}
        
        # 摘要类型筛选
        digest_type = request.args.get("digest_type")
        if digest_type:
            filters["digest_type"] = digest_type
        
        # 状态筛选
        status = request.args.get("status", type=int)
        if status is not None:
            filters["status"] = status
        
        # 日期范围筛选
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        if start_date or end_date:
            filters["date_range"] = (start_date, end_date)
        
        # 标题关键词筛选
        title = request.args.get("title")
        if title:
            filters["title"] = title
        
        # 创建会话和存储库
        db_session = get_db_session()
        digest_repo = DigestRepository(db_session)
        
        # 获取摘要列表
        result = digest_repo.get_digests(user_id, page, per_page, filters)
        
        return success_response(result)
    except Exception as e:
        logger.error(f"获取摘要列表失败: {str(e)}")
        return error_response(40001, f"获取摘要列表失败: {str(e)}")


@digest_bp.route("/detail", methods=["GET"])
@auth_required
def get_digest_detail():
    """获取摘要详情
    
    查询参数:
    - digest_id: 摘要ID
    
    Returns:
        摘要详情
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取摘要ID
        digest_id = request.args.get("digest_id")
        if not digest_id:
            return error_response(40001, "缺少digest_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        digest_repo = DigestRepository(db_session)
        
        # 获取摘要详情
        try:
            result = digest_repo.get_digest_by_id(digest_id, user_id)
            return success_response(result)
        except NotFoundException as e:
            return error_response(40004, str(e))
    except Exception as e:
        logger.error(f"获取摘要详情失败: {str(e)}")
        return error_response(40001, f"获取摘要详情失败: {str(e)}")


@digest_bp.route("/generate", methods=["POST"])
@auth_required
def generate_digest():
    """生成摘要
    
    请求体:
    {
        "date": "2023-01-01", // 可选，不提供则使用前一天
        "rule_id": "rule_id", // 可选，不提供则使用默认规则
        "digest_type": "daily" // 可选，默认为daily
    }
    
    Returns:
        生成结果
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取请求数据
        data = request.get_json() or {}
        
        # 解析日期
        date_str = data.get("date")
        date = None
        if date_str:
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return error_response(40001, "日期格式无效，请使用YYYY-MM-DD格式")
        
        # 获取规则ID
        rule_id = data.get("rule_id")
        
        # 获取摘要类型
        digest_type = data.get("digest_type", "daily")
        if digest_type not in ["daily", "weekly", "custom"]:
            return error_response(40001, "摘要类型无效，支持的类型: daily, weekly, custom")
        
        # 创建会话和存储库
        db_session = get_db_session()
        digest_repo = DigestRepository(db_session)
        article_repo = RssFeedArticleRepository(db_session)
        content_repo = RssFeedArticleContentRepository(db_session)
        
        # 初始化服务
        digest_service = DigestService(digest_repo, article_repo, content_repo)
        
        # 生成摘要
        if digest_type == "daily":
            result = digest_service.generate_daily_digest(user_id, date, rule_id)
        else:
            # 其他类型的摘要生成待实现
            return error_response(40001, f"暂不支持{digest_type}类型的摘要生成")
        
        return success_response(result)
    except ValidationException as e:
        return error_response(40001, str(e))
    except Exception as e:
        logger.error(f"生成摘要失败: {str(e)}")
        return error_response(40001, f"生成摘要失败: {str(e)}")


@digest_bp.route("/update", methods=["POST"])
@auth_required
def update_digest():
    """更新摘要
    
    请求体:
    {
        "digest_id": "digest_id", // 必填
        "title": "新标题", // 可选
        "content": "新内容" // 可选
    }
    
    Returns:
        更新结果
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(40001, "请求数据不能为空")
        
        # 验证必填字段
        if "digest_id" not in data:
            return error_response(40001, "缺少digest_id字段")
        
        # 创建会话和存储库
        db_session = get_db_session()
        digest_repo = DigestRepository(db_session)
        
        # 初始化服务
        digest_service = DigestService(digest_repo)
        
        # 更新摘要
        try:
            update_data = {}
            if "title" in data:
                update_data["title"] = data["title"]
            if "content" in data:
                update_data["content"] = data["content"]
            
            result = digest_service.update_digest(data["digest_id"], user_id, update_data)
            return success_response(result)
        except NotFoundException as e:
            return error_response(40004, str(e))
    except Exception as e:
        logger.error(f"更新摘要失败: {str(e)}")
        return error_response(40001, f"更新摘要失败: {str(e)}")


@digest_bp.route("/rules", methods=["GET"])
@auth_required
def get_digest_rules():
    """获取摘要规则列表
    
    Returns:
        摘要规则列表
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 创建会话和存储库
        db_session = get_db_session()
        digest_repo = DigestRepository(db_session)
        
        # 获取规则列表
        rules = digest_repo.get_digest_rules(user_id)
        
        return success_response(rules)
    except Exception as e:
        logger.error(f"获取摘要规则列表失败: {str(e)}")
        return error_response(40001, f"获取摘要规则列表失败: {str(e)}")


@digest_bp.route("/rule/update", methods=["POST"])
@auth_required
def update_digest_rule():
    """更新摘要规则
    
    请求体:
    {
        "id": "rule_id", // 可选，不提供则创建新规则
        "name": "规则名称", // 必填
        "digest_type": "daily", // 可选，默认为daily
        "feed_filter": {...}, // 可选
        "article_filter": {...}, // 可选
        "summary_length": 300, // 可选
        "include_categories": true, // 可选
        "include_keywords": true, // 可选
        
        // LLM 配置
        "provider_type": "openai", // 可选，AI提供商类型
        "model_id": "gpt-4o", // 可选，模型ID
        "temperature": 0.7, // 可选，温度参数
        "max_tokens": 1500, // 可选，最大生成token数
        "top_p": 1.0, // 可选，核采样参数
        
        "schedule_time": "03:00", // 可选
        "is_active": true // 可选
    }
    
    Returns:
        更新结果
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取请求数据
        data = request.get_json()
        if not data:
            return error_response(40001, "请求数据不能为空")
        
        # 验证必填字段
        if "name" not in data:
            return error_response(40001, "缺少name字段")
        
        # 创建会话和存储库
        db_session = get_db_session()
        digest_repo = DigestRepository(db_session)
        
        # 初始化服务
        digest_service = DigestService(digest_repo)
        
        # 创建或更新规则
        result = digest_service.create_or_update_rule(user_id, data)
        
        return success_response(result)
    except NotFoundException as e:
        return error_response(40004, str(e))
    except Exception as e:
        logger.error(f"更新摘要规则失败: {str(e)}")
        return error_response(40001, f"更新摘要规则失败: {str(e)}")


@digest_bp.route("/rule/detail", methods=["GET"])
@auth_required
def get_rule_detail():
    """获取摘要规则详情
    
    查询参数:
    - rule_id: 规则ID
    
    Returns:
        规则详情
    """
    try:
        # 获取用户ID
        user_id = g.user_id
        
        # 获取规则ID
        rule_id = request.args.get("rule_id")
        if not rule_id:
            return error_response(40001, "缺少rule_id参数")
        
        # 创建会话和存储库
        db_session = get_db_session()
        digest_repo = DigestRepository(db_session)
        
        # 获取规则详情
        try:
            result = digest_repo.get_digest_rule(rule_id, user_id)
            return success_response(result)
        except NotFoundException as e:
            return error_response(40004, str(e))
    except Exception as e:
        logger.error(f"获取摘要规则详情失败: {str(e)}")
        return error_response(40001, f"获取摘要规则详情失败: {str(e)}")