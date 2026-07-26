from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Ticket, RoleEnum, StatusEnum, TicketTransferRequest as TransferModel, TransferStatusEnum, SLARule
from app.schemas import TicketCreate, TicketUpdate, TicketOut, CustomerReplyRequest, TransferRequestCreate, TransferRequestOut, AuditLogOut, SLARuleOut, SLARuleUpdate
from app.auth import get_current_user, require_role
from app.sla_utils import assign_sla_deadline, is_breached
from app.chatbot import classify_ticket_priority, suggest_agent_response
from app.team_utils import assign_team, assign_agent

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketOut)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
):
    priority = classify_ticket_priority(payload.subject, payload.description)
    team_id = assign_team(db)
    ticket = Ticket(
        subject=payload.subject,
        description=payload.description,
        customer_id=current_user.id,
        priority=priority,
        team_id=team_id,
        agent_id=assign_agent(db, team_id),
    )
    db.add(ticket)
    db.flush()
    assign_sla_deadline(ticket, db)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("", response_model=list[TicketOut])
def list_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Ticket)

    if current_user.role == RoleEnum.customer:
        query = query.filter(Ticket.customer_id == current_user.id)
    elif current_user.role == RoleEnum.agent:
        query = query.filter(Ticket.agent_id == current_user.id)
    elif current_user.role == RoleEnum.team_lead:
        query = query.filter(Ticket.team_id == current_user.team_id)

    return query.order_by(Ticket.created_at.desc()).all()


@router.get("/escalations", response_model=list[TicketOut])
def list_escalations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("team_lead", "admin")),
):
    """Returns unresolved tickets that have breached their SLA deadline.
    Team Lead sees only their team's breaches; Admin sees all."""
    query = db.query(Ticket).filter(
        Ticket.status != StatusEnum.resolved,
        Ticket.sla_deadline.isnot(None),
        Ticket.sla_deadline < datetime.utcnow(),
    )
    if current_user.role == RoleEnum.team_lead:
        query = query.filter(Ticket.team_id == current_user.team_id)

    return query.order_by(Ticket.sla_deadline.asc()).all()

@router.get("/audit-logs/transfers", response_model=list[AuditLogOut])
def list_transfer_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Admin-only view of every ticket transfer ever requested, across both
    teams — pending, accepted, or declined — reusing the existing
    ticket_transfer_requests table as the audit trail."""
    requests = db.query(TransferModel).order_by(TransferModel.created_at.desc()).all()
    results = []
    for r in requests:
        ticket = db.query(Ticket).filter(Ticket.id == r.ticket_id).first()
        requester = db.query(User).filter(User.id == r.requested_by).first()
        results.append(AuditLogOut(
            id=r.id,
            ticket_id=r.ticket_id,
            ticket_subject=ticket.subject if ticket else "(deleted ticket)",
            from_team_id=r.from_team_id,
            to_team_id=r.to_team_id,
            requested_by_name=requester.name if requester else "Unknown",
            status=r.status.value,
            created_at=r.created_at,
            resolved_at=r.resolved_at,
        ))
    return results

@router.get("/admin/all-tickets")
def list_all_tickets_with_transfers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Every ticket across both teams, with a summary of its transfer
    history attached — lets Admin see the full picture in one table."""
    tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).all()
    transfer_map = {}
    for r in db.query(TransferModel).order_by(TransferModel.created_at.desc()).all():
        if r.ticket_id not in transfer_map:
            transfer_map[r.ticket_id] = f"T{r.from_team_id} → T{r.to_team_id} ({r.status.value})"

    results = []
    for t in tickets:
        data = TicketOut.from_orm(t).dict()
        data["transfer_summary"] = transfer_map.get(t.id, "Not transferred")
        results.append(data)
    return results

