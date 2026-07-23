from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm

root_agent = Agent(
    name="agent_openai",
    # instruction="You are a Python expert"
    # instruction=(
    #     "Write Python code that prints 'Hello, World!'"
    #     "Make sure to use the print() function to display the message."
    # ),
    instruction="""
        Write Python code that prints 'Hello, World!' using the print() function.
        Make sure the code is simple and easy to understand.
    """,
    model=LiteLlm(model="openai/gpt-4o-mini")
)
