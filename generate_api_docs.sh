#!/bin/bash

# 设置环境变量
PROJECT_DIR="$(pwd)"
OUTPUT_DIR="${PROJECT_DIR}/apifox_docs"
API_DIR="${PROJECT_DIR}/app/api"
TEMP_DIR="${OUTPUT_DIR}/temp"

# 创建输出目录
mkdir -p "${OUTPUT_DIR}"
mkdir -p "${TEMP_DIR}"

# 输出带时间戳的日志
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "开始扫描Flask路由接口..."

# 创建OpenAPI基本文档结构
cat > "${OUTPUT_DIR}/api_docs.json" << EOF
{
  "openapi": "3.0.1",
  "info": {
    "title": "IMP API文档",
    "version": "1.0.0",
    "description": "自动生成的API文档"
  },
  "paths": {
EOF

# 查找所有API蓝图文件并提取路由信息
first_path=true

find "${API_DIR}" -type f -name "*.py" 2>/dev/null | while read -r file; do
    # 排除初始化文件和swagger相关文件
    if [[ "${file}" == *"__init__.py"* ]] || [[ "${file}" == *"swagger"* ]]; then
        continue
    fi
    
    # 提取当前文件的模块名称和路径信息
    relative_path=${file#$PROJECT_DIR/}
    module_name=$(basename "${file}" .py)
    
    log "处理文件: ${relative_path}"
    
    # 提取所有路由定义行号
    grep -n "@.*_bp.route" "${file}" 2>/dev/null | while read -r line; do
        line_num=$(echo "${line}" | cut -d: -f1)
        route_def=$(echo "${line}" | cut -d: -f2-)
        
        # 提取路由路径 - 使用标准sed
        route_path=""
        if echo "${route_def}" | grep -q '@.*_bp\.route("'; then
            route_path=$(echo "${route_def}" | sed -n 's/.*@.*_bp\.route("\([^"]*\)".*/\1/p')
        elif echo "${route_def}" | grep -q "@.*_bp\.route('"; then
            route_path=$(echo "${route_def}" | sed -n "s/.*@.*_bp\.route('\([^']*\)'.*/\1/p")
        fi
        
        # 提取方法 - 使用标准sed
        methods=""
        if echo "${route_def}" | grep -q 'methods=\['; then
            methods=$(echo "${route_def}" | sed -n 's/.*methods=\[\([^]]*\)\].*/\1/p')
        fi
        
        # 如果没有指定方法，则默认为GET
        if [ -z "${methods}" ]; then
            methods='"GET"'
        fi
        
        # 提取HTTP方法(去除引号和空格)
        http_method=$(echo "${methods}" | sed 's/"//g' | sed 's/,.*//g' | tr '[:upper:]' '[:lower:]')
        if [ -z "${http_method}" ]; then
            http_method="get"
        fi
        
        # 获取路由函数名称（下一行的函数定义）
        next_line=$(sed -n "$((line_num+1))p" "${file}")
        route_func=""
        if echo "${next_line}" | grep -q '^def '; then
            route_func=$(echo "${next_line}" | sed -n 's/def \([^(]*\).*/\1/p')
        fi
        
        if [ -n "${route_path}" ] && [ -n "${route_func}" ]; then
            # 提取函数docstring用于描述
            docstring=""
            doc_line=$((line_num+2))
            doc_line_content=$(sed -n "${doc_line}p" "${file}")
            
            # 检查是否有三引号文档字符串
            if echo "${doc_line_content}" | grep -q '"""'; then
                # 简单提取docstring - 仅获取首行
                docstring=$(echo "${doc_line_content}" | sed 's/"""//g' | xargs)
            fi
            
            # 将蓝图名称也添加到文件中
            blueprint_name=$(grep -o "[a-zA-Z0-9_]*_bp" "${file}" | head -1)
            
            # 尝试从文件中提取父蓝图信息
            parent_prefix=""
            if [ -f "${PROJECT_DIR}/app/api/v1/__init__.py" ]; then
                parent_prefix=$(grep -A 1 "${blueprint_name}" "${PROJECT_DIR}/app/api/v1/__init__.py" 2>/dev/null | grep "url_prefix" | sed -n 's/.*url_prefix="\([^"]*\)".*/\1/p')
            fi
            
            # 生成完整路径
            full_path="/api/v1"
            
            # 添加父前缀（如果有）
            if [ -n "${parent_prefix}" ]; then
                full_path="${full_path}${parent_prefix}"
            fi
            
            # 添加路由路径
            full_path="${full_path}${route_path}"
            
            # 生成API文档片段
            if [ "${first_path}" = true ]; then
                first_path=false
            else
                echo "," >> "${OUTPUT_DIR}/api_docs.json"
            fi
            
            cat >> "${OUTPUT_DIR}/api_docs.json" << EOF
    "${full_path}": {
      "${http_method}": {
        "tags": ["${module_name}"],
        "summary": "${docstring}",
        "description": "路由函数: ${route_func}",
        "responses": {
          "200": {
            "description": "成功响应",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "code": {
                      "type": "integer",
                      "example": 200
                    },
                    "message": {
                      "type": "string",
                      "example": "操作成功"
                    },
                    "data": {
                      "type": "object"
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
EOF
            
            log "已生成路由: ${full_path} (${http_method})"
        fi
    done
done

# 完成文档
cat >> "${OUTPUT_DIR}/api_docs.json" << EOF
  }
}
EOF

log "文档生成完成! API文档已保存至: ${OUTPUT_DIR}/api_docs.json"
log "你可以将该文件导入到Apifox中使用。"
log "注意: 这是基本API文档，你可能需要手动添加请求体、参数等详细信息。"