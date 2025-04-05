# 通用成功响应
success_response_schema = {
    "type": "object",
    "properties": {
        "code": {"type": "integer", "example": 200},
        "message": {"type": "string", "example": "操作成功"},
        "data": {"type": "object"}
    }
}

# 通用错误响应
error_response_schema = {
    "type": "object",
    "properties": {
        "code": {"type": "integer", "example": 10001},
        "message": {"type": "string", "example": "操作失败"},
        "data": {"type": "null"}
    }
}

# 分页响应
paginated_response_schema = {
    "type": "object",
    "properties": {
        "code": {"type": "integer", "example": 200},
        "message": {"type": "string", "example": "操作成功"},
        "data": {
            "type": "object",
            "properties": {
                "list": {"type": "array"},
                "total": {"type": "integer"},
                "pages": {"type": "integer"},
                "current_page": {"type": "integer"},
                "per_page": {"type": "integer"}
            }
        }
    }
}