"""AI chatbot logic. Key upgrades over the previous version:
1. Real semantic search over the Knowledge Base using embeddings — only the
   most relevant 3-4 articles are sent per query, not all 18 every time.
   This is genuine "AI semantic search" (matches the FRD requirement),
   not just static context-stuffing, and it's also faster.
2. Handles MULTIPLE tool calls in a single AI turn (e.g. "create a ticket
   AND tell me my other tickets" now actually does both).
3. Explicit rules for emotional tone, ambiguity, and not inventing tickets
   for simple lookup requests.
4. Honest error messaging that distinguishes rate-limiting from other
   failures, instead of one vague fallback for everything.
"""
import math
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import GEMINI_API_KEY
from app.kb_data import KB_ARTICLES
from app.models import Ticket
from app.sla_utils import assign_sla_deadline
from app.team_utils import assign_team, assign_agent

embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=GEMINI_API_KEY,
)

_kb_texts = [f"{a['title']}: {a['content']}" for a in KB_ARTICLES]
try:
    _kb_embeddings = embeddings_model.embed_documents(_kb_texts)
except Exception as e:
    print(f"Warning: could not precompute KB embeddings at startup: {e}")
    _kb_embeddings = []


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def get_relevant_kb_articles(query: str, top_k: int = 4) -> str:
    if not _kb_embeddings:
        return "\n\n".join(f"[{a['category']}] {a['title']}\n{a['content']}" for a in KB_ARTICLES)

    try:
        query_embedding = embeddings_model.embed_query(query)
        scored = [
            (_cosine_similarity(query_embedding, kb_emb), i)
            for i, kb_emb in enumerate(_kb_embeddings)
        ]
        scored.sort(reverse=True)
        top_articles = [KB_ARTICLES[i] for _, i in scored[:top_k]]
        return "\n\n".join(f"[{a['category']}] {a['title']}\n{a['content']}" for a in top_articles)
    except Exception as e:
        print(f"Semantic search error, falling back to full KB: {e}")
        return "\n\n".join(f"[{a['category']}] {a['title']}\n{a['content']}" for a in KB_ARTICLES)


SYSTEM_PROMPT = """You are the SupportX customer support assistant for TechServe Solutions,
a B2B SaaS company providing project and workflow management software.

The most relevant Knowledge Base articles for this customer's message are:

{kb}

You have three tools available:
- check_ticket_status: use when the customer asks about ONE specific existing
  ticket (e.g. "status of ticket #4").
- list_my_tickets: use when the customer asks to see/list ALL their tickets
  (e.g. "what tickets do I have"). NEVER create a new ticket just to answer
  this kind of request — always use this tool instead.
- create_support_ticket: use ONLY when the customer describes a genuinely
  NEW issue not covered by the KB above. Do not use this tool for requests
  to view, list, or check existing data.

Rules:
1. If a KB article directly answers a NEW issue, answer it yourself in plain
   text — no tool needed.
2. If the customer's message contains multiple distinct requests (e.g.
   "create a ticket for X and also show me my tickets"), address ALL of
   them — call multiple tools if needed, don't silently do only one.
3. If a message is too vague to act on ("it's broken", "idk what's wrong"),
   ask ONE short clarifying question rather than guessing or creating a
   ticket immediately.
4. If the customer refers vaguely to "that ticket" or "the issue" and more
   than one ticket could reasonably match, briefly ask which one they mean
   rather than picking one silently.
4b. IMPORTANT: Only ask for a ticket number if the customer's message or
    recent history clearly references an EXISTING ticket. If the customer
    is describing a problem for the first time (even if it happened days
    ago, like "I cancelled 10 days ago and never got my refund"), treat it
    as a NEW issue — do not assume a ticket already exists. Either answer
    from the KB, or call create_support_ticket. Never ask "what's your
    ticket number" for a problem being described for the first time. If
    the customer references a PAST ticket vaguely, use list_my_tickets
    first to check what they have — only ask for a specific number if
    that doesn't clarify which ticket they mean.
5. If the customer expresses frustration, anger, or strong dissatisfaction,
   acknowledge it in ONE SHORT phrase only — like "I'm sorry that's
   happened" or "I understand that's frustrating" — maximum 6 words. Do
   NOT write a full sentence of empathy, and do NOT combine multiple
   empathy phrases together (e.g. don't say both "I'm sorry" AND "I
   understand how upsetting this is"). Pick ONE short phrase, then move
   directly to helping.
6. CRITICAL: Never say a ticket "has been created" or "I've logged this"
   in your reply text UNLESS you are actually calling the
   create_support_ticket tool in this same turn. Your reply text and your
   actual tool calls must always match — if you say a ticket was created,
   you MUST have called the tool. If you are unsure whether something
   needs a ticket, call create_support_ticket rather than just describing
   it in words. Requests like "delete my account", "cancel my
   subscription", or any account-changing action you have no tool for
   ALWAYS require calling create_support_ticket — never just describe
   creating one without actually doing it.
7. Keep answers focused — don't dump unrelated topics when asked a vague
   follow-up like "any other tips"; ask what they're interested in instead.
8. Never reveal internal ticket priority levels to the customer directly.
9. BE CONCISE overall, but especially keep the empathy/apology part to
   the shortest possible phrase (see rule 5). The helpful part of your
   response (offering to check tickets, giving alternatives, etc.) can
   still be a full sentence if needed — the goal is trimming the
   emotional opener, not removing useful options.
"""


