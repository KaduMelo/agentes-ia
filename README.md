# agentes-ia — Acme Cloud AI Support Desk

A hands-on lab of **Google ADK 2.5** agents that simulate the support desk of *Acme
Cloud*, a fictional B2B SaaS (team + card boards, API overage billing, Free/Pro/
Enterprise plans).

The repo is organized around two production-shaped flows:

| Flow | What it does | Kind |
| --- | --- | --- |
| **`ticket_receptionist`** | Talks to the customer, classifies the message, persists the ticket | LLM agent + sub-agent |
| **`ticket_resolution`** | Picks up a persisted ticket and *resolves* it: general support, account actions, refunds, human escalation | Deterministic `Workflow` graph + LLM agents |

Everything the agents touch outside the desk itself (billing, status page, Linear,
the account service) is either an in-memory mock under [outside/](outside/) or a
remote **MCP** server wired through [mcp_clients/](mcp_clients/).

---

## Table of contents

- [Architecture at a glance](#architecture-at-a-glance)
- [Repository map](#repository-map)
- [Requirements and setup](#requirements-and-setup)
- [Environment variables](#environment-variables)
- [Running the agents](#running-the-agents)
- [Agent catalog](#agent-catalog)
- [Agent: ticket_receptionist](#agent-ticket_receptionist)
- [Agent: ticket_resolution](#agent-ticket_resolution)
  - [Workflow graph](#workflow-graph)
  - [Nodes](#nodes)
  - [Sub-agents](#sub-agents)
  - [Refund policy](#refund-policy)
  - [Human-in-the-loop approval](#human-in-the-loop-approval)
- [Standalone / lab agents](#standalone--lab-agents)
- [Dev clones](#dev-clones)
- [Tools reference](#tools-reference)
- [External systems (mocks)](#external-systems-mocks)
- [MCP clients](#mcp-clients)
- [Data model](#data-model)
- [Database](#database)
- [End-to-end walkthrough](#end-to-end-walkthrough)
- [Conventions and gotchas](#conventions-and-gotchas)
- [Managing dependencies](#managing-dependencies)

---

## Architecture at a glance

```mermaid
flowchart LR
    subgraph intake["Intake — agents/ticket_receptionist"]
        R[ticket_receptionist<br/>chat agent] --> C[ticket_classifier<br/>single_turn + output_schema]
        R --> RT[[register_ticket]]
    end

    RT --> DB[(tickets<br/>SQLite / Postgres)]

    subgraph resolution["Resolution — agents/ticket_resolution"]
        W[Workflow graph<br/>deterministic nodes] --> A[attendant]
        W --> RI[refund_investigator]
        W --> E[escalator]
        A --> AO[account_operator]
    end

    DB --> W
    W --> DB

    A --> PS[[platform_status]]
    RI --> BI[[find_invoices]]
    E --> LIN{{Linear MCP}}
    AO --> ACC{{Account MCP}}
    PS --> MS[outside/mock_platform_status_server]
    BI --> MB[outside/mock_billing_server]
    W --> MB
```

Two design rules run through the whole codebase:

1. **The LLM judges, the code decides.** The `refund_investigator` points at
   invoice *lines*; the amount is summed and compared against thresholds by plain
   Python in [nodes.py](agents/ticket_resolution/nodes.py). Money never depends on a
   model's arithmetic.
2. **The boundary is explicit.** Anything that would be a third-party HTTP call in
   production lives in [outside/](outside/) or [mcp_clients/](mcp_clients/), with the
   same signature the real client would have.

---

## Repository map

```
.
├── agents/
│   ├── ticket_receptionist/        # intake: classify + register the ticket
│   │   ├── agent.py                # root_agent + App(plugins=[ModelRetryPlugin])
│   │   ├── plugins.py              # retry plugin for malformed/empty LLM responses
│   │   └── subagents/ticket_classifier/
│   ├── ticket_resolution/          # resolution workflow (ADK Workflow graph)
│   │   ├── agent.py                # the graph: nodes + routing edges
│   │   ├── nodes.py                # deterministic nodes (triage, refund gate, HITL)
│   │   ├── agents/                 # attendant, refund_investigator, escalator, account_operator
│   │   └── tools/                  # billing, platform status, escalation persistence
│   ├── account_operator/           # standalone demo agent (tool confirmation + password)
│   └── agent_openai/               # LiteLLM smoke test (OpenAI model through ADK)
├── db/                             # SQLAlchemy async models, engine, repository, reset
├── outside/                        # in-memory mocks of external systems
├── mcp_clients/                    # MCP toolset factories (Linear, Account)
├── env.py                          # business-policy thresholds read from the environment
├── docker-compose.yml              # optional local Postgres
└── pyproject.toml / uv.lock        # deps, locked
```

---

## Requirements and setup

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Python **3.14** (uv downloads it automatically from `.python-version`)
- A Google AI Studio API key (all production agents run on Gemini models)

```bash
git clone git@github.com:KaduMelo/agentes-ia.git
cd agentes-ia

uv sync                       # creates .venv/ from pyproject.toml + uv.lock
source .venv/bin/activate     # optional; `uv run` works without it

cp .env.example .env          # then fill in the keys
```

The project root must be on `PYTHONPATH` — the agents import `db`, `outside` and
`mcp_clients` as top-level packages. [.vscode/settings.json](.vscode/settings.json)
already sets it for VS Code terminals; in a bare shell, export it:

```bash
export PYTHONPATH="$PWD"
export ADK_SUPPRESS_EXPERIMENTAL_FEATURE_WARNINGS=1
```

The tables are created lazily by SQLAlchemy metadata; to (re)create them from
scratch:

```bash
uv run python -m db.reset      # DROP ALL + CREATE ALL
```

---

## Environment variables

From [.env.example](.env.example):

| Variable | Used by | Default | Notes |
| --- | --- | --- | --- |
| `GOOGLE_API_KEY` | every Gemini agent | — | required |
| `ANTHROPIC_API_KEY` | reserved for LiteLLM experiments | — | optional |
| `OPENAI_API_KEY` | [agent_openai](agents/agent_openai/agent.py) | — | optional |
| `REFUND_APPROVAL_THRESHOLD` | [env.py](env.py) | `100` | above this, a refund needs human approval |
| `REFUND_MAX_LIMIT` | [env.py](env.py) | `500` | absolute ceiling: above it, never auto-refund — hand off |
| `LINEAR_MCP_URL` | [linear_mcp.py](mcp_clients/linear_mcp.py) | `https://mcp.linear.app/mcp` | hosted MCP server |
| `LINEAR_API_KEY` | idem | — | Linear → Settings → Security & access → Personal API keys |
| `ACCOUNT_MCP_URL` | [account_mcp.py](mcp_clients/account_mcp.py) | `http://localhost:8765/mcp` | internal account MCP server |
| `ACCOUNT_MCP_TOKEN` | idem | — | bearer token, when the server requires one |
| `DATABASE_URL` | [db/engine.py](db/engine.py) | `sqlite+aiosqlite:///agents/tickets.db` | see [Database](#database) |

Refund thresholds live in the environment on purpose: they are **business policy**
(how much the agent may refund on its own), not flow logic — they change per
environment, without a deploy.

A missing MCP token does **not** crash the app at import time. The toolset is built
when the agent module is imported, so failing there would take down every flow,
including the ones that never touch that server. Without a token the failure
surfaces on the first tool call, which the agents already handle by returning
`status="error"` (see [_connection.py](mcp_clients/_connection.py)).

---

## Running the agents

Everything runs through the ADK dev UI. Start it **from the repository root** so the
`db` / `outside` / `mcp_clients` imports resolve:

```bash
uv run adk web .
# → http://127.0.0.1:8000/dev-ui/
```

Apps are discovered as dotted module paths. Pick one from the dropdown or address it
directly in the URL:

| App name | Entry point |
| --- | --- |
| `agents.ticket_receptionist` | [agents/ticket_receptionist/agent.py](agents/ticket_receptionist/agent.py) |
| `agents.ticket_resolution` | [agents/ticket_resolution/agent.py](agents/ticket_resolution/agent.py) |
| `agents.account_operator` | [agents/account_operator/agent.py](agents/account_operator/agent.py) |
| `agents.agent_openai` | [agents/agent_openai/agent.py](agents/agent_openai/agent.py) |
| `agents.ticket_resolution.agents.<name>.<name>_dev` | [dev clones](#dev-clones) |

```
http://127.0.0.1:8000/dev-ui/?app=agents.ticket_resolution
```

A headless HTTP API is available with the same app names:

```bash
uv run adk api_server .        # http://127.0.0.1:8000
curl http://127.0.0.1:8000/list-apps
```

> **`ticket_resolution` needs a seeded session state.** The workflow reads
> `ticket_id` from the session state — it does *not* parse it out of the chat
> message. Create the session with the initial state before sending anything:
>
> ```bash
> curl -X POST http://127.0.0.1:8000/apps/agents.ticket_resolution/users/user/sessions \
>   -H 'Content-Type: application/json' \
>   -d '{"state": {"ticket_id": "TCK-99B0FBD7"}}'
> ```
>
> In the dev UI, use the **State** tab of a new session to set `ticket_id`.

Each app keeps its dev-UI sessions in `<app-name>/.adk/session.db` (gitignored).

---

## Agent catalog

| Agent | File | Model | Mode | Output schema | Tools / sub-agents |
| --- | --- | --- | --- | --- | --- |
| `ticket_receptionist` | [agent.py](agents/ticket_receptionist/agent.py) | `gemini-3.5-flash-lite` | `chat` | — | `register_ticket`; sub-agent `ticket_classifier` |
| `ticket_classifier` | [agent.py](agents/ticket_receptionist/subagents/ticket_classifier/agent.py) | `gemini-3.5-flash` | `single_turn` | `TicketClassifierOutput` | — |
| `ticket_resolution` | [agent.py](agents/ticket_resolution/agent.py) | — (graph) | — | — | 8 nodes + 3 agents |
| `attendant` | [agent.py](agents/ticket_resolution/agents/attendant/agent.py) | `gemini-3.5-flash` | — | `AttendantOutput` | `platform_status`, `AgentTool(account_operator)` |
| `account_operator` | [agent.py](agents/ticket_resolution/agents/account_operator/agent.py) | `gemini-3.5-flash` | — | `AccountOperatorOutput` | Account MCP toolset |
| `refund_investigator` | [agent.py](agents/ticket_resolution/agents/refund_investigator/agent.py) | `gemini-3.5-flash` | — | `RefundInvestigatorOutput` | `find_invoices` |
| `escalator` | [agent.py](agents/ticket_resolution/agents/escalator/agent.py) | `gemini-3.5-flash` | — | `EscalatorOutput` (in: `EscalatorInput`) | `get_ticket_escalation`, `create_ticket_escalation`, Linear MCP |
| `account_operator` (standalone) | [agent.py](agents/account_operator/agent.py) | `gemini-3.1-flash-lite` | — | — | `list_invoices`, `get_subscription`, `cancel_subscription` |
| `agent_openai` | [agent.py](agents/agent_openai/agent.py) | `openai/gpt-4o-mini` via LiteLLM | — | — | — |

---

## Agent: ticket_receptionist

The front door. It chats with the customer, delegates classification to a
single-turn sub-agent, and persists the ticket.

```mermaid
flowchart TD
    U([customer message]) --> R[ticket_receptionist]
    R -->|transfers| C[ticket_classifier]
    C -->|writes temp:ticket_classifier_output| S[(session state)]
    R --> T[[register_ticket]]
    S --> T
    T --> DB[(tickets row<br/>status = pending)]
    T --> ID([Ticket ID: TCK-XXXXXXXX])
```

### Classification taxonomy

The classifier ([agent.py](agents/ticket_receptionist/subagents/ticket_classifier/agent.py))
emits a `TicketClassifierOutput`:

```json
{"category": "bug", "confidence": 1.0, "justification": "…", "needs_refund": false}
```

**Real categories** — `billing`, `bug`, `feature_request`, `onboarding`.
**Fallback categories** — `composite` (two or more real ones), `undefined`
(plausible support, no real category fits), `out_of_scope` (not a support request
at all).

The prompt encodes an explicit **precedence ladder**, decided in this order:

1. `out_of_scope` — only if the *entire* ticket is not support.
2. `composite` — if 2+ real categories apply.
3. a single real category — even when surrounded by off-topic noise *next to* the
   request ("my invoice is wrong, and by the way what day is it today?" → `billing`).
4. `undefined` — plausible support, but no real category applies clearly; this also
   covers noise *glued* to the subject ("information about the bitcoin invoice").

Two rules matter downstream: `needs_refund=True` whenever the message mentions a
refund/chargeback or an invoice adjustment (and the model must **never** estimate an
amount — the amount comes from the real invoice later), and `confidence < 0.6` for
ambiguous messages, which is exactly the threshold the resolution triage uses.

### State keys

| Key | Scope | Meaning |
| --- | --- | --- |
| `temp:ticket_classifier_output` | turn-scoped | classifier output, read by `register_ticket` |
| `temp:ticket_created` | turn-scoped | idempotency guard: blocks a second registration |

ADK state prefixes used across the project: no prefix → conventional session state;
`temp:` → survives only within the turn; `user:` → survives across sessions for the
user (long-term memory).

### Guardrails

- **`register_ticket` refuses to run twice** (`temp:ticket_created`) and refuses to
  run before classification (`temp:ticket_classifier_output` missing).
- **`on_tool_error_callback`** turns exceptions into `{"status": "error", …}`,
  exposing `ValueError` messages verbatim and masking everything else.
- **`ModelRetryPlugin`** ([plugins.py](agents/ticket_receptionist/plugins.py)) is
  registered on the `App`. It captures each `LlmRequest` in `before_model_callback`,
  and in `after_model_callback` detects a `MALFORMED_RESPONSE` or a response that
  "finished normally" with no usable content (text, function call, inline data,
  code). It retries up to **5** times with a nudge message appended to a *copy* of
  the request, and — if all retries fail — degrades gracefully into a polite "please
  resend your message" instead of letting the turn die empty.

---

## Agent: ticket_resolution

An ADK `Workflow`: a deterministic graph where the LLM agents are steps, not the
orchestrator. It picks up a ticket already stored by the receptionist, resolves it,
and writes the outcome (`response`, `status`) back to the row.

### Workflow graph

```mermaid
flowchart TD
    START([START]) --> TT{triage_ticket_node}

    TT -->|refuse| RTN[refuse_ticket_node]
    TT -->|attendant| AT[attendant]
    TT -->|refund_investigator| RI[refund_investigator]

    AT --> FT[finish_ticket_node]

    RI --> TR{triage_refund_node}
    TR -->|auto_refund| AR[auto_refund_node]
    TR -->|escalate| ES[escalator]

    ES --> TE{triage_escalation_node}
    TE -->|refund_await_input| AW[await_refund_input_node<br/>⏸ RequestInput]
    TE -->|handoff| FE[finish_escalation_node]

    AW --> RC[refund_with_confirmation]

    RTN --> E([END])
    FT --> E
    AR --> E
    FE --> E
    RC --> E
```

Edges are declared in [agent.py](agents/ticket_resolution/agent.py); the routing keys
(`refuse`, `attendant`, `auto_refund`, …) are the values a node emits through
`EventActions(route=...)`.

### Nodes

Node parameters bind **from session state by name** (the ADK default,
`parameter_binding="state"`), except `node_input` (the previous step's output) and
`ctx` (the workflow context).

| Node | Reads | Decides / does |
| --- | --- | --- |
| `triage_ticket_node` | `ticket_id` → DB row | Loads the ticket, publishes `ticket_message`, `classification_justification`, `customer_id` into state. Routes `refuse` for `out_of_scope`, `refund_investigator` when `needs_refund and confidence >= 0.6`, else `attendant`. |
| `refuse_ticket_node` | `ticket_id` | Replies "this channel is Acme Cloud support only", marks `RESOLVED`. |
| `finish_ticket_node` | `AttendantOutput` | Persists the attendant message; `RESOLVED` on `success`, `FAILED` on `error`. |
| `triage_refund_node` | `RefundInvestigatorOutput`, `customer_id` | **The refund gate** — see below. |
| `auto_refund_node` | `AutoRefundRequest` | Calls `issue_refund`, writes the confirmation message, marks `RESOLVED`. |
| `triage_escalation_node` | `EscalatorOutput` | Only a *successful* `refund_confirmation` may pause the graph; everything else goes to `handoff`. |
| `finish_escalation_node` | `EscalatorOutput` | `ESCALATED`, or `FAILED` + `error` when the escalation itself failed. |
| `await_refund_input_node` | `ticket_id` | Marks `AWAITING_APPROVAL` and returns `RequestInput` — **pauses the graph**. |
| `refund_with_confirmation` | human answer + refund state | Approved → `issue_refund` + `RESOLVED`; refused → polite denial + `RESOLVED`. |

### Sub-agents

**`attendant`** — front line for general support (bug, how-to, onboarding,
configuration). It has [`platform_status`](agents/ticket_resolution/tools/platform_status_tool.py)
to correlate the complaint with an open incident, and reaches
`account_operator` through **`AgentTool`** (a tool call that returns control, not a
`sub_agents` transfer that would hand the conversation away). The prompt draws a
sharp line: *"add someone@x.com to the team"* is an account action → delegate;
*"how do I add a member?"* is a how-to → answer directly. Its `status` field is a
`Literal["success", "error"]` rather than a free `str`, so it becomes an enum in the
function declaration and the model cannot invent a third value that
`finish_ticket_node` would misread.

**`account_operator`** — executes account actions through the Account MCP toolset
(currently filtered to `add_team_member`). It may only report `added` /
`already_member` / `invalid_email` **after** the corresponding MCP response; if the
tool is missing or the call fails it must return `status="error"` so the ticket gets
routed to a human.

**`refund_investigator`** — judges refund policy and nothing else. It calls
`find_invoices` once, then classifies invoice lines:

| SKU pattern | Verdict |
| --- | --- |
| `PLAN-*` once in the month | legitimate — do not refund |
| `PLAN-*` duplicated in the month | **improper** — refund the extra copy |
| `OVERAGE-*` | legitimate — usage overage |
| `ADJ-*` with a justification in `description` | legitimate |
| `ADJ-*` without a justification | **improper** — refund |

It returns `decision` (`refund` / `escalate`), `month`, `item_ids` and a short
`reasoning`. It **never returns an amount** — only line ids.

**`escalator`** — creates the human handoff. Step 1: call `get_ticket_escalation` to
avoid duplicates (an existing record → `status="reused"`). Step 2: open the Linear
issue (title/body composed from `intent` + `summary` + ticket/customer ids, priority
from `severity`) and persist it with `create_ticket_escalation`, storing the Linear
issue id as `external_ref`. Its `intent` is echoed back exactly as received.

The escalation protocol embedded in the issue body
([ticket_escalation_tools.py](agents/ticket_resolution/tools/ticket_escalation_tools.py))
is what makes Linear a usable approval gate:

| Intent | Title prefix | Body protocol |
| --- | --- | --- |
| `refund_confirmation` | `[Aprovação humana]` | *To APPROVE, move this issue to Done; to REFUSE, move it to Canceled.* |
| `handoff` | `[Handoff humano]` | *No automatic resolution — a human must take over.* |

### Refund policy

`triage_refund_node` is the only place that decides money, and it does so in plain
Python:

```mermaid
flowchart TD
    V[RefundInvestigatorOutput] --> D{"decision == refund?"}
    D -->|no| H1[escalate · handoff<br/>severity = medium]
    D -->|yes| C[_compute_refundable:<br/>sum the real invoice lines]
    C -->|not_found| H2[escalate · handoff<br/>severity = low]
    C -->|invalid| H2
    C -->|"block_refund<br/>amount above REFUND_MAX_LIMIT"| H3[escalate · handoff<br/>severity = high]
    C -->|ok| T{"amount above REFUND_APPROVAL_THRESHOLD?"}
    T -->|yes| A[escalate · refund_confirmation<br/>→ human approval gate]
    T -->|no| AU[auto_refund_node<br/>refund issued automatically]
```

`_compute_refundable` reads the invoice for `month`, keeps only the lines whose ids
the investigator listed, and sums them — **no side effects**, so the gate can decide
before anything is paused or paid.

Severity is derived deterministically (`_escalation_severity`), never by the LLM:

| Situation | Severity | Why |
| --- | --- | --- |
| `block_refund` (above the absolute ceiling) | `high` | anomalous amount, possible abuse |
| `not_found` / `invalid` | `low` | data problem, no money at stake |
| approval with amount > 2× the threshold | `high` | large amount in the approval band |
| everything else | `medium` | investigator uncertainty, low band |

Note that `not_found`, `invalid` and `block_refund` **cannot** become an approval
gate — approving them would bypass the policy — so all three become a human handoff.

### Human-in-the-loop approval

`await_refund_input_node` returns an ADK `RequestInput`, which suspends the workflow
until an answer arrives:

```python
RequestInput(
    message="Aprovação humana necessária para o estorno. …",
    response_schema={"type": "object",
                     "properties": {"confirmed": {"type": "boolean"}}},
)
```

The `AWAITING_APPROVAL` status is written *by the node itself*, next to the pause —
the node knows the outcome, the caller doesn't — and the write is idempotent, so a
resume that re-runs the body sets the same value. Resuming with
`{"confirmed": true}` issues the refund; `{"confirmed": false}` closes the ticket
with a polite denial (still `RESOLVED` — the request was answered).

---

## Standalone / lab agents

**[`agents/account_operator`](agents/account_operator/agent.py)** — an independent
demo (not part of the resolution workflow) of ADK's **tool confirmation** flow. It
lists invoices, reads subscriptions and cancels them; when the subscription price is
above `HIGH_VALUE_THRESHOLD` (100) it calls `tool_context.request_confirmation(...)`
and requires the customer's password, returning `awaiting_confirmation` until the
user confirms. Fixture customers: `customer_123` (Pro, 149.90, password `1234`) and
`customer_456` (Basic, 29.90, password `5678`).

**[`agents/agent_openai`](agents/agent_openai/agent.py)** — a one-file smoke test
that a non-Google model works through ADK, via
`LiteLlm(model="openai/gpt-4o-mini")`. Needs `OPENAI_API_KEY`.

---

## Dev clones

Every agent that normally runs *inside* a flow has a `*_dev` sibling that re-exports
it as a chat app, so it can be exercised in isolation in the dev UI:

```python
root_agent = attendant_agent.clone(update={"mode": "chat"})
```

| Dev app | Clones |
| --- | --- |
| `agents.ticket_receptionist.subagents.ticket_classifier.ticket_classifier_dev` | `ticket_classifier` |
| `agents.ticket_resolution.agents.attendant.attendant_dev` | `attendant` |
| `agents.ticket_resolution.agents.account_operator.account_operator_dev` | `account_operator` |
| `agents.ticket_resolution.agents.refund_investigator.refund_investigator_dev` | `refund_investigator` |
| `agents.ticket_resolution.agents.escalator.escalator_dev` | `escalator` |

They are reachable by URL (`?app=<dotted name>`) even when the dropdown only lists
the top-level apps. Remember that the cloned prompts still interpolate state keys
(`{ticket_message}`, `{customer_id}`, `{ticket_id}`), so seed those in the session
state before chatting.

---

## Tools reference

| Tool | File | Signature | Purpose |
| --- | --- | --- | --- |
| `register_ticket` | [ticket_receptionist/agent.py](agents/ticket_receptionist/agent.py) | `(tool_context)` | Persists the classified ticket; returns `{"status", "ticket_id"}` |
| `platform_status` | [platform_status_tool.py](agents/ticket_resolution/tools/platform_status_tool.py) | `() -> dict` | Service states + open incidents (mirrors `GET /api/v1/status`) |
| `find_invoices` | [billing_tools.py](agents/ticket_resolution/tools/billing_tools.py) | `(customer_id) -> {"invoices": [...]}` | All invoices of the ticket's customer |
| `get_ticket_escalation` | [ticket_escalation_tools.py](agents/ticket_resolution/tools/ticket_escalation_tools.py) | `(ticket_id)` | `{"exists", "external_ref", "id"}` — duplicate guard |
| `create_ticket_escalation` | idem | `(ticket_id, customer_id, intent, summary, severity, external_ref)` | Persists the escalation; `created` / `reused` / `failed` |
| `list_invoices`, `get_subscription`, `cancel_subscription` | [account_operator/agent.py](agents/account_operator/agent.py) | — | Standalone demo agent only |

---

## External systems (mocks)

Everything under [outside/](outside/) pretends to be a third-party service with
in-memory data and the same interface the real one would expose. Billing functions
are `async` on purpose — the real billing would be an HTTP call, and the tools/nodes
already `await` them, so swapping in a real client won't change any signature.

### Billing — [mock_billing_server.py](outside/mock_billing_server.py)

`list_invoices`, `get_invoice`, `issue_refund`, `list_refunds`. Refunds are appended
to an in-memory ledger (`rfnd-0001`, …) so a demo run is inspectable.

Fixture data for customer **`user`** (the dev UI's default user id — the ticket
stores `customer_id = tool_context.user_id`, so without this entry every refund demo
would fall into "customer has no invoice"):

| Month | Lines | What it exercises |
| --- | --- | --- |
| `2026-05` | `PLAN-PRO` 149.90 + `ADJ-MIGRATION` 780.00 ("Ajuste manual") | Unjustified adjustment **above `REFUND_MAX_LIMIT`** → blocked, high-severity handoff |
| `2026-06` | `PLAN-PRO` 149.90 + `OVERAGE-API` 23.40 | Fully legitimate invoice → investigator escalates |
| `2026-07` | `PLAN-PRO` ×2 + `OVERAGE-API` 31.20 | **Duplicate plan charge** 149.90 → above the 100 threshold → human approval gate |
| `2026-08` | `PLAN-PRO` + `ADJ-MANUAL` 49.90 + `ADJ-CREDIT` 15.00 (justified: SLA credit for INC-1042) | Unjustified adjustment 49.90 → below the threshold → **automatic refund** |

Customer `customer_123` has a single legitimate `2026-07` invoice.

### Platform status — [mock_platform_status_server.py](outside/mock_platform_status_server.py)

Synchronous, like the real status page GET. Current snapshot: `board` is
**degraded**, everything else operational, with open incident **`INC-1042`**
("slowness opening cards on the board, cause identified, fix rolling out",
status `monitoring`). That incident is what the attendant cites when a customer
reports a 500 error on their board.

---

## MCP clients

[mcp_clients/](mcp_clients/) holds one module per MCP server, each exposing a
`create_*_toolset()` factory. Agents call the factory at import time and know
nothing about URLs, tokens or transport.

| Client | Server | Tool filter | Why filtered |
| --- | --- | --- | --- |
| [linear_mcp.py](mcp_clients/linear_mcp.py) | Linear's hosted MCP (Streamable HTTP) | `list_teams`, `create_issue`, `get_issue` | The escalator only needs to open and re-read an issue (`list_teams` because Linear's `create_issue` requires a `teamId`). A short function declaration also removes the chance of the model touching anything else. |
| [account_mcp.py](mcp_clients/account_mcp.py) | Acme's internal account server | `add_team_member` | Account actions are side effects in a production system: the explicit list *is* the boundary of what the agent may execute. |

[_connection.py](mcp_clients/_connection.py) builds the shared
`StreamableHTTPConnectionParams`: optional bearer header, and a **15s** connect
timeout because ADK's 5s default is too short for a hosted server's handshake plus
first tool listing.

---

## Data model

[db/models.py](db/models.py), SQLAlchemy 2 declarative + async.

### `tickets`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `String(64)` PK | generated as `TCK-XXXXXXXX` |
| `customer_id` | `String(64)`, indexed | the ADK `user_id` |
| `message` | `Text` | the original customer message |
| `status` | enum `TicketStatus` | default `pending` |
| `classification` | **composite** | flattened into `cls_category`, `cls_confidence`, `cls_justification`, `cls_needs_refund` |
| `response` | `Text?` | the final message sent to the customer |
| `error` | `Text?` | failure detail when the flow broke |
| `created_at` / `updated_at` | `DateTime(tz)` | `updated_at` refreshes on update |

`ClassificationModel` is an embedded **value object**, not a table or relationship:
it mirrors the classifier's schema and is read back as a single `classification`
object.

### `ticket_escalations`

`id`, `ticket_id` (unique), `title`, `body`, `severity` (`low|medium|high|urgent`),
`status` (default `open`), `external_ref` (the Linear issue id), timestamps.

### Enums

**`TicketCategory`** — `billing`, `bug`, `feature_request`, `onboarding`,
`composite`, `undefined`, `out_of_scope`, `security_incident`.

**`TicketStatus`** — `pending`, `awaiting_approval`, `resolved`, `escalated`,
`failed`, `auto_closed`.

Which node writes which status:

| Status | Written by |
| --- | --- |
| `pending` | `register_ticket` (default) |
| `resolved` | `refuse_ticket_node`, `finish_ticket_node` (success), `auto_refund_node`, `refund_with_confirmation` (both branches) |
| `awaiting_approval` | `await_refund_input_node` |
| `escalated` | `finish_escalation_node` |
| `failed` | `finish_ticket_node` (error), `finish_escalation_node` (escalation failed) |

---

## Database

Default: SQLite via `aiosqlite`, file at `agents/tickets.db` (gitignored). Override
with `DATABASE_URL`.

A Postgres 16 service is provided for a more production-like run:

```bash
docker compose up -d                      # exposes 5433 → acme/acme/acme
uv add asyncpg                            # not installed by default
export DATABASE_URL="postgresql+asyncpg://acme:acme@localhost:5433/acme"
uv run python -m db.reset
```

[db/repo.py](db/repo.py) is the whole persistence surface: `create_ticket`,
`update_ticket`, `get_ticket`, `create_ticket_escalation`, `get_ticket_escalation` —
each opening its own `async_session.begin()` transaction.

---

## End-to-end walkthrough

**1. Intake** — app `agents.ticket_receptionist`:

> *"Hi, I keep getting a 500 Internal Server Error when I try to open any card on my
> project board. It started this morning and happens every time — I've tried Chrome
> and Firefox, logged out and back in, nothing helps."*

The receptionist transfers to `ticket_classifier`, which returns
`{"category": "bug", "confidence": 1.0, "needs_refund": false, …}`; then
`register_ticket` persists the row and answers with the ticket id — e.g.
`TCK-99B0FBD7`.

**2. Resolution** — app `agents.ticket_resolution`, session seeded with
`{"ticket_id": "TCK-99B0FBD7"}`:

- `triage_ticket_node` loads the ticket, publishes `ticket_message`,
  `classification_justification` and `customer_id`, and routes → `attendant`
  (not `out_of_scope`, `needs_refund` false).
- `attendant` calls `platform_status`, finds `board: degraded` and incident
  `INC-1042`, and returns `{"status": "success", "message": "…"}` correlating the
  customer's 500 error with the incident.
- `finish_ticket_node` stores the message and marks the ticket `RESOLVED`.

**3. Refund variants** — seed a `billing` ticket with `needs_refund=true` and pick
the month from the [fixture table](#billing--mock_billing_serverpy):
`2026-08` → automatic refund; `2026-07` → Linear approval gate + `RequestInput`
pause; `2026-06` → escalation (legitimate invoice); `2026-05` → blocked, high
severity.

---

## Conventions and gotchas

- **Prompt language.** `ticket_receptionist` and its classifier are written in
  English; `ticket_resolution` (nodes, sub-agents, customer-facing copy) is written
  in Portuguese. Customer replies follow the language of the flow that produced them.
- **`Literal` over `str` in output schemas.** It becomes an enum in the function
  declaration, so the model can't return a fourth value that a downstream node would
  misinterpret.
- **`AgentTool` vs `sub_agents`.** The attendant uses `AgentTool(account_operator)`
  so control comes back after the account action; the receptionist uses `sub_agents`
  for the classifier, a real transfer.
- **Idempotency everywhere it matters.** `temp:ticket_created` blocks double
  registration, `get_ticket_escalation` blocks duplicate Linear issues, and
  `await_refund_input_node` re-writes the same status on resume.
- **Never trust the model with arithmetic.** The investigator returns line ids; the
  gate sums them.
- **`.adk/` session stores** are created per app name at the directory you launched
  from — expect folders like `agents.ticket_resolution/` at the repo root. They're
  gitignored and safe to delete.
- **`db/reset.py` drops everything.** It's `DROP ALL` + `CREATE ALL`, not a
  migration.

---

## Managing dependencies

```bash
uv add <package>       # adds a dependency (updates pyproject.toml and uv.lock)
uv remove <package>    # removes a dependency
uv sync                # syncs .venv with the lock file
```

Runtime dependencies: `google-adk[extensions,mcp]==2.5.0` and `sqlalchemy>=2.0.51`.
