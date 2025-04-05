#!/bin/bash

# 创建Swagger文档目录
mkdir -p docs/swagger/{auth,rss,digest,llm}

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}开始生成Swagger文档模板...${NC}"

# 处理auth模块
process_auth_files() {
    echo -e "${YELLOW}处理认证模块...${NC}"
    
    # 获取公钥接口
    cat > docs/swagger/auth/get-public-key.yml << EOF
summary: 获取RSA公钥
description: 获取用于加密密码的RSA公钥
tags:
  - 认证
responses:
  200:
    description: 成功获取公钥
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "获取RSA公钥成功"
        data:
          type: object
          properties:
            public_key:
              type: string
              example: "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkq...-----END PUBLIC KEY-----"
EOF
    echo "✅ 已生成 get-public-key.yml"

    # 注册接口
    cat > docs/swagger/auth/register.yml << EOF
summary: 用户注册
description: 使用手机号和密码注册新用户
tags:
  - 认证
parameters:
  - name: body
    in: body
    required: true
    schema:
      type: object
      required:
        - phone
        - password
      properties:
        phone:
          type: string
          description: 手机号
          example: "13800138000"
        password:
          type: string
          description: RSA加密的密码
          example: "加密后的密码字符串"
        username:
          type: string
          description: 用户名(可选)
          example: "张三"
responses:
  200:
    description: 注册成功
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "注册成功"
        data:
          type: object
          properties:
            user:
              type: object
              properties:
                id:
                  type: string
                  example: "a1b2c3d4e5f6"
                username:
                  type: string
                  example: "张三"
                phone:
                  type: string
                  example: "13800138000"
                role:
                  type: integer
                  example: 1
                status:
                  type: integer
                  example: 1
                created_at:
                  type: string
                  format: date-time
                  example: "2023-01-01T12:00:00"
            token:
              type: string
              example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
EOF
    echo "✅ 已生成 register.yml"

    # 登录接口
    cat > docs/swagger/auth/login.yml << EOF
summary: 用户登录
description: 使用手机号和密码登录
tags:
  - 认证
parameters:
  - name: body
    in: body
    required: true
    schema:
      type: object
      required:
        - phone
        - password
      properties:
        phone:
          type: string
          description: 手机号
          example: "13800138000"
        password:
          type: string
          description: RSA加密的密码
          example: "加密后的密码字符串"
responses:
  200:
    description: 登录成功
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "登录成功"
        data:
          type: object
          properties:
            user:
              type: object
              properties:
                id:
                  type: string
                  example: "a1b2c3d4e5f6"
                username:
                  type: string
                  example: "张三"
                phone:
                  type: string
                  example: "13800138000"
                role:
                  type: integer
                  example: 1
                status:
                  type: integer
                  example: 1
                last_login_at:
                  type: string
                  format: date-time
                  example: "2023-01-01T12:00:00"
            token:
              type: string
              example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
EOF
    echo "✅ 已生成 login.yml"

    # 验证令牌接口
    cat > docs/swagger/auth/verify-token.yml << EOF
summary: 验证JWT令牌
description: 验证JWT令牌的有效性
tags:
  - 认证
parameters:
  - name: body
    in: body
    required: true
    schema:
      type: object
      required:
        - token
      properties:
        token:
          type: string
          description: JWT令牌
          example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
responses:
  200:
    description: 验证结果
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "令牌有效"
        data:
          type: object
          properties:
            valid:
              type: boolean
              example: true
            payload:
              type: object
              description: 令牌中的数据(仅当valid为true时)
EOF
    echo "✅ 已生成 verify-token.yml"
}

