from google.adk import Agent

root_agent = Agent(
    name="agent_gemini_flash",
    # instruction="Voce é um especialista em Python"
    # instruction=(
    #     "Escreva um código Python que imprima 'Olá, Mundo!'"
    #     "Certifique-se de usar a função print() para exibir a mensagem."
    # ),
    instruction="""
        Escreva um código Python que imprima 'Olá, Mundo!' usando a função print().
        Certifique-se de que o código seja simples e fácil de entender.
    """,
    model="gemini-flash-latest"
)
