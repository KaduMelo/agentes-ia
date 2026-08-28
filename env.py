"""Parâmetros de política lidos do ambiente, com default seguro para rodar local.

Ficam fora do código dos nodes porque são POLÍTICA de negócio (quanto o agente
pode estornar sozinho), não regra de fluxo — mudam por ambiente, sem deploy.
"""

import os

# Acima deste valor o refund deixa de ser automático e vai a aprovação humana.
REFUND_APPROVAL_THRESHOLD = float(os.getenv("REFUND_APPROVAL_THRESHOLD", "100"))

# Teto absoluto: acima disso nem com aprovação — vira handoff para um humano.
REFUND_MAX_LIMIT = float(os.getenv("REFUND_MAX_LIMIT", "500"))
