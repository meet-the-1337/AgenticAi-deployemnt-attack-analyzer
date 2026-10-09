"""
reconmind.platform_.tools
=========================
Mock tools for the Action agent.
"""

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CUSTOMERS_FILE = _REPO_ROOT / "mock_data" / "customers.json"
TICKETS_FILE = _REPO_ROOT / "mock_data" / "tickets.json"

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def query_db(customer_id: str) -> dict:
    """Mock DB query fetching customer and ticket info."""
    customers = _load_json(CUSTOMERS_FILE)
    tickets = _load_json(TICKETS_FILE)
    
    cust = customers.get(customer_id)
    if not cust:
        return {"error": f"Customer {customer_id} not found."}
    
    cust_tickets = {k: v for k, v in tickets.items() if v.get("customer_id") == customer_id}
    return {"customer": cust, "tickets": cust_tickets}

def update_ticket(ticket_id: str, status: str) -> bool:
    """Mock ticket status update."""
    tickets = _load_json(TICKETS_FILE)
    if ticket_id not in tickets:
        return False
    tickets[ticket_id]["status"] = status
    _save_json(TICKETS_FILE, tickets)
    return True

def send_email(to: str, subject: str, body: str) -> bool:
    """Mock sending email."""
    logger.info("Would have sent email to %s: [%s] %s", to, subject, body)
    return True

def escalate_to_admin(reason: str) -> bool:
    """Critical-asset tool. Flagged in logging."""
    logger.warning("ESCALATED TO ADMIN: %s", reason)
    return True

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "query_db": {
        "fn": query_db,
        "schema": {
            "type": "function",
            "function": {
                "name": "query_db",
                "description": "Fetch customer and ticket info by customer_id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string", "description": "The ID of the customer, e.g. CUST-001"}
                    },
                    "required": ["customer_id"]
                }
            }
        }
    },
    "update_ticket": {
        "fn": update_ticket,
        "schema": {
            "type": "function",
            "function": {
                "name": "update_ticket",
                "description": "Update the status of a ticket.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "string", "description": "The ID of the ticket, e.g. TKT-100"},
                        "status": {"type": "string", "description": "The new status, e.g. open, closed, in_progress"}
                    },
                    "required": ["ticket_id", "status"]
                }
            }
        }
    },
    "send_email": {
        "fn": send_email,
        "schema": {
            "type": "function",
            "function": {
                "name": "send_email",
                "description": "Send an email to a customer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "The email address"},
                        "subject": {"type": "string", "description": "The subject of the email"},
                        "body": {"type": "string", "description": "The body of the email"}
                    },
                    "required": ["to", "subject", "body"]
                }
            }
        }
    },
    "escalate_to_admin": {
        "fn": escalate_to_admin,
        "schema": {
            "type": "function",
            "function": {
                "name": "escalate_to_admin",
                "description": "Escalate an issue to the admin. Use only when critically needed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "The reason for escalation"}
                    },
                    "required": ["reason"]
                }
            }
        }
    }
}