class CheckTicketStatusInput(BaseModel):
    ticket_id: int = Field(description="The ticket ID number the customer is asking about")


class CreateTicketInput(BaseModel):
    subject: str = Field(description="Short 5-8 word summary of the issue")
    description: str = Field(description="Full description of the customer's issue")
    priority: str = Field(description="One of: P1, P2, P3, P4")


def _build_tools(customer_id: int, db: Session):
    def check_ticket_status(ticket_id: int) -> str:
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id, Ticket.customer_id == customer_id
        ).first()
        if not ticket:
            return f"No ticket #{ticket_id} found for this customer."
        return (
            f"Ticket #{ticket.id}: '{ticket.subject}'. "
            f"Status: {ticket.status.value}. "
            f"Created: {ticket.created_at.strftime('%Y-%m-%d %H:%M')}. "
            f"{'Resolved at: ' + ticket.resolved_at.strftime('%Y-%m-%d %H:%M') if ticket.resolved_at else 'Not yet resolved.'}"
        )

    def list_my_tickets() -> str:
        tickets = db.query(Ticket).filter(Ticket.customer_id == customer_id).order_by(Ticket.created_at.desc()).all()
        if not tickets:
            return "You don't have any tickets yet."
        lines = [f"#{t.id}: '{t.subject}' — {t.status.value}" for t in tickets]
        return "Your tickets:\n" + "\n".join(lines)

    def create_support_ticket(subject: str, description: str, priority: str) -> str:
        if priority not in ["P1", "P2", "P3", "P4"]:
            priority = "P3"
        sentiment = classify_sentiment(subject, description)
        team_id = assign_team(db)
        ticket = Ticket(
            subject=subject,
            description=description,
            customer_id=customer_id,
            priority=priority,
            sentiment=sentiment,
            team_id=team_id,
            agent_id=assign_agent(db, team_id),
        )
        db.add(ticket)
        db.flush()
        assign_sla_deadline(ticket, db)
        db.commit()
        db.refresh(ticket)
        return f"TICKET_CREATED:{ticket.id}:Created ticket #{ticket.id}. An agent will follow up shortly."

    status_tool = StructuredTool.from_function(
        func=check_ticket_status,
        name="check_ticket_status",
        description="Look up the live status of ONE specific existing ticket belonging to this customer.",
        args_schema=CheckTicketStatusInput,
    )
    list_tool = StructuredTool.from_function(
        func=list_my_tickets,
        name="list_my_tickets",
        description="List ALL tickets belonging to this customer.",
    )
    create_tool = StructuredTool.from_function(
        func=create_support_ticket,
        name="create_support_ticket",
        description="Create a new support ticket for a genuinely new issue not covered by the KB.",
        args_schema=CreateTicketInput,
    )
    return [status_tool, list_tool, create_tool]


llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    google_api_key=GEMINI_API_KEY,
    temperature=0.3,
    max_output_tokens=300,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{message}"),
])


def _history_to_messages(history: list[dict]) -> list:
    messages = []
    for turn in (history or [])[-6:]:
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=turn["text"]))
        elif turn.get("role") == "bot" and not turn.get("pending"):
            messages.append(AIMessage(content=turn["text"]))
    return messages


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _friendly_error_message(e: Exception) -> str:
    error_text = str(e)
    if "429" in error_text or "quota" in error_text.lower() or "rate" in error_text.lower():
        return ("I'm getting a lot of requests right now and have hit a temporary rate limit. "
                "Please wait about a minute and try again.")
    return "Something went wrong on my end processing that — please try again in a moment."


def get_chatbot_response(customer_message: str, customer_id: int, db: Session, history: list[dict] = None) -> dict:
    history = history or []
    tools = _build_tools(customer_id, db)
    llm_with_tools = llm.bind_tools(tools)
    chain = prompt | llm_with_tools

    try:
        relevant_kb = get_relevant_kb_articles(customer_message)
        response = chain.invoke({
            "kb": relevant_kb,
            "history": _history_to_messages(history),
            "message": customer_message,
        })

        if response.tool_calls:
            reply_parts = []
            ticket_id = None
            resolved = True

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                matching_tool = next((t for t in tools if t.name == tool_name), None)
                if not matching_tool:
                    continue
                result = matching_tool.func(**tool_args)

                if tool_name == "create_support_ticket":
                    _, tid_str, human_text = result.split(":", 2)
                    ticket_id = int(tid_str)
                    resolved = False
                    reply_parts.append(human_text.strip())
                else:
                    reply_parts.append(result)

            return {"resolved": resolved, "reply": "\n\n".join(reply_parts), "ticket_id": ticket_id}

        return {"resolved": True, "reply": _extract_text(response.content), "ticket_id": None}

    except Exception as e:
        print(f"Chatbot error: {e}")
        return {"resolved": False, "reply": _friendly_error_message(e), "ticket_id": None}


def classify_ticket_priority(subject: str, description: str) -> str:
    classify_prompt = ChatPromptTemplate.from_template(
        """Classify this support ticket's priority for TechServe Solutions.
P1=critical/account inaccessible/security, P2=high/major feature broken/billing dispute,
P3=medium/minor bug, P4=low/feature request.

Subject: {subject}
Description: {description}

Respond with ONLY one word: P1, P2, P3, or P4."""
    )
    try:
        result = (classify_prompt | llm).invoke({"subject": subject, "description": description})
        text = _extract_text(result.content).strip()
        return text if text in ["P1", "P2", "P3", "P4"] else "P3"
    except Exception as e:
        print(f"Classification error: {e}")
        return "P3"

