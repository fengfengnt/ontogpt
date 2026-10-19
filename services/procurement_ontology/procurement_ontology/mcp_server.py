"""Two read tools; authenticated transport supplies identity outside tool arguments."""

from contextvars import ContextVar

from mcp.server import MCPServer

from .identity import Identity

current_identity: ContextVar[Identity | None] = ContextVar("procurement_mcp_identity", default=None)


def create_mcp(query):
    server = MCPServer("采购本体知识查询", log_level="WARNING")

    def identity():
        actor = current_identity.get()
        if actor is None or actor.scope_id == "platform":
            raise PermissionError("需要绑定企业的查询身份")
        return actor

    @server.tool(structured_output=True)
    def search_ontology_items(query: str, category_key: str) -> dict[str, object]:
        """搜索当前企业已发布的二级品类知识，返回实际版本。"""
        return query_service.search(identity(), query, category_key)

    @server.tool(structured_output=True)
    def get_ontology_item(item_id: str, observed_version: dict[str, str] | None = None) -> dict[str, object]:
        """读取当前企业条目、来源和一跳关系；版本变化时要求刷新。"""
        return query_service.get(identity(), item_id, observed_version)

    query_service = query
    return server
