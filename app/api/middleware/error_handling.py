from flask import jsonify
from app.core.status_codes import SUCCESS, UNKNOWN_ERROR

def handle_exception(e):
    """全局异常处理器"""
    # 记录错误
    # current_app.logger.error(f"Unhandled exception: {str(e)}")
    
    # 获取业务状态码，默认为未知错误
    code = getattr(e, 'code', UNKNOWN_ERROR)
    
    # 返回JSON格式的错误响应
    response = {
        "code": code,
        "message": str(e),
        "data": None
    }
    
    # 确定HTTP状态码，默认为500
    http_status_code = getattr(e, 'http_status_code', 500)
    
    return jsonify(response), http_status_code