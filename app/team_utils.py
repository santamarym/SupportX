from sqlalchemy.orm import Session
from app.models import Ticket, User, RoleEnum, StatusEnum


def assign_team(db: Session) -> int:
    """Simple round-robin team routing: alternates between team 1 and 2
    based on total ticket count, so tickets spread evenly across teams."""
    ticket_count = db.query(Ticket).count()
    return 1 if ticket_count % 2 == 0 else 2


def assign_agent(db: Session, team_id: int) -> int | None:
    """Load-based agent assignment: finds every agent on the given team,
    counts how many unresolved tickets each currently has, and assigns
    the new ticket to whichever agent has the fewest — so work stays
    balanced across the team instead of piling up on one person.
    Returns None if the team has no agents (ticket stays unassigned)."""
    agents = db.query(User).filter(
        User.role == RoleEnum.agent, User.team_id == team_id
    ).all()
    if not agents:
        return None

    least_loaded_agent = None
    lowest_count = None
    for agent in agents:
        open_count = db.query(Ticket).filter(
            Ticket.agent_id == agent.id,
            Ticket.status != StatusEnum.resolved,
        ).count()
        if lowest_count is None or open_count < lowest_count:
            lowest_count = open_count
            least_loaded_agent = agent

    return least_loaded_agent.id if least_loaded_agent else None