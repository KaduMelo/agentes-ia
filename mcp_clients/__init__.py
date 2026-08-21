"""Clients MCP dos servidores externos que os agentes usam como ferramenta.

Um módulo por servidor, cada um expondo uma factory `create_*_toolset()`. Os
agentes chamam a factory no import e não sabem de URL, token ou transporte —
tudo isso é configuração de ambiente, resolvida aqui.
"""
