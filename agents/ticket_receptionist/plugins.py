from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins import BasePlugin
from google.genai.types import Content
from google.genai import types
import logging

_RETRIABLE_LLM_ERRORS = ["MALFORMED_RESPONSE"]
_MAX_RETRIES = 5

_NUDGE = types.Content(
    role="user",
    parts=[
        types.Part(text=(
            "Your previous response had no content."
            "Please try again and provide a clear answer."
        ))
    ],
)

logger = logging.getLogger(__name__)


def _is_empty_response(llm_response: LlmResponse) -> bool:
    """Response that 'finished normally' but without any useful content."""
    if llm_response.partial:
        return False  # streaming chunk: a partial empty is normal
    if llm_response.error_code:
        return False  # already covered by the error path
    if llm_response.content and llm_response.content.parts:
        for part in llm_response.content.parts:
            if part.thought:
                continue  # a thought alone is not a useful response
            if (part.text or part.function_call or part.function_response
                    or part.inline_data or part.executable_code
                    or part.code_execution_result):
                return False  # it has real content
    return True


class ModelRetryPlugin(BasePlugin):

    _pending_requests: dict[str, LlmRequest] = {}

    def __init__(self, name=None):
        self.name = name or "model_retry_plugin"

    async def before_model_callback(self, *, callback_context: CallbackContext, llm_request: LlmRequest) -> LlmResponse | None:
        """before_model: stores the request for a possible retry in after_model."""
        self._pending_requests[callback_context.invocation_id] = llm_request
        return None  # None = follow the normal flow

    async def after_model_callback(self, *, callback_context: CallbackContext, llm_response: LlmResponse) -> LlmResponse | None:
        llm_request = self._pending_requests.pop(
            callback_context.invocation_id, None)

        code = getattr(llm_response.error_code,
                       "name", llm_response.error_code)
        if (code not in _RETRIABLE_LLM_ERRORS and not _is_empty_response(llm_response)) or llm_request is None:
            return None

            # copy with the nudge appended — a DIFFERENT request from the one that failed
        retry_request = llm_request.model_copy(deep=True)
        retry_request.contents = list(
            retry_request.contents or []) + [_NUDGE]

        llm = callback_context._invocation_context.agent.canonical_model  # type: ignore

        for attempt in range(1, _MAX_RETRIES + 1):
            logger.warning("Response %s; retry %d/%d",
                           code or "empty", attempt, _MAX_RETRIES)
            final_response = None
            async for response in llm.generate_content_async(retry_request, stream=False):
                final_response = response
            if (final_response is not None
                    and not final_response.error_code
                    and not _is_empty_response(final_response)):
                return final_response

        # exhausted: degrade gracefully instead of letting the turn die empty
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(text=(
                        "I had a technical problem while completing this step. "
                        "Could you resend your message, please?"
                    ))
                ],
            )
        )

    async def after_agent_callback(self, *, agent: BaseAgent, callback_context: CallbackContext) -> Content | None:
        self._pending_requests.pop(callback_context.invocation_id, None)
