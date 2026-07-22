from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm

root_agent = Agent(
    name="agent_openai",
    # instruction="Voce é um especialista em Python"
    # instruction=(
    #     "Escreva um código Python que imprima 'Olá, Mundo!'"
    #     "Certifique-se de usar a função print() para exibir a mensagem."
    # ),
    instruction="""
        Escreva um código Python que imprima 'Olá, Mundo!' usando a função print().
        Certifique-se de que o código seja simples e fácil de entender.
    """,
    model=LiteLlm(model="openai/gpt-4o-mini")
)
