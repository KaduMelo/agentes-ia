from multiprocessing import Value
from typing import Any, Optional

from google.adk.agents import Agent
from google.adk.apps import App
from agents.ticket_receptionist.plugins import ModelRetryPlugin
from db.models import TicketModel, ClassificationModel
from google.adk.tools import ToolContext
from agents.ticket_receptionist.subagents.ticket_classifier.agent import (
    TicketClassifierOutput, ticket_classifier_subagent, CLASSIFIER_OUTPUT_KEY
)
from google.genai.types import Content
from db import repo
from google.adk.tools import BaseTool
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
import logging

logger = logging.getLogger(__name__)

TICKET_CREATED_KEY = "temp:ticket_created"


def _user_message(content: Content | None) -> str:
    if not content or not content.parts:
        return ""
    return "\n".join([part.text for part in content.parts if part.text])

# framework -> middleware -> service handleError
# controller|service


async def register_ticket(tool_context: ToolContext):
    """
    Registers a support ticket in Acme Cloud's service desk.
    Args:
        tool_context (ToolContext): The tool context, containing the ticket information.
    Returns:
        dict: A dictionary containing the status of the ticket registration.
    """

    if TICKET_CREATED_KEY in tool_context.state:
        return {"status": "error", "message": "The ticket has already been registered. It cannot be registered again."}

    if not CLASSIFIER_OUTPUT_KEY in tool_context.state:
        return {"status": "error", "message": "The ticket has not been classified. Please classify the ticket before registering it."}

    classification = TicketClassifierOutput.model_validate(
        tool_context.state[CLASSIFIER_OUTPUT_KEY])

    user_message = _user_message(tool_context.user_content)

    # raise Exception("database error")
    if not user_message:
        raise ValueError(
            "The user message is empty. The ticket cannot be registered.")

    ticket_created = await repo.create_ticket(
        TicketModel(
            customer_id=tool_context.user_id,
            message=user_message,
            classification=ClassificationModel(
                **classification.model_dump()
            )
        )
    )
    tool_context.state[TICKET_CREATED_KEY] = True

    return {"status": "success", "ticket_id": ticket_created.id}


# """
# - ABOUT THE USER MESSAGE USED FOR TICKET CLASSIFICATION:
# If you identify that the user message is too generic, without any detail or context,
# you must ask the user for more information before proceeding with the ticket classification.
# The user must provide specific steps or details about how, when and where the problem happened,
# or any other relevant information that can help classify the ticket.
# """

_INSTRUCTION_RECEPTIONIST = """
You are the Ticket Receptionist of Acme Cloud's service desk.
If the user asks about an already registered ticket, look up the ticket status and give an appropriate answer.
If the user asks to list tickets,
provide a list of the registered tickets according to the given criteria (for example, status, category, etc.).

If the user asks to create a ticket, ask what the ticket message is and then
trigger the ticket classification process and proceed with the ticket registration.

"""


def _handle_tool_error(
        tool: BaseTool,
        args: dict[str, Any], tool_context: ToolContext, error: Exception) -> dict | None:
    logger.error("Error while running tool %s: %s", tool.name, error)
    if isinstance(error, ValueError):
        return {"status": "error", "message": str(error)}
    return {
        "status": "error",
        "message": "An unexpected error occurred while processing your request."
    }


# _RETRIABLE_LLM_ERRORS = ["MALFORMED_RESPONSE"]
# _MAX_RETRIES = 5

# # in-flight requests, per invocation (the LLM calls of an invocation are sequential)
# _pending_requests: dict[str, LlmRequest] = {}


# def capture_request_callback(
#     callback_context: CallbackContext, llm_request: LlmRequest
# ) -> Optional[LlmResponse]:
#     """before_model: stores the request for a possible retry in after_model."""
#     _pending_requests[callback_context.invocation_id] = llm_request
#     return None  # None = follow the normal flow

# def _is_empty_response(llm_response: LlmResponse) -> bool:
#     """Response that 'finished normally' but without any useful content."""
#     if llm_response.partial:
#         return False  # streaming chunk: a partial empty is normal
#     if llm_response.error_code:
#         return False  # already covered by the error path
#     if llm_response.content and llm_response.content.parts:
#         for part in llm_response.content.parts:
#             if part.thought:
#                 continue  # a thought alone is not a useful response
#             if (part.text or part.function_call or part.function_response
#                     or part.inline_data or part.executable_code
#                     or part.code_execution_result):
#                 return False  # it has real content
#     return True


# _NUDGE = types.Content(
#     role="user",
#     parts=[
#         types.Part(text=(
#             "Your previous response had no content."
#             "Please try again and provide a clear answer."
#         ))
#     ],
# )


# async def retry_malformed_callback(
#     callback_context: CallbackContext, llm_response: LlmResponse
# ) -> Optional[LlmResponse]:
#     llm_request = _pending_requests.pop(callback_context.invocation_id, None)

#     code = getattr(llm_response.error_code, "name", llm_response.error_code)
#     if (code not in _RETRIABLE_LLM_ERRORS and not _is_empty_response(llm_response)) or llm_request is None:
#         return None

#     # copy with the nudge appended — a DIFFERENT request from the one that failed
#     retry_request = llm_request.model_copy(deep=True)
#     retry_request.contents = list(retry_request.contents or []) + [_NUDGE]

#     llm = callback_context._invocation_context.agent.canonical_model  # type: ignore

#     for attempt in range(1, _MAX_RETRIES + 1):
#         logger.warning("Response %s; retry %d/%d",
#                        code or "empty", attempt, _MAX_RETRIES)
#         final_response = None
#         async for response in llm.generate_content_async(retry_request, stream=False):
#             final_response = response
#         if (final_response is not None
#                 and not final_response.error_code
#                 and not _is_empty_response(final_response)):
#             return final_response

#     # exhausted: degrade gracefully instead of letting the turn die empty
#     return LlmResponse(
#         content=types.Content(
#             role="model",
#             parts=[
#                 types.Part(text=(
#                     "I had a technical problem while completing this step. "
#                     "Could you resend your message, please?"
#                 ))
#             ],
#         )
#     )

# def cleanup_pending_requests_callback(callback_context: CallbackContext) -> None:
#     _pending_requests.pop(callback_context.invocation_id, None)

root_agent = Agent(
    name="ticket_receptionist",
    description="Responsible for receiving Acme Cloud support tickets and classifying them.",
    model="gemini-3.5-flash-lite",
    instruction=_INSTRUCTION_RECEPTIONIST,
    sub_agents=[
        ticket_classifier_subagent
    ],
    mode="chat",
    tools=[register_ticket],
    on_tool_error_callback=_handle_tool_error,
    # before_model_callback=capture_request_callback,
    # after_model_callback=retry_malformed_callback,
    # after_agent_callback=cleanup_pending_requests_callback,
)

app = App(
    root_agent=root_agent,
    name="ticket_receptionist",
    plugins=[ModelRetryPlugin()]
)
