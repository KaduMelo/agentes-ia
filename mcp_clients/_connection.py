"""Base comum dos clients MCP: transporte HTTP + bearer token do ambiente."""

import logging
import os

from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams

logger = logging.getLogger(__name__)

# Handshake + primeira listagem de tools; o default de 5s do ADK é curto demais
# para servidor hospedado.
_CONNECT_TIMEOUT = 15.0


def http_connection(
    *,
    server_name: str,
    url: str,
    token: str | None,
    timeout: float = _CONNECT_TIMEOUT,
) -> StreamableHTTPConnectionParams:
    """Parâmetros de conexão Streamable HTTP para `url`, com bearer opcional.

    Token ausente não levanta erro: o toolset é construído no import do agente e
    quebrar aí derrubaria o app inteiro (inclusive os fluxos que nem usam este
    servidor). Sem token a falha aparece na primeira chamada de tool, que os
    agentes já tratam devolvendo `status="error"`.
    """
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        logger.warning(
            "%s: sem token configurado — as chamadas ao MCP vão falhar na "
            "autenticação até a variável de ambiente ser preenchida.",
            server_name,
        )

    return StreamableHTTPConnectionParams(
        url=url,
        headers=headers or None,
        timeout=timeout,
    )


def env(name: str, default: str | None = None) -> str | None:
    """`os.getenv` tratando string vazia como ausente (`.env` com chave em branco)."""
    value = os.getenv(name, "")
    return value.strip() or default