# 处理RSS模块
process_rss_files() {
    echo -e "${YELLOW}处理RSS模块...${NC}"
    
    # Feed列表接口
    cat > docs/swagger/rss/feed-list.yml << EOF
summary: 获取Feed列表
description: 获取RSS Feed列表，支持分页和筛选
tags:
  - RSS Feed
parameters:
  - name: page
    in: query
    type: integer
    description: 页码，默认1
    required: false
    default: 1
  - name: per_page
    in: query
    type: integer
    description: 每页数量，默认20
    required: false
    default: 20
  - name: title
    in: query
    type: string
    description: Feed标题模糊搜索
    required: false
  - name: category_id
    in: query
    type: integer
    description: 分类ID
    required: false
  - name: is_active
    in: query
    type: integer
    description: 状态(1=启用, 0=禁用)
    required: false
    enum: [0, 1]
responses:
  200:
    description: 获取Feed列表成功
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "操作成功"
        data:
          type: object
          properties:
            list:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                  url:
                    type: string
                  category_id:
                    type: integer
                  logo:
                    type: string
                  title:
                    type: string
                  description:
                    type: string
                  is_active:
                    type: boolean
                  last_fetch_at:
                    type: string
                    format: date-time
                  category:
                    type: object
                    properties:
                      id:
                        type: integer
                      name:
                        type: string
            total:
              type: integer
            pages:
              type: integer
            current_page:
              type: integer
            per_page:
              type: integer
EOF
    echo "✅ 已生成 feed-list.yml"

    # Feed详情接口
    cat > docs/swagger/rss/feed-detail.yml << EOF
summary: 获取Feed详情
description: 根据ID获取Feed详细信息
tags:
  - RSS Feed
parameters:
  - name: feed_id
    in: query
    type: string
    description: Feed ID
    required: true
responses:
  200:
    description: 获取Feed详情成功
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "操作成功"
        data:
          type: object
          properties:
            id:
              type: string
            url:
              type: string
            category_id:
              type: integer
            logo:
              type: string
            title:
              type: string
            description:
              type: string
            is_active:
              type: boolean
            last_fetch_at:
              type: string
              format: date-time
            last_fetch_status:
              type: integer
            last_fetch_error:
              type: string
            last_successful_fetch_at:
              type: string
              format: date-time
            total_articles_count:
              type: integer
            consecutive_failures:
              type: integer
            created_at:
              type: string
              format: date-time
            updated_at:
              type: string
              format: date-time
EOF
    echo "✅ 已生成 feed-detail.yml"

    # 文章列表接口
    cat > docs/swagger/rss/article-list.yml << EOF
summary: 获取文章列表
description: 获取RSS文章列表，支持分页和筛选
tags:
  - RSS 文章
parameters:
  - name: page
    in: query
    type: integer
    description: 页码，默认1
    required: false
    default: 1
  - name: per_page
    in: query
    type: integer
    description: 每页数量，默认10
    required: false
    default: 10
  - name: id
    in: query
    type: integer
    description: 文章ID
    required: false
  - name: feed_id
    in: query
    type: string
    description: Feed ID
    required: false
  - name: status
    in: query
    type: integer
    description: 状态
    required: false
  - name: title
    in: query
    type: string
    description: 标题关键词
    required: false
  - name: start_date
    in: query
    type: string
    format: date
    description: 开始日期
    required: false
  - name: end_date
    in: query
    type: string
    format: date
    description: 结束日期
    required: false
responses:
  200:
    description: 获取文章列表成功
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "操作成功"
        data:
          type: object
          properties:
            list:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  feed_id:
                    type: string
                  feed_title:
                    type: string
                  feed_logo:
                    type: string
                  title:
                    type: string
                  summary:
                    type: string
                  link:
                    type: string
                  published_date:
                    type: string
                    format: date-time
                  status:
                    type: integer
            total:
              type: integer
            pages:
              type: integer
            current_page:
              type: integer
            per_page:
              type: integer
EOF
    echo "✅ 已生成 article-list.yml"
}

