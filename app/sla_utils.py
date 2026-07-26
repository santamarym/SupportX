from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import Ticket, SLARule


def assign_sla_deadline(ticket: Ticket, db: Session) -> None:
    """Looks up the SLA rule matching this ticket's priority and sets its
    deadline based on resolution_minutes. Called right after a ticket is
    created — from both manual creation (Day 3) and the chatbot (Day 4-5),
    so every ticket gets a deadline regardless of how it was created."""
    rule = db.query(SLARule).filter(SLARule.priority == ticket.priority).first()
    if rule:
        ticket.sla_deadline = ticket.created_at + timedelta(minutes=rule.resolution_minutes)


def is_breached(ticket: Ticket) -> bool:
    """A ticket is breached if it's past its SLA deadline and still not resolved."""
    if ticket.status == "resolved" or not ticket.sla_deadline:
        return False
    return datetime.utcnow() > ticket.sla_deadline