"""Mock do sistema de billing da Acme Cloud (o "outside" do agente).

Assíncrono de propósito: o billing real seria um HTTP externo, e as tools/nodes
já o consomem com `await`. Trocar por um client de verdade não muda a assinatura.

Formato de uma fatura:
    {"month": "YYYY-MM", "items": [{"id", "sku", "amount", "description"}, ...]}

Os SKUs seguem o vocabulário que o `refund_investigator` julga:
- `PLAN-*`      assinatura do plano — legítima UMA vez no mês; repetida = cobrança duplicada.
- `OVERAGE-*`   excedente de uso — sempre legítimo.
- `ADJ-*`       ajuste manual — indevido quando a `description` não traz justificativa.
"""

from datetime import datetime, timezone
from typing import Any

# `user` é o id default do usuário no dev UI do ADK, e o ticket guarda
# `customer_id = tool_context.user_id` — sem essa entrada, todo refund no dev UI
# cairia em "cliente sem fatura" e escalaria antes de exercitar a política.
DEFAULT_CUSTOMER_ID = "user"

_INVOICES: dict[str, list[dict[str, Any]]] = {
    DEFAULT_CUSTOMER_ID: [
        {
            "month": "2026-05",
            "items": [
                {"id": "itm-2605-1", "sku": "PLAN-PRO", "amount": 149.90,
                 "description": "Plano Pro — assinatura mensal"},
                {"id": "itm-2605-2", "sku": "ADJ-MIGRATION", "amount": 780.00,
                 "description": "Ajuste manual"},
            ],
        },
        {
            "month": "2026-06",
            "items": [
                {"id": "itm-2606-1", "sku": "PLAN-PRO", "amount": 149.90,
                 "description": "Plano Pro — assinatura mensal"},
                {"id": "itm-2606-2", "sku": "OVERAGE-API", "amount": 23.40,
                 "description": "Excedente de API — 234k chamadas acima da franquia"},
            ],
        },
        {
            "month": "2026-07",
            "items": [
                {"id": "itm-2607-1", "sku": "PLAN-PRO", "amount": 149.90,
                 "description": "Plano Pro — assinatura mensal"},
                {"id": "itm-2607-2", "sku": "PLAN-PRO", "amount": 149.90,
                 "description": "Plano Pro — assinatura mensal"},
                {"id": "itm-2607-3", "sku": "OVERAGE-API", "amount": 31.20,
                 "description": "Excedente de API — 312k chamadas acima da franquia"},
            ],
        },
        {
            "month": "2026-08",
            "items": [
                {"id": "itm-2608-1", "sku": "PLAN-PRO", "amount": 149.90,
                 "description": "Plano Pro — assinatura mensal"},
                {"id": "itm-2608-2", "sku": "ADJ-MANUAL", "amount": 49.90,
                 "description": "Ajuste manual"},
                {"id": "itm-2608-3", "sku": "ADJ-CREDIT", "amount": 15.00,
                 "description": "Ajuste manual — crédito de SLA do incidente INC-1042, aprovado pelo suporte"},
            ],
        },
    ],
    "customer_123": [
        {
            "month": "2026-07",
            "items": [
                {"id": "itm-123-2607-1", "sku": "PLAN-BASIC", "amount": 29.90,
                 "description": "Plano Basic — assinatura mensal"},
                {"id": "itm-123-2607-2", "sku": "OVERAGE-STORAGE", "amount": 8.75,
                 "description": "Excedente de storage — 35 GB acima da franquia"},
            ],
        },
    ],
}

# Ledger dos estornos emitidos, na ordem em que saíram. Só existe para o mock
# ser inspecionável (teste/demo): o billing real devolveria o id do provedor.
_REFUNDS: list[dict[str, Any]] = []


async def list_invoices(customer_id: str) -> list[dict[str, Any]]:
    """Faturas do cliente, da mais antiga para a mais recente.

    Cliente desconhecido devolve lista vazia — é o sinal que o
    `refund_investigator` lê como "não há fatura" e escala.
    """
    return [dict(invoice) for invoice in _INVOICES.get(customer_id, [])]


async def get_invoice(customer_id: str, month: str) -> dict[str, Any]:
    """Uma fatura pelo mês (`YYYY-MM`), ou `{"error": ...}` se não existir.

    Quem chama testa `"error" in inv` antes de olhar `items`.
    """
    for invoice in _INVOICES.get(customer_id, []):
        if invoice["month"] == month:
            return dict(invoice)
    return {"error": f"Nenhuma fatura de {month} para o cliente {customer_id}."}


async def issue_refund(customer_id: str, amount: float, reason: str) -> dict[str, Any]:
    """Emite o estorno e devolve o comprovante (`refund_id`, `status`)."""
    refund = {
        "refund_id": f"rfnd-{len(_REFUNDS) + 1:04d}",
        "customer_id": customer_id,
        "amount": round(float(amount), 2),
        "reason": reason,
        "status": "processed",
        "issued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _REFUNDS.append(refund)
    return refund


async def list_refunds(customer_id: str | None = None) -> list[dict[str, Any]]:
    """Estornos já emitidos — filtra por cliente quando `customer_id` vem."""
    if customer_id is None:
        return list(_REFUNDS)
    return [r for r in _REFUNDS if r["customer_id"] == customer_id]