# 处理摘要模块
process_digest_files() {
    echo -e "${YELLOW}处理摘要模块...${NC}"
    
    # 摘要列表接口
    cat > docs/swagger/digest/digest-list.yml << EOF
summary: 获取摘要列表
description: 获取文章摘要列表，支持分页和筛选
tags:
  - 摘要
parameters:
  - name: page
    in: query
    type: integer
    description: 页码，默认1
    required: false
    default: 1
  - name: per_page
    in: query
    type: integer
    description: 每页数量，默认10
    required: false
    default: 10
  - name: digest_type
    in: query
    type: string
    description: 摘要类型，如daily, weekly
    required: false
  - name: status
    in: query
    type: integer
    description: 状态
    required: false
  - name: start_date
    in: query
    type: string
    format: date
    description: 开始日期
    required: false
  - name: end_date
    in: query
    type: string
    format: date
    description: 结束日期
    required: false
  - name: title
    in: query
    type: string
    description: 标题关键词
    required: false
responses:
  200:
    description: 获取摘要列表成功
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "操作成功"
        data:
          type: object
          properties:
            list:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                  user_id:
                    type: string
                  title:
                    type: string
                  content:
                    type: string
                  article_count:
                    type: integer
                  source_date:
                    type: string
                    format: date-time
                  digest_type:
                    type: string
                  status:
                    type: integer
                  created_at:
                    type: string
                    format: date-time
            total:
              type: integer
            pages:
              type: integer
            current_page:
              type: integer
            per_page:
              type: integer
EOF
    echo "✅ 已生成 digest-list.yml"

    # 生成摘要接口
    cat > docs/swagger/digest/generate-digest.yml << EOF
summary: 生成摘要
description: 生成文章摘要
tags:
  - 摘要
parameters:
  - name: body
    in: body
    required: true
    schema:
      type: object
      properties:
        date:
          type: string
          format: date
          description: 日期，不提供则使用前一天
          example: "2023-01-01"
        rule_id:
          type: string
          description: 规则ID，不提供则使用默认规则
        digest_type:
          type: string
          description: 摘要类型，默认为daily
          enum: [daily, weekly, custom]
          default: daily
responses:
  200:
    description: 生成摘要成功
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "操作成功"
        data:
          type: object
          properties:
            message:
              type: string
              example: "摘要生成成功"
            digest_id:
              type: string
              example: "a1b2c3d4e5f6"
            title:
              type: string
              example: "2023-01-01阅读摘要"
            article_count:
              type: integer
              example: 10
EOF
    echo "✅ 已生成 generate-digest.yml"
}

# 处理LLM模块
process_llm_files() {
    echo -e "${YELLOW}处理LLM模块...${NC}"
    
    # 获取AI提供商列表接口
    cat > docs/swagger/llm/providers.yml << EOF
summary: 获取AI提供商列表
description: 获取所有LLM提供商
tags:
  - LLM
responses:
  200:
    description: 获取提供商列表成功
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "操作成功"
        data:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              name:
                type: string
                example: "OpenAI"
              provider_type:
                type: string
                example: "openai"
              description:
                type: string
              api_key:
                type: string
                example: "********"
              api_base_url:
                type: string
              default_model:
                type: string
                example: "gpt-4o"
              is_active:
                type: boolean
EOF
    echo "✅ 已生成 providers.yml"

    # 测试AI提供商接口
    cat > docs/swagger/llm/provider-test.yml << EOF
summary: 测试AI提供商连接
description: 测试LLM提供商连接并返回可用模型
tags:
  - LLM
parameters:
  - name: body
    in: body
    required: true
    schema:
      type: object
      required:
        - id
      properties:
        id:
          type: integer
          description: 提供商ID
        api_key:
          type: string
          description: API密钥(不提供则使用数据库中的)
        api_base_url:
          type: string
          description: 覆盖API基础URL
responses:
  200:
    description: 测试结果
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "操作成功"
        data:
          type: object
          properties:
            success:
              type: boolean
              example: true
            provider:
              type: string
              example: "OpenAI"
            models:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                    example: "gpt-4o"
                  created:
                    type: integer
                  owned_by:
                    type: string
                    example: "openai"
EOF
    echo "✅ 已生成 provider-test.yml"
}

# 生成通用定义文件
generate_definitions() {
    echo -e "${YELLOW}生成通用定义文件...${NC}"
    
    cat > docs/swagger/definitions.yml << EOF
definitions:
  Success:
    type: object
    properties:
      code:
        type: integer
        example: 200
      message:
        type: string
        example: "操作成功"
      data:
        type: object
        
  Error:
    type: object
    properties:
      code:
        type: integer
        example: 10001
      message:
        type: string
        example: "操作失败"
      data:
        type: null
        
  Pagination:
    type: object
    properties:
      list:
        type: array
      total:
        type: integer
      pages:
        type: integer
      current_page:
        type: integer
      per_page:
        type: integer
EOF
    echo "✅ 已生成 definitions.yml"
}

