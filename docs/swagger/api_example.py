"""API文档示例"""
from flask import Blueprint, request
from app.core.responses import success_response
from app.utils.swagger_utils import document_api

# 创建蓝图
example_bp = Blueprint("example", __name__)

@example_bp.route("/hello", methods=["GET"])
@document_api("example/hello.yml")
def hello():
    """Hello World示例接口"""
    name = request.args.get("name", "World")
    return success_response({"message": f"Hello, {name}!"})

@example_bp.route("/create", methods=["POST"])
@document_api("example/create.yml")
def create():
    """创建示例接口"""
    data = request.get_json()
    if not data:
        return success_response(None, "请求数据不能为空", 10001)
    
    name = data.get("name")
    if not name:
        return success_response(None, "缺少name参数", 10001)
    
    return success_response({"id": 1, "name": name, "created_at": "2023-01-01T12:00:00"}, "创建成功")
