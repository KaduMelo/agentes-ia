"""Client do MCP do Linear — onde o `escalator` abre o issue do handoff humano.

Servidor hospedado pelo próprio Linear (Streamable HTTP). O token sai de
`LINEAR_API_KEY` (Settings → Security & access → Personal API keys).
"""

from google.adk.tools.mcp_tool import McpToolset

from mcp_clients._connection import env, http_connection

_DEFAULT_URL = "https://mcp.linear.app/mcp"

# O escalonador só precisa abrir e reler issue — `list_teams` porque o
# `create_issue` do Linear exige o `teamId`. Filtrar mantém a function
# declaration curta e tira do modelo a chance de mexer em outra coisa.
_TOOL_FILTER = ["list_teams", "create_issue", "get_issue"]


def create_linear_toolset() -> McpToolset:
    """Toolset do Linear pronto para entrar em `Agent(tools=[...])`."""
    return McpToolset(
        connection_params=http_connection(
            server_name="linear_mcp",
            url=env("LINEAR_MCP_URL", _DEFAULT_URL),  # type: ignore[arg-type]
            token=env("LINEAR_API_KEY"),
        ),
        tool_filter=_TOOL_FILTER,
    )
