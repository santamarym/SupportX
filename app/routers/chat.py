import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import require_role
from app.chatbot import get_chatbot_response

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatHistoryTurn(BaseModel):
    role: str
    text: str


class ChatMessage(BaseModel):
    message: str
    history: list[ChatHistoryTurn] = []


class ChatResponse(BaseModel):
    reply: str
    resolved: bool
    ticket_id: int | None = None


@router.post("/message", response_model=ChatResponse)
def send_chat_message(
    payload: ChatMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
):
    """The chatbot now gets real database access (via db) and the
    customer's own ID (never trusting a customer_id from the request body
    itself — it comes from the authenticated JWT), plus recent conversation
    history for context-aware follow-ups.

    Response time is measured here as a standalone performance metric,
    independent of ticket SLA — it applies to every chat turn, whether or
    not a ticket ends up being created, since it measures the AI's own
    speed, not human agent responsiveness (which is what SLA response
    time tracks separately, only for tickets that actually exist)."""
    history = [turn.dict() for turn in payload.history]

    start_time = time.time()
    result = get_chatbot_response(
        customer_message=payload.message,
        customer_id=current_user.id,
        db=db,
        history=history,
    )
    elapsed_seconds = round(time.time() - start_time, 2)
    print(f"Chatbot response time: {elapsed_seconds}s | resolved={result['resolved']} | ticket_id={result.get('ticket_id')}")

    return ChatResponse(
        reply=result["reply"],
        resolved=result["resolved"],
        ticket_id=result.get("ticket_id"),
    )