@router.get("/dashboard/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("team_lead", "admin")),
):
    query = db.query(Ticket)
    if current_user.role == RoleEnum.team_lead:
        query = query.filter(Ticket.team_id == current_user.team_id)
    all_tickets = query.all()

    total = len(all_tickets)
    open_count = sum(1 for t in all_tickets if t.status == StatusEnum.open)
    resolved_count = sum(1 for t in all_tickets if t.status == StatusEnum.resolved)
    escalated_count = sum(1 for t in all_tickets if t.status == StatusEnum.escalated)
    in_progress_count = sum(1 for t in all_tickets if t.status == StatusEnum.in_progress)

    now = datetime.utcnow()
    breached_count = sum(
        1 for t in all_tickets
        if t.sla_deadline and t.status != StatusEnum.resolved and t.sla_deadline < now
    )

    resolution_rate = round((resolved_count / total) * 100, 1) if total > 0 else 0

    priority_counts = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
    for t in all_tickets:
        priority_counts[t.priority.value] += 1

    status_counts = {
        "open": open_count,
        "in_progress": in_progress_count,
        "escalated": escalated_count,
        "resolved": resolved_count,
    }

    resolution_by_day = {}
    for t in all_tickets:
        if t.status == StatusEnum.resolved and t.resolved_at:
            day = t.resolved_at.strftime("%Y-%m-%d")
            hours = (t.resolved_at - t.created_at).total_seconds() / 3600
            resolution_by_day.setdefault(day, []).append(hours)

    avg_resolution_by_day = {
        day: round(sum(hrs) / len(hrs), 1) for day, hrs in sorted(resolution_by_day.items())
    }

    response_by_day = {}
    for t in all_tickets:
        if t.first_response_at:
            day = t.created_at.strftime("%Y-%m-%d")
            minutes = (t.first_response_at - t.created_at).total_seconds() / 60
            response_by_day.setdefault(day, []).append(minutes)

    avg_response_by_day = {
        day: round(sum(mins) / len(mins), 1) for day, mins in sorted(response_by_day.items())
    }

    return {
        "total_tickets": total,
        "open_tickets": open_count,
        "resolved_tickets": resolved_count,
        "sla_breaches": breached_count,
        "resolution_rate_percent": resolution_rate,
        "priority_counts": priority_counts,
        "status_counts": status_counts,
        "avg_resolution_hours_by_day": avg_resolution_by_day,
        "avg_response_minutes_by_day": avg_response_by_day,
    }

@router.get("/admin/sla-rules", response_model=list[SLARuleOut])
def list_sla_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    return db.query(SLARule).order_by(SLARule.priority).all()


@router.patch("/admin/sla-rules/{rule_id}", response_model=SLARuleOut)
def update_sla_rule(
    rule_id: int,
    payload: SLARuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    rule = db.query(SLARule).filter(SLARule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="SLA rule not found")
    rule.response_minutes = payload.response_minutes
    rule.resolution_minutes = payload.resolution_minutes
    db.commit()
    db.refresh(rule)
    return rule

@router.get("/notifications")
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns a simple list of 'things that changed recently' relevant to
    this user's role — checked via polling on page load, not real-time
    push."""
    notifications = []

    if current_user.role == RoleEnum.customer:
        tickets = db.query(Ticket).filter(
            Ticket.customer_id == current_user.id,
            Ticket.agent_reply.isnot(None),
            Ticket.status != StatusEnum.resolved,
            Ticket.reply_seen_by_customer == False,
        ).all()
        for t in tickets:
            notifications.append({"text": f"New reply on ticket #{t.id}: {t.subject}", "link_ticket_id": t.id})

        resolved_tickets = db.query(Ticket).filter(
            Ticket.customer_id == current_user.id,
            Ticket.status == StatusEnum.resolved,
            Ticket.resolved_seen_by_customer == False,
        ).all()
        for t in resolved_tickets:
            notifications.append({"text": f"Ticket #{t.id} resolved: {t.subject}", "link_ticket_id": t.id})

    elif current_user.role == RoleEnum.team_lead:
        requests = db.query(TransferModel).filter(
            TransferModel.status == TransferStatusEnum.pending,
            TransferModel.to_team_id == current_user.team_id,
        ).all()
        for r in requests:
            notifications.append({"text": f"New transfer request for ticket #{r.ticket_id}", "link_ticket_id": r.ticket_id})

    return {"count": len(notifications), "notifications": notifications}

@router.post("/notifications/mark-seen")
def mark_notifications_seen(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
):
    db.query(Ticket).filter(Ticket.customer_id == current_user.id).update({
        "reply_seen_by_customer": True,
        "resolved_seen_by_customer": True,
    })
    db.commit()
    return {"message": "Marked as seen"}


@router.get("/{ticket_id}/suggest-response")
def get_suggested_response(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("agent", "team_lead", "admin")),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    suggestion = suggest_agent_response(ticket.subject, ticket.description)
    return {"suggestion": suggestion}

@router.post("/{ticket_id}/customer-reply", response_model=TicketOut)
def submit_customer_reply(
    ticket_id: int,
    payload: CustomerReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("customer")),
):
    ticket = db.query(Ticket).filter(
        Ticket.id == ticket_id, Ticket.customer_id == current_user.id
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.customer_reply = payload.customer_reply
    db.commit()
    db.refresh(ticket)
    return ticket

@router.post("/{ticket_id}/request-transfer", response_model=TransferRequestOut)
def request_transfer(
    ticket_id: int,
    payload: TransferRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("team_lead", "admin")),
):
    """Team Lead requests moving a ticket to another team. This does NOT
    move the ticket yet — it creates a pending request that the receiving
    Team Lead must accept before anything actually changes."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if current_user.role == RoleEnum.team_lead and ticket.team_id != current_user.team_id:
        raise HTTPException(status_code=403, detail="You can only request transfers for your own team's tickets")

    existing = db.query(TransferModel).filter(
        TransferModel.ticket_id == ticket_id, TransferModel.status == TransferStatusEnum.pending
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A transfer request for this ticket is already pending")

    request = TransferModel(
        ticket_id=ticket_id,
        from_team_id=ticket.team_id,
        to_team_id=payload.new_team_id,
        requested_by=current_user.id,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.get("/transfer-requests/incoming", response_model=list[TransferRequestOut])
def list_incoming_transfer_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("team_lead", "admin")),
):
    """Requests waiting for THIS Team Lead's approval — i.e. transfers
    proposed INTO their team."""
    query = db.query(TransferModel).filter(TransferModel.status == TransferStatusEnum.pending)
    if current_user.role == RoleEnum.team_lead:
        query = query.filter(TransferModel.to_team_id == current_user.team_id)
    return query.order_by(TransferModel.created_at.desc()).all()

@router.get("/transfer-requests/outgoing", response_model=list[TransferRequestOut])
def list_outgoing_transfer_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("team_lead", "admin")),
):
    """ALL requests THIS Team Lead has sent — pending, accepted, or
    declined — so they always have visibility into what happened,
    regardless of outcome."""
    query = db.query(TransferModel)
    if current_user.role == RoleEnum.team_lead:
        query = query.filter(TransferModel.requested_by == current_user.id)
    return query.order_by(TransferModel.created_at.desc()).all()