def suggest_agent_response(ticket_subject: str, ticket_description: str, conversation: str = "") -> str:
    """Generates a DRAFT response an Agent can review, edit, and send to
    the customer — the agent stays in control, this just saves them from
    starting with a blank page. Uses the same semantic KB search as the
    customer chatbot, so suggestions are grounded in real KB content."""
    relevant_kb = get_relevant_kb_articles(f"{ticket_subject} {ticket_description}")

    suggest_prompt = ChatPromptTemplate.from_template(
        """Draft a short reply for a Support Agent to send inside an existing
support ticket thread. The customer already opened this ticket — this is
NOT a first-contact email.

STRICT RULES:
- NO "Subject:" line
- NO greeting like "Hello" or "Dear Customer"
- NO sign-off like "Best regards" or "[Agent Name]"
- NEVER say "reply to this email" or "respond to this email" — this is a
  message inside the app's ticket thread, not an email. If the customer
  needs to confirm something, say "reply to this message" instead.
- READ THE CONVERSATION SO FAR CAREFULLY. If the customer already said the
  issue is resolved, working, or fine, do NOT repeat earlier troubleshooting
  advice — instead acknowledge that and ask if they need anything else, or
  confirm you'll close the ticket.
- If the customer said something ISN'T working or gave new information,
  respond specifically to THAT, don't repeat the same generic advice again.
- Maximum 3 sentences, OR a maximum 3-item bullet list if steps are needed

Relevant Knowledge Base info:
{kb}

Ticket subject: {subject}
Ticket description: {description}

Conversation so far:
{conversation}

Output ONLY the short reply text, nothing else."""
    )
    try:
        result = (suggest_prompt | llm).invoke({
            "kb": relevant_kb,
            "subject": ticket_subject,
            "description": ticket_description,
            "conversation": conversation if conversation else "(no messages yet)",
        })
        return _extract_text(result.content).strip()
    except Exception as e:
        print(f"Suggestion error: {e}")
        return "Could not generate a suggestion right now — please write a response manually."

def summarize_conversation(ticket_subject: str, conversation: str) -> str:
    """Generates a short summary of a ticket's back-and-forth conversation,
    for Team Leads reviewing many tickets without reading full threads."""
    if not conversation or conversation.strip() == "":
        return "No conversation yet."

    summary_prompt = ChatPromptTemplate.from_template(
        """Summarize this support ticket conversation in 1-2 short, clear sentences.

Cover: what the customer needed, what actually happened (steps tried, or
actions taken/requested), and the current state.

RULES:
- Do NOT force every conversation into a "troubleshooting steps" format.
  If this is about approving/declining an action (like account deletion,
  a refund, a cancellation) rather than fixing a technical problem,
  describe it that way instead — e.g. "The agent requested confirmation
  to delete the account, but the customer declined."
- Only state WHO resolved something or WHAT fixed it if the conversation
  explicitly says so
- CAREFULLY check whether the LAST message is a final, conclusive answer
  (e.g. "no need to do that", "it works now", "please cancel that") — if
  so, the conversation has CONCLUDED. Do not say "waiting on customer" if
  the customer already gave their final answer
- Only say "waiting on customer" if the LAST message was from the agent,
  asking something not yet answered
- Do not use quotes or restate the ticket subject

Ticket subject: {subject}

Conversation:
{conversation}

Output ONLY the 1-2 sentence summary."""
    )
    try:
        result = (summary_prompt | llm).invoke({
            "subject": ticket_subject,
            "conversation": conversation,
        })
        return _extract_text(result.content).strip()
    except Exception as e:
        print(f"Summary error: {e}")
        return "Could not generate a summary right now."

def classify_sentiment(subject: str, description: str) -> str:
    """Detects customer tone/urgency signals separate from technical
    priority — a flag for humans to notice, never used to auto-change
    SLA deadlines or priority."""
    sentiment_prompt = ChatPromptTemplate.from_template(
        """Read this customer support ticket and classify the customer's
tone. Choose exactly ONE of these labels:

- frustrated: customer expresses clear annoyance, anger, or repeated complaints
- urgent: customer expresses time pressure or business impact, even if calm
- neutral: normal, calm tone, no strong emotion

Ticket subject: {subject}
Ticket description: {description}

Respond with ONLY one word: frustrated, urgent, or neutral."""
    )
    try:
        result = (sentiment_prompt | llm).invoke({"subject": subject, "description": description})
        text = _extract_text(result.content).strip().lower()
        return text if text in ["frustrated", "urgent", "neutral"] else "neutral"
    except Exception as e:
        print(f"Sentiment error: {e}")
        return "neutral"