# 生成Swagger配置文件
generate_swagger_config() {
    echo -e "${YELLOW}生成Swagger配置文件...${NC}"
    
    cat > docs/swagger/swagger.json << EOF
{
  "swagger": "2.0",
  "info": {
    "title": "IMP API",
    "description": "Intelligent Middleware Platform API Documentation",
    "version": "1.0.0",
    "contact": {
      "email": "example@example.com"
    }
  },
  "basePath": "/api/v1",
  "schemes": [
    "http",
    "https"
  ],
  "tags": [
    {
      "name": "认证",
      "description": "认证相关API"
    },
    {
      "name": "RSS Feed",
      "description": "RSS Feed管理相关API"
    },
    {
      "name": "RSS 文章",
      "description": "RSS文章管理相关API"
    },
    {
      "name": "摘要",
      "description": "文章摘要相关API"
    },
    {
      "name": "LLM",
      "description": "LLM提供商管理相关API"
    }
  ],
  "securityDefinitions": {
    "JWT": {
      "type": "apiKey",
      "name": "Authorization",
      "in": "header",
      "description": "JWT Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\""
    },
    "AppKey": {
      "type": "apiKey",
      "name": "X-App-Key",
      "in": "header",
      "description": "Application API Key"
    }
  }
}
EOF
    echo "✅ 已生成 swagger.json"
}