@router.patch("/transfer-requests/{request_id}/respond")
def respond_to_transfer_request(
    request_id: int,
    accept: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("team_lead", "admin")),
):
    """The RECEIVING Team Lead accepts or declines. Only on accept does the
    ticket's team_id and agent actually change."""
    request = db.query(TransferModel).filter(TransferModel.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Transfer request not found")
    if current_user.role == RoleEnum.team_lead and request.to_team_id != current_user.team_id:
        raise HTTPException(status_code=403, detail="You can only respond to requests for your own team")
    if request.status != TransferStatusEnum.pending:
        raise HTTPException(status_code=400, detail="This request has already been resolved")

    request.status = TransferStatusEnum.accepted if accept else TransferStatusEnum.declined
    request.resolved_at = datetime.utcnow()

    if accept:
        ticket = db.query(Ticket).filter(Ticket.id == request.ticket_id).first()
        ticket.team_id = request.to_team_id
        ticket.agent_id = assign_agent(db, request.to_team_id)

    db.commit()
    return {"message": f"Transfer request {'accepted' if accept else 'declined'}."}

@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    _check_ticket_access(ticket, current_user)
    return ticket


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("agent", "team_lead", "admin")),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if current_user.role == RoleEnum.agent and ticket.agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update tickets assigned to you")

    if payload.status is not None:
        ticket.status = payload.status
        if payload.status == StatusEnum.resolved:
            ticket.resolved_at = datetime.utcnow()
            ticket.resolved_seen_by_customer = False
    if payload.priority is not None:
        ticket.priority = payload.priority
    if payload.agent_id is not None:
        if current_user.role == RoleEnum.agent:
            raise HTTPException(status_code=403, detail="Agents cannot reassign tickets")
        ticket.agent_id = payload.agent_id
    print(f"DEBUG: payload.agent_reply = {payload.agent_reply!r}")
    if payload.agent_reply is not None:
        ticket.agent_reply = payload.agent_reply
        ticket.status = StatusEnum.in_progress
        ticket.reply_seen_by_customer = False
        if ticket.first_response_at is None:
            ticket.first_response_at = datetime.utcnow()
        print(f"DEBUG: status set to {ticket.status}")

    db.commit()
    db.refresh(ticket)
    return ticket


def _check_ticket_access(ticket: Ticket, current_user: User):
    if current_user.role == RoleEnum.admin:
        return
    if current_user.role == RoleEnum.customer and ticket.customer_id == current_user.id:
        return
    if current_user.role == RoleEnum.agent and ticket.agent_id == current_user.id:
        return
    if current_user.role == RoleEnum.team_lead and ticket.team_id == current_user.team_id:
        return
    raise HTTPException(status_code=403, detail="You don't have access to this ticket")