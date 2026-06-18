"""Graphiti / Neo4j 工具函数。

替代原 zep_paging.py，提供：
- Graphiti 客户端工厂（单例，持久化事件循环）
- 同步包装器（Flask 线程中安全调用 async Graphiti API）
- 全量节点/边查询（Neo4j Cypher）

架构说明：
  asyncio 的 async TCP 连接（Neo4j driver 底层）与创建它们的 event loop 绑定。
  若用 asyncio.run() 每次新建 loop，连接会因 "attached to a different loop" 出错。
  解决方案：一个常驻后台线程运行持久 event loop，所有 Graphiti 操作提交到该 loop 执行。
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from graphiti_core import Graphiti
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

from .logger import get_logger

logger = get_logger('mirofish.graphiti_utils')

_DEFAULT_MAX_NODES = 2000


class _AsyncLoopThread:
    """单一常驻后台线程，持有一个永不关闭的 event loop。

    所有 Graphiti / Neo4j async 操作都提交到这个 loop，
    确保 Neo4j async driver 的连接始终绑定到同一 loop。
    """

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_forever,
            daemon=True,
            name="graphiti-async-loop",
        )
        self._thread.start()

    def _run_forever(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro) -> Any:
        """提交协程并阻塞调用线程直到完成；异常会透传。"""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()


_async_loop_thread = _AsyncLoopThread()


def run_async(coro) -> Any:
    """在持久 event loop 线程中运行 async 协程（阻塞直到完成）。"""
    return _async_loop_thread.run(coro)


# ── Graphiti 客户端单例 ─────────────────────────────────────────────────────

_graphiti_client: Graphiti | None = None
_graphiti_client_lock = threading.Lock()


def _create_graphiti_client() -> Graphiti:
    from ..config import Config

    llm_client = OpenAIGenericClient(
        config=LLMConfig(
            api_key=Config.LLM_API_KEY,
            model=Config.LLM_MODEL_NAME,
            base_url=Config.LLM_BASE_URL,
        )
    )
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=Config.GRAPHITI_EMBEDDING_API_KEY,
            base_url=Config.GRAPHITI_EMBEDDING_BASE_URL,
            embedding_model=Config.GRAPHITI_EMBEDDING_MODEL,
        )
    )
    cross_encoder = OpenAIRerankerClient(
        config=LLMConfig(
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_BASE_URL,
        )
    )
    return Graphiti(
        uri=Config.NEO4J_URI,
        user=Config.NEO4J_USER,
        password=Config.NEO4J_PASSWORD,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder,
    )


def get_graphiti_client() -> Graphiti:
    """返回全局 Graphiti 单例（懒加载，线程安全）。

    首次调用时创建客户端；后续复用同一实例。
    所有操作通过 run_async() 在同一持久 event loop 中执行，
    避免 Neo4j async driver 跨 loop 问题。
    """
    global _graphiti_client
    if _graphiti_client is None:
        with _graphiti_client_lock:
            if _graphiti_client is None:
                logger.info("初始化 Graphiti 客户端...")
                _graphiti_client = _create_graphiti_client()
                run_async(_graphiti_client.build_indices_and_constraints())
                logger.info("Graphiti 客户端初始化完成（Neo4j 索引已建立）")
    return _graphiti_client


async def _fetch_all_nodes_async(
    client: Graphiti,
    group_id: str,
    max_items: int = _DEFAULT_MAX_NODES,
) -> list[dict[str, Any]]:
    """异步：通过 Neo4j Cypher 获取 group_id 下的所有实体节点。"""
    cypher = """
    MATCH (n:Entity)
    WHERE n.group_id = $group_id
    RETURN n.uuid AS uuid,
           n.name AS name,
           n.summary AS summary,
           labels(n) AS labels,
           n.attributes AS attributes
    LIMIT $limit
    """
    result = await client.driver.execute_query(
        cypher,
        {"group_id": group_id, "limit": max_items},
    )
    records = result.records if hasattr(result, 'records') else result[0]

    nodes = []
    for r in records:
        raw_labels = r.get("labels") or []
        nodes.append({
            "uuid": r.get("uuid") or "",
            "name": r.get("name") or "",
            "summary": r.get("summary") or "",
            "labels": list(raw_labels),
            "attributes": r.get("attributes") or {},
        })

    logger.debug(f"fetch_all_nodes: group_id={group_id}, count={len(nodes)}")
    if len(nodes) >= max_items:
        logger.warning(f"节点数达到上限 {max_items}，graph={group_id}，可能存在截断")
    return nodes


async def _fetch_all_edges_async(
    client: Graphiti,
    group_id: str,
) -> list[dict[str, Any]]:
    """异步：通过 Neo4j Cypher 获取 group_id 下的所有关系边。"""
    cypher = """
    MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity)
    WHERE r.group_id = $group_id
    RETURN r.uuid AS uuid,
           r.name AS name,
           r.fact AS fact,
           s.uuid AS source_node_uuid,
           t.uuid AS target_node_uuid,
           r.created_at AS created_at,
           r.valid_at AS valid_at,
           r.invalid_at AS invalid_at,
           r.expired_at AS expired_at
    """
    result = await client.driver.execute_query(
        cypher,
        {"group_id": group_id},
    )
    records = result.records if hasattr(result, 'records') else result[0]

    edges = []
    for r in records:
        edges.append({
            "uuid": r.get("uuid") or "",
            "name": r.get("name") or "",
            "fact": r.get("fact") or "",
            "source_node_uuid": r.get("source_node_uuid") or "",
            "target_node_uuid": r.get("target_node_uuid") or "",
            "created_at": r.get("created_at"),
            "valid_at": r.get("valid_at"),
            "invalid_at": r.get("invalid_at"),
            "expired_at": r.get("expired_at"),
            "attributes": {},
        })

    logger.debug(f"fetch_all_edges: group_id={group_id}, count={len(edges)}")
    return edges


async def _delete_group_async(client: Graphiti, group_id: str) -> None:
    """异步：删除 group_id 下的所有节点和边。"""
    await client.driver.execute_query(
        "MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity) WHERE r.group_id = $gid DELETE r",
        {"gid": group_id},
    )
    await client.driver.execute_query(
        "MATCH (n:EpisodicNode) WHERE n.group_id = $gid DELETE n",
        {"gid": group_id},
    )
    await client.driver.execute_query(
        "MATCH (n:Entity) WHERE n.group_id = $gid DETACH DELETE n",
        {"gid": group_id},
    )
    logger.info(f"已删除图谱数据: group_id={group_id}")


# ── 同步入口（供现有同步代码调用）────────────────────────────────────────────

def fetch_all_nodes(
    client: Graphiti,
    group_id: str,
    max_items: int = _DEFAULT_MAX_NODES,
) -> list[dict[str, Any]]:
    return run_async(_fetch_all_nodes_async(client, group_id, max_items))


def fetch_all_edges(
    client: Graphiti,
    group_id: str,
) -> list[dict[str, Any]]:
    return run_async(_fetch_all_edges_async(client, group_id))


def delete_group(client: Graphiti, group_id: str) -> None:
    run_async(_delete_group_async(client, group_id))
