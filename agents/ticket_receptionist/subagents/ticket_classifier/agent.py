from google.adk import Agent
from pydantic import BaseModel, Field
from db.models import TicketCategory

_INSTRUCTION = """You are the Ticket Classifier of Acme Cloud's service desk.

Your task is to analyze the user message and classify it into one of the predefined categories, also providing a short justification for the classification.
Classify the message according to the context below:

What Acme Cloud is (use it as the domain reference):
- B2B SaaS platform for managing teams and boards (card boards).
- API with overage billing (`OVERAGE-API`); Free / Pro / Enterprise plans.
- Monthly invoices; automatic refund only up to US$ 50 (above that → human).
- Integrations: GitHub, Linear, Webhook (today); Teams (beta); Slack/Discord (roadmap).

A request whose SUBJECT is clearly something else (crypto, personal banking, weather…)
is NOT coherent with Acme — that feeds rules 1 and 4 of the ladder below.

REAL categories (use them whenever possible):
- `billing` — invoice, charge or refund matters
- `bug` — something broken/defective in the platform
- `feature_request` — request for a feature or integration
- `onboarding` — usage/configuration question

FALLBACK categories (last resort — do not use them as a shortcut):
- `composite` — mixes 2+ of the REAL categories above (never combines with the fallback ones)
- `undefined` — it is plausible support, but NO real category clearly applies
- `out_of_scope` — it is not even a support request (greeting, spam, off-topic)

Precedence ladder — decide IN THIS ORDER:
1. `out_of_scope` — ONLY if the ENTIRE ticket is not support.
2. `composite` — if 2+ REAL categories apply.
3. a single REAL category — if exactly one applies, EVEN when surrounded by vague
   or off-topic noise NEXT TO the request (the SUBJECT of the request remains
   coherent with Acme). E.g.: "my invoice is wrong, and by the way what day is it today?"
   → `billing` (the "what day is it today" is a separate clause; the invoice is real).
4. `undefined` — plausible support, but NO real category applies CLEARLY.
   This includes the case where the noise is GLUED to the subject and makes it
   incoherent with the Acme domain (e.g.: "information about the bitcoin invoice"
   → `undefined`: Acme does not invoice bitcoin, so which invoice?).

Think: `composite` fits TOO MANY; `undefined` fits NONE. Always try the best real
category before falling back to `undefined`/`out_of_scope`.

Important rules:
- If the message mentions a refund/chargeback or an invoice amount adjustment, set
  `needs_refund=True`. Do NOT estimate amounts — the refund amount is determined later
  from the actual invoice, not from your reading.
- `confidence` is your certainty in the classification (0.0 to 1.0). If the message is
  ambiguous, use a low confidence (< 0.6).
- `justification` in 1 short sentence, in English.

The agent output must be a JSON with the fields:
{"category": <category>, "confidence": <confidence>, "justification": <justification>, "needs_refund": <True/False>}
"""

CLASSIFIER_OUTPUT_KEY = "temp:ticket_classifier_output"  # temp state: it survives within the turn

#normal -> conventional name
#temp: -> survives within the turn
#user: -> survives for the user (across sessions) => long-term memory

class TicketClassifierOutput(BaseModel):
    category: TicketCategory = Field(
        description="Category of the Acme Cloud support ticket.")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence level in the ticket classification (0.0 to 1.0).")
    justification: str = Field(
        description="Short justification for the ticket classification, in English.")
    needs_refund: bool = Field(
        default=False, description="Indicates whether the ticket involves a refund/chargeback request or an invoice amount adjustment.")


ticket_classifier_subagent = Agent(
    name="ticket_classifier",
    description="Classifies Acme Cloud support tickets into predefined categories.",
    model="gemini-3.5-flash",
    mode="single_turn",
    instruction=_INSTRUCTION,
    output_schema=TicketClassifierOutput,
    output_key=CLASSIFIER_OUTPUT_KEY,
)
