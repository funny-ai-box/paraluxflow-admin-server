# app/domains/rss/services/vectorization_service.py
import logging
import uuid
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import json

from app.infrastructure.vector_stores.factory import VectorStoreFactory
from app.infrastructure.llm_providers.factory import LLMProviderFactory
from app.core.exceptions import APIException
from flask import current_app

logger = logging.getLogger(__name__)

class ArticleVectorizationService:
    """RSS文章向量化服务"""

    def __init__(self, article_repo, content_repo, task_repo, provider_type="openai", model="text-embedding-3-large", store_type="milvus"):
        """初始化向量化服务

        Args:
            article_repo: 文章仓库
            content_repo: 文章内容仓库
            task_repo: 向量化任务仓库
            provider_type: 默认openai
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

       
        self.vector_dimension = 3072 # Example for text-embedding-ada-002

        # 初始化LLM Provider和向量存储
        self._init_services()

    def _init_services(self):
        """初始化LLM提供商和向量存储"""
        try:
            print("初始化向量化服务中的 LLM Provider 和 Vector Store...") # Debug print
            # Ensure Flask app context is available or handle appropriately
            if not current_app:
                # Handle cases outside Flask request context (e.g., background tasks)
                # Option 1: Pass config explicitly if possible
                # Option 2: Use a dedicated app context factory
                # Option 3: Log a warning and potentially defer initialization
                logger.warning("无法访问 Flask 应用上下文，服务初始化可能受限。")
                # For simplicity here, we assume it's run within context or config is accessible
                # In a real app, better context management is needed for background tasks

            # --- Initialize LLM Provider ---
            # Check if already initialized
            if not self.llm_provider:
                 print(f"初始化 LLM Provider: {self.provider_type}") # Debug print
                 self.llm_provider = LLMProviderFactory.create_provider(
                      provider_name=self.provider_type,
                      # Pass necessary config, potentially embeddings_model if needed by factory
                      # The factory should ideally fetch config from DB/Env
                      embeddings_model=self.model # Pass the specific model intended for embeddings
                 )
                 logger.info(f"成功初始化 {self.provider_type} 提供商用于向量化")
                 print(f"LLM Provider ({self.provider_type}) 初始化成功。") # Debug print
            else:
                print("LLM Provider 已初始化。") # Debug print

            # --- Initialize Vector Store ---
            # Check if already initialized
            if not self.vector_store:
                print(f"初始化 Vector Store: {self.store_type}") # Debug print
                # Attempt to get config, provide defaults if outside context and config isn't passed
                milvus_host = "localhost"
                milvus_port = "19530"
                if current_app:
                    milvus_host = current_app.config.get("MILVUS_HOST", milvus_host)
                    milvus_port = current_app.config.get("MILVUS_PORT", milvus_port)
                else:
                    # Fallback or get from environment directly if needed for background tasks
                    import os
                    milvus_host = os.environ.get("MILVUS_HOST", milvus_host)
                    milvus_port = os.environ.get("MILVUS_PORT", milvus_port)
                    logger.warning(f"在 Flask 上下文之外运行，使用环境变量或默认 Milvus 配置: {milvus_host}:{milvus_port}")


                store_config = {
                    "host": milvus_host,
                    "port": milvus_port
                    # Add user/password if needed from config/env
                }
                print(f"Vector Store 配置: {store_config}") # Debug print

                # 创建向量存储实例
                self.vector_store = VectorStoreFactory.create_store(
                    store_name=self.store_type,
                    **store_config
                )
                print(f"Vector Store ({self.store_type}) 实例创建成功。") # Debug print


                # 确保集合存在
                print(f"确保集合 '{self.collection_name}' 存在...") # Debug print
                self._ensure_collection_exists()
                print(f"集合 '{self.collection_name}' 确认存在。") # Debug print

                logger.info(f"成功初始化 {self.store_type} 向量存储")
            else:
                 print("Vector Store 已初始化。") # Debug print

        except Exception as e:
            logger.error(f"初始化服务失败: {str(e)}", exc_info=True) # Log traceback
            print(f"错误: 初始化服务失败: {str(e)}") # Debug print
            # Consider re-raising or handling gracefully based on application needs
            # raise Exception(f"初始化服务失败: {str(e)}")

    def _ensure_collection_exists(self):
        """确保向量集合存在，如果不存在则自动创建"""
        try:
            # Check if vector_store is initialized
            if not self.vector_store:
                logger.error("尝试在未初始化的向量存储上检查集合。")
                raise Exception("Vector store not initialized before checking collection.")

            if not self.vector_store.index_exists(self.collection_name):
                logger.info(f"集合 {self.collection_name} 不存在，正在自动创建...")
                print(f"集合 {self.collection_name} 不存在，正在自动创建...") # Debug print

                # 创建集合
                self.vector_store.create_index(
                    index_name=self.collection_name,
                    dimension=self.vector_dimension,
                    description="RSS文章向量集合"
                )
                logger.info(f"成功创建集合 {self.collection_name}，维度为 {self.vector_dimension}")
                print(f"成功创建集合 {self.collection_name}，维度为 {self.vector_dimension}") # Debug print
                return True
            else:
                print(f"集合 {self.collection_name} 已存在。") # Debug print
                return True  # 集合已存在
        except Exception as e:
            logger.error(f"检查/创建集合失败: {str(e)}", exc_info=True) # Log traceback
            print(f"错误: 检查/创建集合失败: {str(e)}") # Debug print
            # Re-raise with more context
            raise Exception(f"检查/创建Milvus集合失败: {str(e)}。请确保Milvus服务正确配置和运行。")


    def process_article_vectorization(self, article_id: int) -> Dict[str, Any]:
        """处理单篇文章的向量化 - 不再生成摘要，直接使用已有摘要

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
                    raise Exception("无法初始化服务，请检查配置")
            except Exception as e:
                logger.error(f"初始化向量化服务失败: {str(e)}")
                try:
                    # Attempt to mark article as failed even if services failed to init
                    self.article_repo.update_article_vectorization_status(
                        article_id=article_id,
                        status=2,  # 失败
                        error_message=f"服务初始化失败: {str(e)}"
                    )
                except Exception as db_error:
                    logger.error(f"更新文章 {article_id} 状态失败: {str(db_error)}")
                raise Exception(f"服务初始化失败: {str(e)}") # Re-raise original error

        try:
            # 标记文章为正在处理状态
            try:
                self.article_repo.update_article_vectorization_status(
                    article_id=article_id,
                    status=3,  # 正在处理
                    error_message=None
                )
            except Exception as e:
                logger.error(f"无法更新文章 {article_id} 状态为处理中: {str(e)}")
                raise Exception(f"数据库访问错误: {str(e)}。请检查数据库连接和表结构。")

            # 获取文章信息
            err, article = self.article_repo.get_article_by_id(article_id)
            if err:
                raise Exception(f"获取文章 {article_id} 失败: {err}")
            if not article:
                 raise Exception(f"未找到文章 {article_id}")

            # 获取要使用的摘要 - 直接使用现有摘要，不生成新摘要
            summary_to_use = article.get("summary", "")
            
            # 使用生成的摘要（如果存在）
            generated_summary = article.get("generated_summary")
            if generated_summary and len(generated_summary) > len(summary_to_use):
                logger.info(f"文章 {article_id} 使用爬虫生成的摘要而非原始摘要")
                summary_to_use = generated_summary

            # 如果摘要仍然是空的，使用标题作为最后的备选
            if not summary_to_use:
                logger.warning(f"文章 {article_id} 没有可用摘要，将使用标题")
                summary_to_use = article.get("title", "")

            # --- Vectorization ---
            # 构建向量化文本（标题 + 摘要）
            vector_text = f"{article.get('title', '')}\n{summary_to_use}".strip() # Use .get and strip
            if not vector_text: # Handle case where both title and summary are empty
                 logger.error(f"文章 {article_id} 标题和摘要均为空，无法进行向量化。")
                 raise Exception("无法生成向量化文本（标题和摘要均为空）")

            print(f"准备为文章 {article_id} 生成向量，文本片段: '{vector_text[:100]}...'") # Debug print
            embedding_result = self.llm_provider.generate_embeddings(
                texts=[vector_text],
                model=self.model # Ensure the correct model is passed
            )
            print(f"文章 {article_id} 向量生成成功。") # Debug print

            # 从结果中提取向量
            vector = embedding_result.get("embeddings", [None])[0]
            if not vector:
                 logger.error(f"LLM Provider 未能为文章 {article_id} 返回向量。")
                 raise Exception("未能从LLM Provider获取向量")

            feed_id = article.get("feed_id", "unknown")
            vector_id = f"article_{feed_id}_{article_id}" # Use the article ID directly for uniqueness

            # 准备元数据
            metadata = {
                "article_id": article_id,
                "feed_id": article.get("feed_id", "unknown"),
                "title": article.get("title", ""),
                "summary": summary_to_use, # Use the final summary for metadata
                "published_date": article.get("published_date"), # Store original publish date if available
                "vectorized_at": datetime.now().isoformat() # Add vectorization timestamp
            }

            # --- Store Vector ---
            print(f"准备将向量 {vector_id} 插入/更新到 Milvus 集合 {self.collection_name}...") # Debug print
            try:
                self.vector_store.upsert(
                    index_name=self.collection_name,
                    vectors=[vector],
                    ids=[vector_id],
                    metadata=[metadata]
                )
                print(f"向量 {vector_id} 成功存储到 Milvus。") # Debug print
            except Exception as e:
                logger.error(f"存储向量 {vector_id} 失败: {str(e)}", exc_info=True)
                raise Exception(f"存储向量失败: {str(e)}。请检查Milvus服务是否正确配置和运行。")

            # --- Update Database ---
            update_data = {
                "is_vectorized": True,
                "vector_id": vector_id,
                "vectorized_at": datetime.now(),
                "embedding_model": self.model,
                "vector_dimension": self.vector_dimension,
                "vectorization_status": 1  # 成功
            }

            print(f"准备更新数据库文章 {article_id} 状态...") # Debug print
            self.article_repo.update_article_vectorization(article_id, update_data)
            print(f"数据库文章 {article_id} 更新成功。") # Debug print

            return {
                "status": "success",
                "article_id": article_id,
                "vector_id": vector_id,
                "message": "文章向量化成功"
            }
        except Exception as e:
            logger.error(f"文章 {article_id} 向量化失败: {str(e)}", exc_info=True) # Log full traceback

            # Attempt to mark article as failed in DB
            try:
                self.article_repo.update_article_vectorization_status(
                    article_id=article_id,
                    status=2,  # 失败
                    error_message=str(e)[:1000] # Limit error message length for DB
                )
                print(f"文章 {article_id} 状态已标记为失败。") # Debug print
            except Exception as db_error:
                logger.error(f"更新文章 {article_id} 向量化状态为失败时出错: {str(db_error)}", exc_info=True)
                # Combine errors if DB update also fails
                raise Exception(f"文章向量化失败: {str(e)}. 此外，更新数据库状态时出错: {str(db_error)}")

            # Re-raise the original vectorization error
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
            if not article:
                 raise Exception(f"未找到文章 {article_id}")

            # 检查文章是否已向量化
            print(f"检查文章 {article_id} 的向量化状态...") # Debug print
            if not article.get("is_vectorized") or not article.get("vector_id"):
                logger.warning(f"文章 {article_id} 尚未向量化，无法查找相似文章。")
                # Option 1: Raise an exception
                # raise Exception("文章尚未向量化")
                # Option 2: Return empty list
                return []

            article_vector_id = article.get("vector_id")
            print(f"文章 {article_id} 已向量化，向量ID: {article_vector_id}") # Debug print

            # 获取文章向量
            print(f"从 Vector Store 获取向量: {article_vector_id}") # Debug print
            vector_results = self.vector_store.get(
                index_name=self.collection_name,
                ids=[article_vector_id] # Pass ID in a list
            )

            if not vector_results:
                logger.error(f"无法在向量库中找到文章 {article_id} 的向量 (ID: {article_vector_id})，即使它被标记为已向量化。")
                # Possible issue: vector deleted, ID mismatch, DB/vector store inconsistency
                # Option 1: Try to re-vectorize (could be slow/costly)
                # Option 2: Return empty list or raise error
                return [] # Returning empty list for now

            vector = vector_results[0].get("vector")
            if not vector:
                 logger.error(f"从向量库检索到的向量数据为空: {vector_results[0]}")
                 return []

            print(f"成功获取向量 {article_vector_id}。") # Debug print

            # 搜索相似文章
            print(f"在集合 {self.collection_name} 中搜索相似向量...") # Debug print
            search_results = self.vector_store.search(
                index_name=self.collection_name,
                query_vector=vector,
                top_k=limit + 1  # +1 because it might include itself
            )
            print(f"向量搜索完成，找到 {len(search_results)} 个结果。") # Debug print


            # 过滤掉自己并处理结果
            result_articles = []
            for result in search_results:
                metadata = result.get("metadata", {})
                # Use get with default for article_id in metadata
                retrieved_article_id = metadata.get("article_id")

                # Ensure retrieved_article_id is not None and compare with the input article_id
                if retrieved_article_id is not None and retrieved_article_id != article_id:
                    print(f"处理相似结果: ID={retrieved_article_id}, Score={result.get('score')}") # Debug print
                    # 获取完整的文章信息
                    err_full, full_article = self.article_repo.get_article_by_id(retrieved_article_id)
                    if not err_full and full_article:
                        # 添加相似度信息
                        full_article["similarity"] = result.get("score")
                        result_articles.append(full_article)
                    else:
                         logger.warning(f"无法获取相似文章 {retrieved_article_id} 的完整信息: {err_full}")

                    # Break if we have enough results
                    if len(result_articles) >= limit:
                        break

            print(f"最终返回 {len(result_articles)} 篇相似文章。") # Debug print
            return result_articles
        except Exception as e:
            logger.error(f"获取相似文章失败: {str(e)}", exc_info=True)
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
            print(f"为查询 '{query[:50]}...' 生成向量...") # Debug print
            embedding_result = self.llm_provider.generate_embeddings(
                texts=[query],
                model=self.model # Use the configured model
            )
            print("查询向量生成成功。") # Debug print

            # 从结果中提取向量
            query_vector = embedding_result.get("embeddings", [None])[0]
            if not query_vector:
                 logger.error(f"LLM Provider 未能为查询 '{query[:50]}...' 返回向量。")
                 raise Exception("未能从LLM Provider获取查询向量")

            # 在向量库中搜索
            print(f"在集合 {self.collection_name} 中搜索相关文章...") # Debug print
            search_results = self.vector_store.search(
                index_name=self.collection_name,
                query_vector=query_vector,
                top_k=limit
            )
            print(f"向量搜索完成，找到 {len(search_results)} 个结果。") # Debug print

            # 获取完整的文章信息
            result_articles = []
            for result in search_results:
                metadata = result.get("metadata", {})
                article_id = metadata.get("article_id")
                print(f"处理搜索结果: ID={article_id}, Score={result.get('score')}") # Debug print

                if article_id:
                    err_full, full_article = self.article_repo.get_article_by_id(article_id)
                    if not err_full and full_article:
                        # 添加相似度信息
                        full_article["similarity"] = result.get("score")
                        result_articles.append(full_article)
                    else:
                         logger.warning(f"无法获取搜索结果文章 {article_id} 的完整信息: {err_full}")

            print(f"最终返回 {len(result_articles)} 篇搜索结果文章。") # Debug print
            return result_articles
        except Exception as e:
            logger.error(f"搜索文章失败: {str(e)}", exc_info=True)
            raise Exception(f"搜索文章失败: {str(e)}")

    def get_vectorization_statistics(self) -> Dict[str, Any]:
        """获取向量化统计信息

        Returns:
            统计信息
        """
        try:
            # 确保服务已初始化 (只需要 vector_store)
            if not self.vector_store:
                self._init_services()

            # --- Database Statistics ---
            print("获取数据库中的文章统计信息...") # Debug print
            # Build base filter (e.g., exclude certain statuses if needed)
            base_filters = {} # Add filters if you only want to count 'valid' articles

            # Get total count using base filters
            all_articles_result = self.article_repo.get_articles(page=1, per_page=1, filters=base_filters)
            all_articles = all_articles_result.get("total", 0)
            print(f"数据库中总文章数: {all_articles}") # Debug print


            # Function to get count for a specific status
            def get_count_by_status(status_code):
                status_filters = base_filters.copy()
                status_filters["vectorization_status"] = status_code
                count_result = self.article_repo.get_articles(page=1, per_page=1, filters=status_filters)
                return count_result.get("total", 0)

            # Get counts for each status
            vectorized_articles = get_count_by_status(1)
            failed_articles = get_count_by_status(2)
            processing_articles = get_count_by_status(3)
            pending_articles = get_count_by_status(0) # Explicitly count pending

            # --- Vector Store Statistics ---
            milvus_count = 0
            vector_store_exists = False
            if self.vector_store:
                 print(f"获取向量存储 '{self.collection_name}' 的信息...") # Debug print
                 try:
                      if self.vector_store.index_exists(self.collection_name):
                           vector_store_exists = True
                           milvus_count = self.vector_store.count(self.collection_name)
                           print(f"向量存储中的向量数: {milvus_count}") # Debug print
                      else:
                           print(f"向量存储集合 '{self.collection_name}' 不存在。") # Debug print
                 except Exception as vs_err:
                      logger.error(f"无法从向量存储获取计数: {vs_err}", exc_info=True)
                      print(f"错误: 无法从向量存储获取计数: {vs_err}") # Debug print

            # --- Calculate Rate ---
            vectorization_rate = (vectorized_articles / all_articles * 100) if all_articles > 0 else 0
            print(f"向量化率: {vectorization_rate:.2f}%") # Debug print

            return {
                "total_articles": all_articles,
                "vectorized_articles": vectorized_articles,
                "failed_articles": failed_articles,
                "processing_articles": processing_articles,
                "pending_articles": pending_articles, # Use the counted pending value
                "vector_store_vectors": milvus_count,
                "vector_store_type": self.store_type,
                "vector_store_collection_exists": vector_store_exists,
                "vectorization_rate": round(vectorization_rate, 2)
            }
        except Exception as e:
            logger.error(f"获取向量化统计信息失败: {str(e)}", exc_info=True)
            return {
                "error": f"获取统计信息时出错: {str(e)}"
            }