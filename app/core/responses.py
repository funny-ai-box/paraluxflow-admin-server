# app/core/responses.py
from app.core.status_codes import SUCCESS

def success_response(data=None, message="操作成功"):
    """生成标准成功响应"""
    return {
        "code": SUCCESS,
        "message": message,
        "data": data
    }