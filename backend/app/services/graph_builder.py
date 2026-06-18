"""
图谱构建服务
使用 Graphiti + Neo4j 自托管知识图谱（替代 Zep Cloud）
"""

import uuid
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.graphiti_utils import (
    get_graphiti_client, run_async,
    fetch_all_nodes, fetch_all_edges, delete_group,
)
from .text_processor import TextProcessor
from ..utils.locale import t, get_locale, set_locale
from ..utils.logger import get_logger

logger = get_logger('mirofish.graph_builder')

# Graphiti 保留属性名，不能用于自定义实体属性
_RESERVED_ATTRS = {'uuid', 'name', 'group_id', 'name_embedding', 'summary', 'created_at'}


@dataclass
class GraphInfo:
    """图谱信息"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


def _build_pydantic_entity_types(ontology: Dict[str, Any]) -> Dict[str, Any]:
    """将本体定义转换为 Graphiti 所需的 Pydantic entity_types 字典。"""
    from pydantic import BaseModel, Field
    from typing import Optional

    entity_types = {}
    for entity_def in ontology.get("entity_types", []):
        name = entity_def["name"]
        description = entity_def.get("description", f"A {name} entity.")
        attrs: Dict[str, Any] = {"__doc__": description, "__annotations__": {}}

        for attr_def in entity_def.get("attributes", []):
            attr_name = attr_def["name"]
            if attr_name.lower() in _RESERVED_ATTRS:
                attr_name = f"entity_{attr_name}"
            attr_desc = attr_def.get("description", attr_name)
            attrs[attr_name] = Field(default=None, description=attr_desc)
            attrs["__annotations__"][attr_name] = Optional[str]

        entity_class = type(name, (BaseModel,), attrs)
        entity_class.__doc__ = description
        entity_types[name] = entity_class

    return entity_types


def _build_pydantic_edge_types(ontology: Dict[str, Any]) -> Dict[str, Any]:
    """将本体定义转换为 Graphiti 所需的 Pydantic edge_types 字典。"""
    from pydantic import BaseModel, Field
    from typing import Optional

    edge_types = {}
    for edge_def in ontology.get("edge_types", []):
        name = edge_def["name"]
        description = edge_def.get("description", f"A {name} relationship.")
        attrs: Dict[str, Any] = {"__doc__": description, "__annotations__": {}}

        for attr_def in edge_def.get("attributes", []):
            attr_name = attr_def["name"]
            if attr_name.lower() in _RESERVED_ATTRS:
                attr_name = f"edge_{attr_name}"
            attr_desc = attr_def.get("description", attr_name)
            attrs[attr_name] = Field(default=None, description=attr_desc)
            attrs["__annotations__"][attr_name] = Optional[str]

        edge_class = type(name, (BaseModel,), attrs)
        edge_class.__doc__ = description
        edge_types[name] = edge_class

    return edge_types


def _build_edge_type_map(ontology: Dict[str, Any]) -> Dict[tuple, List[str]]:
    """构建 (source_type, target_type) -> [edge_names] 映射。"""
    edge_type_map: Dict[tuple, List[str]] = {}
    for edge_def in ontology.get("edge_types", []):
        edge_name = edge_def["name"]
        for st in edge_def.get("source_targets", []):
            key = (st.get("source", "Entity"), st.get("target", "Entity"))
            edge_type_map.setdefault(key, []).append(edge_name)
    return edge_type_map


class GraphBuilderService:
    """
    图谱构建服务
    负责调用 Graphiti API 构建知识图谱（自托管 Neo4j）
    """

    def __init__(self, api_key: Optional[str] = None):
        # api_key 参数保留以兼容现有调用，实际不使用（Graphiti 无 API Key）
        self.task_manager = TaskManager()

    def _make_client(self) -> Graphiti:
        return get_graphiti_client()

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """
        异步构建图谱（在背景线程中运行）

        Returns:
            任务ID
        """
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )
        current_locale = get_locale()

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size, current_locale),
            daemon=True,
        )
        thread.start()
        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
        locale: str = 'zh',
    ):
        """图谱构建工作线程（在独立线程中使用 asyncio.run）"""
        set_locale(locale)
        client = self._make_client()

        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message=t('progress.startBuildingGraph'),
            )

            # 1. 初始化 Neo4j 索引（首次建库时需要，幂等操作）
            run_async(client.build_indices_and_constraints())
            self.task_manager.update_task(
                task_id, progress=8,
                message=t('progress.graphCreated', graphId="graphiti"),
            )

            # 2. 生成 group_id（对应原来的 graph_id）
            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id, progress=10,
                message=t('progress.graphCreated', graphId=graph_id),
            )

            # 3. 将本体转换为 Pydantic 模型（随每个 episode 传入）
            entity_types = _build_pydantic_entity_types(ontology)
            edge_types = _build_pydantic_edge_types(ontology)
            edge_type_map = _build_edge_type_map(ontology)
            self.task_manager.update_task(
                task_id, progress=15,
                message=t('progress.ontologySet'),
            )

            # 4. 文本分块
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id, progress=20,
                message=t('progress.textSplit', count=total_chunks),
            )

            # 5. 逐块写入 Graphiti（add_episode 完成即处理完，无需轮询）
            self._add_chunks_to_graphiti(
                client=client,
                graph_id=graph_id,
                chunks=chunks,
                entity_types=entity_types,
                edge_types=edge_types,
                edge_type_map=edge_type_map,
                progress_callback=lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 0.70),  # 20-90%
                    message=msg,
                ),
            )

            # 6. 获取图谱信息
            self.task_manager.update_task(
                task_id, progress=90,
                message=t('progress.fetchingGraphInfo'),
            )
            graph_info = self._get_graph_info(client, graph_id)

            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })

        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"图谱构建失败: {error_msg}")
            self.task_manager.fail_task(task_id, error_msg)
        finally:
            run_async(client.close())

    def create_graph(self, name: str) -> str:
        """生成图谱 group_id（Graphiti 无需预先创建图谱）"""
        return f"mirofish_{uuid.uuid4().hex[:16]}"

    def _add_chunks_to_graphiti(
        self,
        client: Graphiti,
        graph_id: str,
        chunks: List[str],
        entity_types: Dict[str, Any],
        edge_types: Dict[str, Any],
        edge_type_map: Dict[tuple, List[str]],
        progress_callback: Optional[Callable] = None,
    ):
        """将文本块逐个写入 Graphiti。

        Graphiti 的 add_episode() 在 await 返回时已完成实体提取，
        无需像 Zep Cloud 那样轮询 episode 处理状态。
        """
        total = len(chunks)
        reference_time = datetime.now(timezone.utc)

        for i, chunk in enumerate(chunks):
            chunk_num = i + 1
            if progress_callback:
                progress_callback(
                    t('progress.sendingBatch', current=chunk_num, total=total, chunks=1),
                    i / total,
                )

            try:
                run_async(client.add_episode(
                    name=f"chunk_{chunk_num:04d}",
                    episode_body=chunk,
                    source_description="MiroFish document chunk",
                    reference_time=reference_time,
                    source=EpisodeType.text,
                    group_id=graph_id,
                    entity_types=entity_types if entity_types else None,
                    edge_types=edge_types if edge_types else None,
                    edge_type_map=edge_type_map if edge_type_map else None,
                ))

                # 短暂休眠避免 LLM API 过载
                if i < total - 1:
                    time.sleep(0.5)

            except Exception as e:
                logger.error(f"写入 chunk {chunk_num} 失败: {e}")
                if progress_callback:
                    progress_callback(
                        t('progress.batchFailed', batch=chunk_num, error=str(e)), 0,
                    )
                raise

        if progress_callback:
            progress_callback(
                t('progress.processingComplete', completed=total, total=total), 1.0,
            )

    def _get_graph_info(self, client: Graphiti, graph_id: str) -> GraphInfo:
        """获取图谱统计信息"""
        nodes = fetch_all_nodes(client, graph_id)
        edges = fetch_all_edges(client, graph_id)

        entity_types = set()
        for node in nodes:
            for label in node.get("labels", []):
                if label not in ("Entity", "Node"):
                    entity_types.add(label)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=list(entity_types),
        )

    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """获取完整图谱数据（含详细节点/边信息）"""
        client = self._make_client()
        try:
            nodes = fetch_all_nodes(client, graph_id)
            edges = fetch_all_edges(client, graph_id)

            node_map = {n["uuid"]: n["name"] for n in nodes}

            nodes_data = [
                {
                    "uuid": n["uuid"],
                    "name": n["name"],
                    "labels": n["labels"],
                    "summary": n["summary"],
                    "attributes": n["attributes"],
                    "created_at": None,
                }
                for n in nodes
            ]

            edges_data = [
                {
                    "uuid": e["uuid"],
                    "name": e["name"],
                    "fact": e["fact"],
                    "fact_type": e["name"],
                    "source_node_uuid": e["source_node_uuid"],
                    "target_node_uuid": e["target_node_uuid"],
                    "source_node_name": node_map.get(e["source_node_uuid"], ""),
                    "target_node_name": node_map.get(e["target_node_uuid"], ""),
                    "attributes": e["attributes"],
                    "created_at": str(e["created_at"]) if e["created_at"] else None,
                    "valid_at": str(e["valid_at"]) if e["valid_at"] else None,
                    "invalid_at": str(e["invalid_at"]) if e["invalid_at"] else None,
                    "expired_at": str(e["expired_at"]) if e["expired_at"] else None,
                    "episodes": [],
                }
                for e in edges
            ]

            return {
                "graph_id": graph_id,
                "nodes": nodes_data,
                "edges": edges_data,
                "node_count": len(nodes_data),
                "edge_count": len(edges_data),
            }
        finally:
            run_async(client.close())

    def delete_graph(self, graph_id: str):
        """删除图谱（按 group_id 清除所有关联节点和边）"""
        client = self._make_client()
        try:
            delete_group(client, graph_id)
        finally:
            run_async(client.close())
