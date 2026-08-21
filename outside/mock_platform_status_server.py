"""Mock da status page da Acme Cloud — equivale a `GET https://status.acme.com/api/v1/status`.

Síncrono porque a tool que o consome (`platform_status`) também é: a status page
real é um GET simples, sem estado do lado do agente.
"""

from typing import Any

# Estados possíveis por serviço: operational | degraded | outage | maintenance.
_SERVICES: dict[str, str] = {
    "api": "operational",
    "board": "degraded",
    "billing": "operational",
    "dashboard": "operational",
    "webhooks": "operational",
}

_OPEN_INCIDENTS: list[dict[str, Any]] = [
    {
        "id": "INC-1042",
        "service": "board",
        "summary": (
            "Lentidão ao abrir cards no board para uma parcela dos clientes. "
            "Causa identificada, correção em rollout."
        ),
        "status": "monitoring",
        "started_at": "2026-08-20T14:10:00Z",
    },
]


def get_service_status() -> dict[str, Any]:
    """Snapshot atual: `services` (serviço→estado) e `open_incidents`."""
    return {
        "services": dict(_SERVICES),
        "open_incidents": [dict(incident) for incident in _OPEN_INCIDENTS],
    }
