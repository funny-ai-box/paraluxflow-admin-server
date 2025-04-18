"""自定义异常类"""
from app.core.status_codes import PARAMETER_ERROR

class APIException(Exception):
    """API异常基类"""

    def __init__(self, message, code=60000, http_status_code=400):
        self.message = message
        self.code = code
        self.http_status_code = http_status_code
        super().__init__(self.message)


# 具体异常示例
class NotFoundException(APIException):
    """资源未找到异常"""

    def __init__(self, message="资源未找到"):
        from app.core.status_codes import NOT_FOUND

        super().__init__(message, NOT_FOUND, 404)


class AuthenticationException(APIException):
    """认证失败异常"""

    def __init__(self, message="认证失败"):
        from app.core.status_codes import AUTH_FAILED

        super().__init__(message, AUTH_FAILED, 403)


class ValidationException(APIException):
    """数据验证失败异常"""

    def __init__(self, message="数据验证失败",err_code=PARAMETER_ERROR):
        

        super().__init__(message, err_code, 200)


class ConflictException(APIException):
    """资源冲突异常"""

    def __init__(self, message="资源已存在"):
        from app.core.status_codes import PARAMETER_ERROR

        super().__init__(message, PARAMETER_ERROR, 409)
