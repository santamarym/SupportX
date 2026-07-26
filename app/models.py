import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class RoleEnum(str, enum.Enum):
    customer = "customer"
    agent = "agent"
    team_lead = "team_lead"
    admin = "admin"


class PriorityEnum(str, enum.Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class StatusEnum(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    escalated = "escalated"
    resolved = "resolved"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.customer)
    team_id = Column(Integer, nullable=True)  # used for team_lead/agent grouping
    created_at = Column(DateTime, default=datetime.utcnow)

    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)

    tickets_created = relationship(
        "Ticket", back_populates="customer", foreign_keys="Ticket.customer_id"
    )
    tickets_assigned = relationship(
        "Ticket", back_populates="agent", foreign_keys="Ticket.agent_id"
    )


class SLARule(Base):
    __tablename__ = "sla_rules"

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(Enum(PriorityEnum), unique=True, nullable=False)
    response_minutes = Column(Integer, nullable=False)
    resolution_minutes = Column(Integer, nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(StatusEnum), default=StatusEnum.open)
    priority = Column(Enum(PriorityEnum), default=PriorityEnum.P3)

    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    team_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    sla_deadline = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    agent_reply = Column(Text, nullable=True)
    reply_seen_by_customer = Column(Boolean, default=False)
    resolved_seen_by_customer = Column(Boolean, default=False)  
    first_response_at = Column(DateTime, nullable=True)
    customer_reply = Column(Text, nullable=True)
    
    customer = relationship("User", foreign_keys=[customer_id], back_populates="tickets_created")
    agent = relationship("User", foreign_keys=[agent_id], back_populates="tickets_assigned")
    
    @property
    def customer_name(self):
        return self.customer.name if self.customer else None
    
    @property
    def agent_name(self):
        return self.agent.name if self.agent else None

class TransferStatusEnum(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"


class TicketTransferRequest(Base):
    __tablename__ = "ticket_transfer_requests"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    from_team_id = Column(Integer, nullable=False)
    to_team_id = Column(Integer, nullable=False)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(TransferStatusEnum), default=TransferStatusEnum.pending)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    ticket = relationship("Ticket")
