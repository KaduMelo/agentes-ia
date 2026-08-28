"""Client do MCP de conta — as ações que o `account_operator` executa.

Servidor interno da Acme (adicionar membro à equipe, etc.), apontado por
`ACCOUNT_MCP_URL`; `ACCOUNT_MCP_TOKEN` é o bearer, quando o servidor exigir.
"""

from google.adk.tools.mcp_tool import McpToolset

from mcp_clients._connection import env, http_connection

_DEFAULT_URL = "http://localhost:8765/mcp"

# Ações de conta são efeito colateral em sistema de produção: a lista explícita
# é o limite do que o agente pode executar. Ampliar aqui é decisão consciente.
_TOOL_FILTER = ["add_team_member"]


def create_account_toolset() -> McpToolset:
    """Toolset de conta pronto para entrar em `Agent(tools=[...])`."""
    return McpToolset(
        connection_params=http_connection(
            server_name="account_mcp",
            url=env("ACCOUNT_MCP_URL", _DEFAULT_URL),  # type: ignore[arg-type]
            token=env("ACCOUNT_MCP_TOKEN"),
        ),
        tool_filter=_TOOL_FILTER,
    )