# 创建安装脚本
create_install_script() {
    echo -e "${YELLOW}创建安装脚本...${NC}"
    
    cat > install_swagger.py << EOF
"""安装Swagger到Flask应用"""
import os
import sys

def add_swagger_to_app():
    """将Swagger添加到Flask应用"""
    # 检查app/__init__.py文件是否存在
    if not os.path.exists("app/__init__.py"):
        print("未找到app/__init__.py文件，请确保您在正确的项目根目录下运行此脚本")
        return False
    
    # 读取文件内容
    with open("app/__init__.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # 检查是否已经安装了Swagger
    if "flasgger" in content:
        print("已经安装了Swagger，无需重复安装")
        return True
    
    # 添加导入语句
    import_statement = "from flasgger import Swagger\n"
    if "from flask import Flask" in content:
        content = content.replace("from flask import Flask", "from flask import Flask\n" + import_statement)
    else:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "import" in line:
                lines.insert(i + 1, import_statement)
                content = "\n".join(lines)
                break
    
    # 添加Swagger初始化代码
    swagger_config = """
    # 初始化Swagger
    app.config['SWAGGER'] = {
        'title': 'IMP API',
        'description': 'Intelligent Middleware Platform API Documentation',
        'version': '1.0.0',
        'uiversion': 3,
        'doc_dir': './docs/swagger/',
        'termsOfService': '',
        'hide_top_bar': False,
        'specs': [
            {
                'endpoint': 'apispec',
                'route': '/apispec.json',
                'rule_filter': lambda rule: True,  # 所有接口
                'model_filter': lambda tag: True,  # 所有模型
            },
            {
                'endpoint': 'auth_apispec',
                'route': '/auth/apispec.json',
                'rule_filter': lambda rule: rule.endpoint.startswith('auth'),
                'model_filter': lambda tag: True,
            },
            {
                'endpoint': 'rss_apispec',
                'route': '/rss/apispec.json',
                'rule_filter': lambda rule: rule.endpoint.startswith('rss'),
                'model_filter': lambda tag: True,
            },
            {
                'endpoint': 'digest_apispec',
                'route': '/digest/apispec.json',
                'rule_filter': lambda rule: rule.endpoint.startswith('digest'),
                'model_filter': lambda tag: True,
            },
            {
                'endpoint': 'llm_apispec',
                'route': '/llm/apispec.json',
                'rule_filter': lambda rule: rule.endpoint.startswith('llm'),
                'model_filter': lambda tag: True,
            }
        ],
        'specs_route': '/api/docs/'
    }
    Swagger(app)
    """
    
    # 在return app前添加Swagger初始化代码
    if "return app" in content:
        content = content.replace("return app", swagger_config + "\n    return app")
    else:
        content += "\n" + swagger_config
    
    # 写回文件
    with open("app/__init__.py", "w", encoding="utf-8") as f:
        f.write(content)
    
    print("成功添加Swagger到Flask应用")
    return True

def create_api_wrapper():
    """创建API装饰器工具"""
    # 创建目录
    os.makedirs("app/utils", exist_ok=True)
    
    # 创建文件
    with open("app/utils/swagger_utils.py", "w", encoding="utf-8") as f:
        f.write('''"""Swagger工具函数"""
from functools import wraps
from flasgger import swag_from
import os

def document_api(yaml_path):
    """API文档装饰器
    
    Args:
        yaml_path: YAML文件路径，相对于docs/swagger目录
        
    Returns:
        装饰器函数
    """
    def decorator(f):
        # 检查是否存在docs/swagger目录
        if not os.path.exists("docs/swagger"):
            # 如果不存在，则直接返回原函数
            return f
        
        # 构建完整路径
        full_path = os.path.join("docs/swagger", yaml_path)
        
        # 检查文件是否存在
        if not os.path.exists(full_path):
            # 如果不存在，则直接返回原函数
            return f
        
        # 应用swagger装饰器
        return swag_from(full_path)(f)
    
    return decorator
''')
    
    print("成功创建API装饰器工具")
    return True

def add_requirements():
    """添加依赖到项目"""
    # 检查pyproject.toml是否存在
    if os.path.exists("pyproject.toml"):
        with open("pyproject.toml", "r", encoding="utf-8") as f:
            content = f.read()
        
        if "flasgger" not in content:
            # 找到[tool.poetry.dependencies]部分并添加flasgger
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "[tool.poetry.dependencies]" in line:
                    lines.insert(i + 1, 'flasgger = "^0.9.5"')
                    break
            
            with open("pyproject.toml", "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            
            print("已将flasgger添加到pyproject.toml文件")
            print("请运行 'poetry install' 安装新依赖")
    else:
        print("未找到pyproject.toml文件")
        print("请手动添加flasgger依赖: pip install flasgger")

if __name__ == "__main__":
    print("开始安装Swagger到Flask应用...")
    if add_swagger_to_app():
        create_api_wrapper()
        add_requirements()
        print("\n安装完成！")
        print("请运行以下命令安装依赖:")
        print("  pip install flasgger")
        print("\n使用方法:")
        print("1. 在API函数上添加装饰器:")
        print("   from app.utils.swagger_utils import document_api")
        print("   @auth_bp.route('/login', methods=['POST'])")
        print("   @document_api('auth/login.yml')")
        print("   def login():")
        print("       # 实现代码")
        print("\n2. 访问API文档:")
        print("   http://your-domain/api/docs/")
    else:
        print("安装失败")
EOF
    echo "✅ 已生成 install_swagger.py"
}

# 创建API示例文件
create_api_example() {
    echo -e "${YELLOW}创建API示例文件...${NC}"
    
    cat > docs/swagger/api_example.py << EOF
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
EOF
    echo "✅ 已生成 api_example.py"

    # 创建示例YAML文件
    mkdir -p docs/swagger/example
    
    cat > docs/swagger/example/hello.yml << EOF
summary: Hello World示例
description: 获取Hello World消息
tags:
  - 示例
parameters:
  - name: name
    in: query
    type: string
    description: 名称
    required: false
    default: World
responses:
  200:
    description: 成功
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "操作成功"
        data:
          type: object
          properties:
            message:
              type: string
              example: "Hello, World!"
EOF
    echo "✅ 已生成 hello.yml"

    cat > docs/swagger/example/create.yml << EOF
summary: 创建示例
description: 创建一个示例记录
tags:
  - 示例
parameters:
  - name: body
    in: body
    required: true
    schema:
      type: object
      required:
        - name
      properties:
        name:
          type: string
          description: 名称
          example: "测试名称"
responses:
  200:
    description: 创建成功
    schema:
      type: object
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: "创建成功"
        data:
          type: object
          properties:
            id:
              type: integer
              example: 1
            name:
              type: string
              example: "测试名称"
            created_at:
              type: string
              format: date-time
              example: "2023-01-01T12:00:00"
EOF
    echo "✅ 已生成 create.yml"
}

# 主函数
main() {
    # 处理各模块
    process_auth_files
    process_rss_files
    process_digest_files
    process_llm_files
    
    # 生成通用定义
    generate_definitions
    
    # 生成Swagger配置
    generate_swagger_config
    
    # 创建安装脚本
    create_install_script
    
    # 创建API示例
    create_api_example
    
    echo -e "\n${GREEN}Swagger文档模板生成完成!${NC}"
    echo -e "请运行 ${YELLOW}python install_swagger.py${NC} 安装Swagger到您的Flask应用。"
    echo -e "安装完成后，请在您的API函数上添加 ${YELLOW}@document_api('路径/文件名.yml')${NC} 装饰器。"
    echo -e "例如: ${YELLOW}@document_api('auth/login.yml')${NC}"
    echo -e "访问API文档: ${YELLOW}http://your-domain/api/docs/${NC}"
}

# 执行主函数
main