from google.adk import Agent
from google.adk.tools.function_tool import FunctionTool

INVOICES = [
    {
        "id": "invoice_001",
        "customer_id": "customer_123",
        "amount": 49.99,
        "issue_date": "2024-01-01",
        "due_date": "2024-01-15",
        "status": "paid",
    },
    {
        "id": "invoice_002",
        "customer_id": "customer_123",
        "amount": 49.99,
        "issue_date": "2024-02-01",
        "due_date": "2024-02-15",
        "status": "pending",
    },
]


def list_invoices(customer_id: str) -> dict:
    """
        Lists the invoices for a specific customer.
        Args:
            customer_id (str): The ID of the customer whose invoices should be listed.
        Returns:
            dict: A dictionary containing the customer's list of invoices.
    """

    return {
        "invoices": [invoice for invoice in INVOICES if invoice["customer_id"] == customer_id],
    }


SUBSCRIPTIONS: dict[str, dict] = {
    "customer_123": {"plan": "Pro", "status": "active", "renewal": "2026-07-01"},
}


def get_subscription(customer_id: str) -> dict:
    """
        Retrieves the subscription data for a specific customer.
        Args:
            customer_id (str): The ID of the customer whose subscription should be retrieved.
        Returns:
            dict: A dictionary containing the subscription's plan, status and renewal date,
                or an error if the customer is not found.
    """

    subscription = SUBSCRIPTIONS.get(customer_id)
    if subscription is None:
        return {"status": "error", "reason": "customer_not_found", "customer_id": customer_id}

    return {"customer_id": customer_id, **subscription}


def cancel_subscription(customer_id: str) -> dict:
    """
        Cancels the subscription for a specific customer.
        Args:
            customer_id (str): The ID of the customer whose subscription should be cancelled.
        Returns:
            dict: A dictionary containing the status of the cancellation operation.
    """

    subscription = SUBSCRIPTIONS.get(customer_id)
    if subscription is None:
        return {"status": "error", "reason": "customer_not_found", "customer_id": customer_id}

    subscription["status"] = "cancelled"
    return {"status": "cancelled", "customer_id": customer_id}


root_agent = Agent(
    name="account_operator",
    instruction="""
        You are Acme's interactive account support agent.
        You are responsible for:
         - Informing the customer about their subscription: plan, status and renewal date.
         - Answering questions about the customer's invoices.
         - Cancelling the customer's subscription, if requested.
         - If no data is found for the customer, inform them that the information could not be located.
        The user needs to provide the customer ID so you can look up the correct information.
        Before cancelling a subscription, always use get_subscription to confirm it exists.
        Only call cancel_subscription if get_subscription confirms an existing subscription;
        otherwise, tell the customer the subscription could not be found and do not ask for cancellation confirmation.
        Be courteous and direct.
    """,
    model="gemini-3.1-flash-lite",
    tools=[
        list_invoices,
        get_subscription,
        FunctionTool(cancel_subscription, require_confirmation=True)
    ]
)
