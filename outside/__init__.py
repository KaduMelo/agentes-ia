"""Mocks dos sistemas EXTERNOS à central de atendimento.

Tudo aqui finge ser um serviço de terceiro (billing, status page): a mesma
interface que a versão real teria, com os dados em memória. Manter esses mocks
fora de `agents/` deixa explícito o que é fronteira do sistema — o dia que virar
HTTP de verdade, só o corpo das funções muda.
"""
