from google.adk import Workflow
from google.adk.workflow import START
from agents.ticket_receptionist.agent import root_agent as ticket_receptionist_agent

root_agent = Workflow(
    name="ticket_resolution",
    description="This agent is responsible for resolving support tickets.",
    edges=[(START, ticket_receptionist_agent)]
)
