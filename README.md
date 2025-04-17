# Intelligent Middleware Platform

Intelligent Middleware Platform (IMP) 是一个智能中间件平台，提供RSS订阅管理、文章抓取和处理等功能。

## 部署指南

### Zeabur 一键部署

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/templates/XXXXX)

### 环境要求

- Python 3.10+
- MySQL 5.7+
- Redis (可选)

### 本地开发

1. 克隆代码库
```bash
git clone <repository-url>
cd paraluxflow-server
```

2. 安装依赖
```bash
# 使用 Poetry
poetry install

# 或者使用 pip
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填写必要的配置信息
```

4. 初始化数据库
```bash
flask db upgrade
```

5. 运行开发服务器
```bash
flask run
```

### Docker 部署

```bash
docker build -t paraluxflow-server .
docker run -p 8000:8000 --env-file .env paraluxflow-server
```

## API 文档

API 文档可通过以下路径访问：

- `/api/docs` - Swagger UI 文档