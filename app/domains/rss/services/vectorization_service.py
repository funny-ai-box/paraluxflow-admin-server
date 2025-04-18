# app/domains/rss/services/vectorization_service.py
"""RSS文章向量化服务 - 使用已有的LLM Provider和向量存储接口"""
import logging
import uuid
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import json

from app.infrastructure.vector_stores.factory import VectorStoreFactory
from app.infrastructure.llm_providers.factory import LLMProviderFactory
from app.utils.summary_generator import generate_summary
from app.core.exceptions import APIException
from flask import current_app

logger = logging.getLogger(__name__)

class ArticleVectorizationService:
    """RSS文章向量化服务"""
    
    def __init__(self, article_repo, content_repo, task_repo, provider_type="volcano", model="doubao-embedding-large-text-240915", store_type="milvus"):
        """初始化向量化服务
        
        Args:
            article_repo: 文章仓库
            content_repo: 文章内容仓库
            task_repo: 向量化任务仓库
            provider_type: 提供商类型，默认为openai
            model: 嵌入模型名称
            store_type: 向量存储类型，默认为milvus
        """
        self.article_repo = article_repo
        self.content_repo = content_repo
        self.task_repo = task_repo
        self.provider_type = provider_type
        self.model = model
        self.store_type = store_type
        self.llm_provider = None
        self.vector_store = None
        self.collection_name = "rss_articles"  # 默认集合/索引名称
        
        # 设置向量维度（根据模型确定）
        if "volcano" in self.provider_type:
    
            self.vector_dimension = 4096
        else:

            self.vector_dimension = 1536
        
        # 初始化LLM Provider和向量存储
        self._init_services()
    
    def _init_services(self):
        """初始化LLM提供商和向量存储"""
        try:
     
         
            print("初始化服务")
            self.llm_provider = LLMProviderFactory.create_provider(
                provider_name=self.provider_type,
                embeddings_model=self.model
            )
            
            logger.info(f"成功初始化{self.provider_type}提供商用于向量化")
            
            # 从配置获取向量存储配置
            store_config = {
                "host": current_app.config.get("MILVUS_HOST", "localhost"),
                "port": current_app.config.get("MILVUS_PORT", "19530")
            }
            
            # 创建向量存储实例
            self.vector_store = VectorStoreFactory.create_store(
                store_name=self.store_type,
                **store_config
            )
            
            
            
            # 确保集合存在
            self._ensure_collection_exists()
            
            logger.info(f"成功初始化{self.store_type}向量存储")
        except Exception as e:
            logger.error(f"初始化服务失败: {str(e)}")
            # 不抛出异常，允许延迟初始化
    
    def _ensure_collection_exists(self):
        """确保向量集合存在，如果不存在则自动创建"""
        try:
            if not self.vector_store.index_exists(self.collection_name):
                logger.info(f"集合 {self.collection_name} 不存在，正在自动创建...")
                
                # 简化集合定义，只使用基本字段
                # 创建集合
                self.vector_store.create_index(
                    index_name=self.collection_name,
                    dimension=self.vector_dimension,
                    description="RSS文章向量集合"
                    # 不指定额外字段，只使用默认的id、vector和metadata
                )
                logger.info(f"成功创建集合 {self.collection_name}，维度为 {self.vector_dimension}")
                return True
            return True  # 集合已存在
        except Exception as e:
            logger.error(f"检查/创建集合失败: {str(e)}")
            raise Exception(f"检查/创建集合失败: {str(e)}。请确保Milvus服务正确配置和运行。")
    
    def start_vectorization_task(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """启动向量化任务
        
        Args:
            filters: 文章过滤条件，默认为None表示所有未向量化的文章
            
        Returns:
            任务信息
            
        Raises:
            Exception: 启动任务失败时抛出异常
        """
        # 确保服务已初始化
        if not self.llm_provider or not self.vector_store:
            self._init_services()
            if not self.llm_provider or not self.vector_store:
                raise Exception("无法初始化服务，请检查配置")
        
        # 创建过滤条件
        if not filters:
            filters = {}
        
        # 确保只处理未向量化的文章
        if "vectorization_status" not in filters:
            filters["vectorization_status"] = 0  # 未处理
        
        # 查询符合条件的文章数量
        articles_result = self.article_repo.get_articles(page=1, per_page=1, filters=filters)
        total_articles = articles_result["total"]
        
        if total_articles == 0:
            raise Exception("没有符合条件的文章需要向量化")
        
        # 创建任务记录
        batch_id = str(uuid.uuid4())
        task_data = {
            "batch_id": batch_id,
            "total_articles": total_articles,
            "processed_articles": 0,
            "success_articles": 0,
            "failed_articles": 0,
            "status": 0,  # 进行中
            "embedding_model": self.model,
            "started_at": datetime.now()
        }
        
        task = self.task_repo.create_task(task_data)
        
        # 触发异步任务处理
        logger.info(f"启动向量化任务 {batch_id}，共 {total_articles} 篇文章")
        
        # 启动后台线程进行处理
        threading.Thread(
            target=self._process_vectorization_task,
            args=(batch_id, filters),
            daemon=True
        ).start()
        
        return task
    
    def _process_vectorization_task(self, batch_id: str, filters: Dict[str, Any]) -> None:
        """后台处理向量化任务
        
        Args:
            batch_id: 批次ID
            filters: 文章过滤条件
        """
        logger.info(f"后台开始处理向量化任务 {batch_id}")
        page = 1
        per_page = 10  # 每批处理10篇
        processed_count = 0
        success_count = 0
        failed_count = 0
        
        try:
            # 不断获取新的文章进行处理，直到没有更多符合条件的文章
            while True:
                # 获取一批文章
                articles_result = self.article_repo.get_articles(page=page, per_page=per_page, filters=filters)
                articles = articles_result["list"]
                
                if not articles:
                    break  # 没有更多文章了
                
                # 处理这批文章
                for article in articles:
                    try:
                        # 向量化文章
                        result = self.process_article_vectorization(article["id"])
                        
                        # 更新计数
                        processed_count += 1
                        if result["status"] == "success":
                            success_count += 1
                        else:
                            failed_count += 1
                        
                        # 更新任务状态
                        self.task_repo.update_task(batch_id, {
                            "processed_articles": processed_count,
                            "success_articles": success_count,
                            "failed_articles": failed_count
                        })
                        
                        # 限制请求频率，避免API限流
                        time.sleep(0.5)
                    except Exception as e:
                        logger.error(f"处理文章 {article['id']} 时出错: {str(e)}")
                        failed_count += 1
                        processed_count += 1
                        
                        # 更新任务状态
                        self.task_repo.update_task(batch_id, {
                            "processed_articles": processed_count,
                            "success_articles": success_count,
                            "failed_articles": failed_count
                        })
                
                # 进入下一页
                page += 1
            
            # 任务完成，更新状态
            ended_time = datetime.now()
            started_time = datetime.fromisoformat(self.task_repo.get_task(batch_id)["started_at"])
            total_time = (ended_time - started_time).total_seconds()
            
            self.task_repo.update_task(batch_id, {
                "status": 1,  # 已完成
                "ended_at": ended_time,
                "total_time": total_time
            })
            
            logger.info(f"向量化任务 {batch_id} 完成, 总计: {processed_count}, 成功: {success_count}, 失败: {failed_count}")
        except Exception as e:
            # 任务失败，更新状态
            logger.error(f"向量化任务 {batch_id} 处理失败: {str(e)}")
            
            ended_time = datetime.now()
            started_time = datetime.fromisoformat(self.task_repo.get_task(batch_id)["started_at"])
            total_time = (ended_time - started_time).total_seconds()
            
            self.task_repo.update_task(batch_id, {
                "status": 2,  # 失败
                "ended_at": ended_time,
                "total_time": total_time,
                "error_message": str(e)
            })
    
    def process_article_vectorization(self, article_id: int) -> Dict[str, Any]:
        """处理单篇文章的向量化
        
        Args:
            article_id: 文章ID
            
        Returns:
            处理结果
            
        Raises:
            Exception: 处理失败时抛出异常
        """
        # 确保服务已初始化
        if not self.llm_provider or not self.vector_store:
            try:
                self._init_services()
                if not self.llm_provider or not self.vector_store:
                    # 这里抛出异常而不是尝试继续处理
                    raise Exception("无法初始化服务，请检查配置")
            except Exception as e:
                # 记录详细的初始化错误信息
                logger.error(f"初始化向量化服务失败: {str(e)}")
                # 更新文章状态
                try:
                    self.article_repo.update_article_vectorization_status(
                        article_id=article_id, 
                        status=2,  # 失败
                        error_message=f"服务初始化失败: {str(e)}"
                    )
                except Exception as db_error:
                    # 如果连状态更新都失败（如表结构问题），则记录这个额外错误
                    logger.error(f"更新文章状态失败: {str(db_error)}")
                    # 组合两个错误信息以提供更完整的错误上下文
                    raise Exception(f"服务初始化失败: {str(e)}。数据库错误: {str(db_error)}")
                # 原始错误继续向上抛出
                raise Exception(f"服务初始化失败: {str(e)}")
        
        try:
            # 标记文章为正在处理状态
            try:
                self.article_repo.update_article_vectorization_status(
                    article_id=article_id, 
                    status=3,  # 正在处理
                    error_message=None
                )
            except Exception as e:
                # 如果无法更新状态（可能是数据库结构问题），直接抛出异常
                logger.error(f"无法更新文章状态: {str(e)}")
                raise Exception(f"数据库结构错误: {str(e)}。表中可能缺少向量化相关字段，请确保已进行数据库迁移。")
                
            # 获取文章信息
            err, article = self.article_repo.get_article_by_id(article_id)
            if err:
                raise Exception(f"获取文章失败: {err}")
            

            
            # 检查摘要质量，如果摘要不存在或太短，生成新摘要
            summary = article["summary"]
            generated_summary = None
            
            if not summary or len(summary) < 100:
                logger.info(f"文章 {article_id} 摘要太短，生成新摘要")
                if not article["content_id"]:
                    raise Exception("文章缺少内容，无法向量化")
                
                # 获取文章内容
                err, content = self.content_repo.get_article_content(article["content_id"])
                if err:
                    raise Exception(f"获取文章内容失败: {err}")
                
                # 使用sumy生成摘要
                html_content = content.get("html_content")
                text_content = content.get("text_content")
                
                if html_content:
                    generated_summary = generate_summary(html=html_content, sentences_count=5)
                elif text_content:
                    generated_summary = generate_summary(text=text_content, sentences_count=5)
                else:
                    generated_summary = ""
                
                # 如果生成了新摘要，更新文章的摘要
                if generated_summary and len(generated_summary) > 100:
                    summary = generated_summary
            
            # 构建向量化文本（标题+摘要）
            vector_text = f"{article['title']}\n{summary}"
            
            
            embedding_result = self.llm_provider.generate_embeddings(
                    texts=[vector_text],
                    model=self.model
                )
        
            
            # 从结果中提取向量
            vector = embedding_result["embeddings"][0]
            feed_id = article.get("feed_id", "unknown")
            # 生成向量ID
            vector_id = f"article_{feed_id}_{article_id}"
            
            # 准备元数据
            metadata = {
                "article_id": article_id,
                "feed_id": article["feed_id"],
                "title": article["title"],
                "summary": summary,
                "created_at": datetime.now().isoformat()
            }
            
            # 插入向量到向量存储
            try:
                self.vector_store.upsert(
                    index_name=self.collection_name,
                    vectors=[vector],
                    ids=[vector_id],
                    metadata=[metadata]
                )
            except Exception as e:
                # 提供具体的向量存储错误
                logger.error(f"存储向量失败: {str(e)}")
                raise Exception(f"存储向量失败: {str(e)}。请检查Milvus服务是否正确配置和运行。")
            
            # 更新文章状态
            update_data = {
                "is_vectorized": True,
                "vector_id": vector_id,
                "vectorized_at": datetime.now(),
                "embedding_model": self.model,
                "vector_dimension": self.vector_dimension,
                "vectorization_status": 1  # 成功
            }
            
            # 如果生成了新摘要，也更新摘要
            if generated_summary:
                update_data["generated_summary"] = generated_summary
            
            self.article_repo.update_article_vectorization(article_id, update_data)
            
            return {
                "status": "success",
                "article_id": article_id,
                "vector_id": vector_id,
                "message": "文章向量化成功"
            }
        except Exception as e:
            # 记录详细错误
            logger.error(f"文章 {article_id} 向量化失败: {str(e)}")
            
            # 尝试更新文章状态
            try:
                self.article_repo.update_article_vectorization_status(
                    article_id=article_id,
                    status=2,  # 失败
                    error_message=str(e)
                )
            except Exception as db_error:
                # 如果连状态更新都失败，记录额外错误
                logger.error(f"更新文章向量化状态失败: {str(db_error)}")
                # 附加额外的错误信息
                raise Exception(f"文章向量化失败: {str(e)}。数据库错误: {str(db_error)}")
            
            # 向上抛出原始错误
            raise Exception(f"文章向量化失败: {str(e)}")
    
    def get_similar_articles(self, article_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """获取相似文章
        
        Args:
            article_id: 文章ID
            limit: 返回数量
            
        Returns:
            相似文章列表
            
        Raises:
            Exception: 查询失败时抛出异常
        """
        try:
            # 确保服务已初始化
            if not self.llm_provider or not self.vector_store:
                self._init_services()
                if not self.llm_provider or not self.vector_store:
                    raise Exception("无法初始化服务，请检查配置")
            
            # 获取文章信息
            err, article = self.article_repo.get_article_by_id(article_id)
            if err:
                raise Exception(f"获取文章失败: {err}")
            
            # 检查文章是否已向量化
            if not article.get("is_vectorized") or not article.get("vector_id"):
                raise Exception("文章尚未向量化")
            
            # 获取文章向量
            vector_results = self.vector_store.get(
                index_name=self.collection_name,
                ids=[article["vector_id"]]
            )
            
            if not vector_results:
                # 如果没有找到向量，可能是ID格式不正确或已删除
                # 重新生成向量
                summary = article.get("summary") or article.get("generated_summary") or ""
                vector_text = f"{article['title']}\n{summary}"
                
                # 使用LLM Provider生成向量
                embedding_result = self.llm_provider.generate_embeddings(
                    texts=[vector_text],
                    model=self.model
                )
                
                # 从结果中提取向量
                vector = embedding_result["embeddings"][0]
            else:
                # 使用找到的向量
                vector = vector_results[0]["vector"]
            
            # 搜索相似文章
            search_results = self.vector_store.search(
                index_name=self.collection_name,
                query_vector=vector,
                top_k=limit + 1  # +1是因为会包含自己
            )
            
            # 过滤掉自己
            search_results = [
                result for result in search_results
                if result["metadata"].get("article_id") != article_id
            ][:limit]
            
            # 获取完整的文章信息
            result_articles = []
            for result in search_results:
                metadata = result["metadata"]
                article_id = metadata.get("article_id")
                
                if article_id:
                    err, full_article = self.article_repo.get_article_by_id(article_id)
                    if not err and full_article:
                        # 添加相似度信息
                        full_article["similarity"] = result["score"]
                        result_articles.append(full_article)
            
            return result_articles
        except Exception as e:
            logger.error(f"获取相似文章失败: {str(e)}")
            raise Exception(f"获取相似文章失败: {str(e)}")
    
    def search_articles(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """根据查询文本搜索文章
        
        Args:
            query: 查询文本
            limit: 返回数量
            
        Returns:
            相关文章列表
            
        Raises:
            Exception: 搜索失败时抛出异常
        """
        try:
            # 确保服务已初始化
            if not self.llm_provider or not self.vector_store:
                self._init_services()
                if not self.llm_provider or not self.vector_store:
                    raise Exception("无法初始化服务，请检查配置")
            
            # 将查询文本转换为向量
            embedding_result = self.llm_provider.generate_embeddings(
                texts=[query],
                model=self.model
            )
            
            # 从结果中提取向量
            query_vector = embedding_result["embeddings"][0]
            
            # 在向量库中搜索
            search_results = self.vector_store.search(
                index_name=self.collection_name,
                query_vector=query_vector,
                top_k=limit
            )
            
            # 获取完整的文章信息
            result_articles = []
            for result in search_results:
                metadata = result["metadata"]
                article_id = metadata.get("article_id")
                
                if article_id:
                    err, full_article = self.article_repo.get_article_by_id(article_id)
                    if not err and full_article:
                        # 添加相似度信息
                        full_article["similarity"] = result["score"]
                        result_articles.append(full_article)
            
            return result_articles
        except Exception as e:
            logger.error(f"搜索文章失败: {str(e)}")
            raise Exception(f"搜索文章失败: {str(e)}")
    
    def get_vectorization_statistics(self) -> Dict[str, Any]:
        """获取向量化统计信息
        
        Returns:
            统计信息
        """
        try:
            # 确保服务已初始化
            if not self.vector_store:
                self._init_services()
            
            # 查询全部文章数量
            all_articles = self.article_repo.get_articles(page=1, per_page=1)["total"]
            
            # 查询已向量化文章数量
            vectorized_articles = self.article_repo.get_articles(
                page=1, 
                per_page=1, 
                filters={"vectorization_status": 1}
            )["total"]
            
            # 查询向量化失败文章数量
            failed_articles = self.article_repo.get_articles(
                page=1, 
                per_page=1, 
                filters={"vectorization_status": 2}
            )["total"]
            
            # 查询正在处理的文章数量
            processing_articles = self.article_repo.get_articles(
                page=1, 
                per_page=1, 
                filters={"vectorization_status": 3}
            )["total"]
            
            # 获取向量库中的向量数量
            milvus_count = 0
            if self.vector_store and self.vector_store.index_exists(self.collection_name):
                milvus_count = self.vector_store.count(self.collection_name)
            
            # 计算向量化比例
            vectorization_rate = (vectorized_articles / all_articles * 100) if all_articles > 0 else 0
            
            return {
                "total_articles": all_articles,
                "vectorized_articles": vectorized_articles,
                "failed_articles": failed_articles,
                "processing_articles": processing_articles,
                "pending_articles": all_articles - vectorized_articles - failed_articles - processing_articles,
                "vector_store_vectors": milvus_count,
                "vector_store_type": self.store_type,
                "vectorization_rate": round(vectorization_rate, 2)
            }
        except Exception as e:
            logger.error(f"获取向量化统计信息失败: {str(e)}")
            return {
                "error": str(e)
            }