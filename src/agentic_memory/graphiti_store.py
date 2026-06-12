"""GraphitiMemoryStore — the real L4 temporal graph behind the ``MemoryStore`` seam.

Implements exactly the six seam primitives over graphiti-core's ``EntityNode`` /
``EntityEdge`` persistence (Neo4j backend; see ``docker-compose.yml``). All domain
writes/queries — ``write_requirements``, ``write_adr``, ``omitted_requirement_ids``,
``retrieve`` — are inherited from the shared ABC, so this store and the offline
``InMemoryMemoryStore`` behave identically by construction.

Per D10 (structured-first): nodes and edges are written deterministically from the
Pydantic artifacts. No LLM client is constructed anywhere in this module — Graphiti's
extraction/search stack is V2 surface.

Mapping decisions (D15):
- graphiti uuids are global primary keys while our node ids are per-``group_id``
  (the fake keys on ``(group_id, id)``), so uuids are namespaced ``{group_id}:{id}``
  and the domain id is preserved in ``attributes``.
- Neo4j properties cannot nest, so our ``attrs`` dict rides a single ``attrs_json``
  string attribute — proven lossless before the design was frozen.
- graphiti's API is async; the seam is sync. The store owns ONE persistent event
  loop on a daemon thread and submits every coroutine to it — the neo4j async
  driver binds its connection pool to the loop that first uses it, so per-call
  ``asyncio.run`` (fresh loop each time) breaks with "Future attached to a
  different loop". One loop per store instance is the correct bridge.

Imports of graphiti-core are lazy so the offline path (base env, no ``graph`` extra)
never needs the dependency (D11).
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from .artifacts import AgentPersona
from .graph import DEFAULT_GROUP, EdgeType, GraphEdge, GraphNode, MemoryStore, NodeType

# docker-compose.yml local-dev defaults (NOT secrets — override via NEO4J_* env).
_DEV_URI = "bolt://localhost:7687"
_DEV_USER = "neo4j"
_DEV_PASSWORD = "devpassword"


class GraphitiMemoryStore(MemoryStore):
    """The real shared temporal graph (L4). Drop-in for ``InMemoryMemoryStore``."""

    def __init__(
        self,
        driver: Any | None = None,
        *,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
    ) -> None:
        # One persistent loop on a daemon thread: the neo4j async driver binds its
        # connection pool to the loop that first runs it, so every coroutine for
        # this store MUST execute on the same loop (see module docstring).
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="graphiti-store-loop", daemon=True
        )
        self._thread.start()

        if driver is not None:
            self._driver = driver
        else:
            from graphiti_core.driver.neo4j_driver import Neo4jDriver  # lazy (D11)

            self._driver = Neo4jDriver(
                uri=uri or os.getenv("NEO4J_URI", _DEV_URI),
                user=user or os.getenv("NEO4J_USER", _DEV_USER),
                password=password or os.getenv("NEO4J_PASSWORD", _DEV_PASSWORD),
                database=database,
            )

    def _run(self, coro: Any, *, timeout: float = 60.0) -> Any:
        """Submit a coroutine to the store's loop and wait for the result."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)

    def close(self) -> None:
        """Release the driver and stop the store's event loop."""
        try:
            self._run(self._driver.close())
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5)

    # -- uuid namespacing ---------------------------------------------------

    @staticmethod
    def _uuid(group_id: str, node_id: str) -> str:
        # ":" is the namespace delimiter — a colon inside either component would
        # let two different (group, id) pairs collide on the same uuid.
        if ":" in group_id:
            raise ValueError(f"group_id must not contain ':' — got {group_id!r}")
        return f"{group_id}:{node_id}"

    # -- mapping ------------------------------------------------------------

    def _to_entity_node(self, node: GraphNode) -> Any:
        from graphiti_core.nodes import EntityNode  # lazy

        return EntityNode(
            uuid=self._uuid(node.group_id, node.id),
            name=str(node.attrs.get("title") or node.attrs.get("text") or node.id),
            group_id=node.group_id,
            labels=[node.type.value],
            summary="",
            # graphiti's Neo4j save unconditionally calls db.create.setNodeVectorProperty,
            # which NPEs on null — its pipeline assumes embeddings always exist. V1 does
            # no semantic search (D10/D15), so a deterministic placeholder satisfies the
            # contract; V2's real embedder overwrites it.
            name_embedding=[0.0],
            attributes={
                "node_id": node.id,
                "node_type": node.type.value,
                "author": node.author.value,
                "canonical": node.canonical,
                "attrs_json": json.dumps(node.attrs, default=str),
            },
            created_at=node.created_at,
        )

    @staticmethod
    def _from_entity_node(en: Any) -> GraphNode:
        a = en.attributes or {}
        return GraphNode(
            id=a.get("node_id", en.uuid),
            type=NodeType(a["node_type"]),
            author=AgentPersona(a["author"]),
            group_id=en.group_id,
            attrs=json.loads(a.get("attrs_json", "{}")),
            canonical=bool(a.get("canonical", False)),
            created_at=en.created_at or datetime.now(timezone.utc),
        )

    def _to_entity_edge(self, edge: GraphEdge) -> Any:
        from graphiti_core.edges import EntityEdge  # lazy

        return EntityEdge(
            uuid=self._uuid(edge.group_id, edge.id),
            group_id=edge.group_id,
            source_node_uuid=self._uuid(edge.group_id, edge.src),
            target_node_uuid=self._uuid(edge.group_id, edge.dst),
            name=edge.type.value,
            fact=f"{edge.src} {edge.type.value} {edge.dst}",
            fact_embedding=[0.0],  # same placeholder rationale as name_embedding above
            attributes={
                "edge_id": edge.id,
                "edge_type": edge.type.value,
                "src": edge.src,
                "dst": edge.dst,
                "author": edge.author.value,
                "attrs_json": json.dumps(edge.attrs, default=str),
            },
            created_at=edge.created_at,
        )

    @staticmethod
    def _from_entity_edge(ee: Any) -> GraphEdge:
        a = ee.attributes or {}
        return GraphEdge(
            id=a.get("edge_id", ee.uuid),
            type=EdgeType(a["edge_type"]),
            src=a.get("src", ee.source_node_uuid),
            dst=a.get("dst", ee.target_node_uuid),
            author=AgentPersona(a["author"]),
            group_id=ee.group_id,
            attrs=json.loads(a.get("attrs_json", "{}")),
            created_at=ee.created_at or datetime.now(timezone.utc),
        )

    # -- group discovery (for group_id=None spans) ---------------------------

    def _all_group_ids(self) -> list[str]:
        records, _, _ = self._run(
            self._driver.execute_query(
                "MATCH (n:Entity) WHERE n.group_id IS NOT NULL "
                "RETURN DISTINCT n.group_id AS group_id"
            )
        )
        return [r["group_id"] for r in records]

    # -- the six primitives ---------------------------------------------------

    def add_node(self, node: GraphNode) -> GraphNode:
        self._run(self._to_entity_node(node).save(self._driver))  # MERGE → upsert
        return node

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        self._run(self._to_entity_edge(edge).save(self._driver))
        return edge

    def get_node(self, node_id: str, *, group_id: str = DEFAULT_GROUP) -> GraphNode | None:
        from graphiti_core.errors import NodeNotFoundError  # lazy
        from graphiti_core.nodes import EntityNode  # lazy

        try:
            en = self._run(EntityNode.get_by_uuid(self._driver, self._uuid(group_id, node_id)))
        except NodeNotFoundError:
            return None
        return self._from_entity_node(en) if en is not None else None

    def nodes(
        self, *, type: NodeType | None = None, group_id: str | None = None
    ) -> list[GraphNode]:
        from graphiti_core.errors import GroupsNodesNotFoundError  # lazy
        from graphiti_core.nodes import EntityNode  # lazy

        gids = [group_id] if group_id is not None else self._all_group_ids()
        if not gids:
            return []
        try:
            ens = self._run(EntityNode.get_by_group_ids(self._driver, gids))
        except GroupsNodesNotFoundError:
            return []
        out = [self._from_entity_node(en) for en in ens]
        return [n for n in out if type is None or n.type == type]

    def edges(
        self,
        *,
        type: EdgeType | None = None,
        src: str | None = None,
        dst: str | None = None,
        group_id: str | None = None,
    ) -> list[GraphEdge]:
        from graphiti_core.edges import EntityEdge  # lazy
        from graphiti_core.errors import GroupsEdgesNotFoundError  # lazy

        gids = [group_id] if group_id is not None else self._all_group_ids()
        if not gids:
            return []
        try:
            ees = self._run(EntityEdge.get_by_group_ids(self._driver, gids))
        except GroupsEdgesNotFoundError:
            return []
        out = [self._from_entity_edge(ee) for ee in ees]
        return [
            e for e in out
            if (type is None or e.type == type)
            and (src is None or e.src == src)
            and (dst is None or e.dst == dst)
        ]

    def promote_canonical(self, node_id: str, *, group_id: str = DEFAULT_GROUP) -> None:
        node = self.get_node(node_id, group_id=group_id)
        if node is None:
            raise KeyError(f"no such node: {node_id} (group {group_id})")
        self.add_node(node.model_copy(update={"canonical": True}))


def make_memory_store(**kwargs: Any) -> MemoryStore:
    """The real-store factory — drop-in for ``InMemoryMemoryStore()`` in a live run.

    Connection resolution: explicit kwargs > ``NEO4J_URI``/``NEO4J_USER``/
    ``NEO4J_PASSWORD`` env > docker-compose local-dev defaults.
    """
    return GraphitiMemoryStore(**kwargs)
