from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models import RoleEnum, StatusEnum, PriorityEnum

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    # role is intentionally NOT accepted from public signup for agent/team_lead/admin.
    # Only customers self-register; other roles are created by Admin (see routers/auth.py).


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: RoleEnum

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: RoleEnum
    name: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class TicketCreate(BaseModel):
    subject: str
    description: str


class TicketUpdate(BaseModel):
    status: StatusEnum | None = None
    priority: PriorityEnum | None = None
    agent_id: int | None = None
    agent_reply: str | None = None


class TicketOut(BaseModel):
    id: int
    subject: str
    description: str
    status: StatusEnum
    priority: PriorityEnum
    customer_id: int
    customer_name: str | None = None
    agent_id: int | None
    agent_name: str | None = None
    agent_reply: str | None = None
    customer_reply: str | None = None
    team_id: int | None
    created_at: datetime
    sla_deadline: datetime | None
    resolved_at: datetime | None

    class Config:
        from_attributes = True

class CustomerReplyRequest(BaseModel):
        customer_reply: str

class TransferRequestCreate(BaseModel):
    new_team_id: int


class TransferRequestOut(BaseModel):
    id: int
    ticket_id: int
    from_team_id: int
    to_team_id: int
    requested_by: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class AuditLogOut(BaseModel):
    id: int
    ticket_id: int
    ticket_subject: str
    from_team_id: int
    to_team_id: int
    requested_by_name: str
    status: str
    created_at: datetime
    resolved_at: datetime | None

    class Config:
        from_attributes = True

class SLARuleOut(BaseModel):
    id: int
    priority: str
    response_minutes: int
    resolution_minutes: int

    class Config:
        from_attributes = True


class SLARuleUpdate(BaseModel):
    response_minutes: int
    resolution_minutes: int

class MassEmailRequest(BaseModel):
    customer_ids: list[int]
    subject: str
    message: str

class TicketMessageCreate(BaseModel):
    message: str


class TicketMessageOut(BaseModel):
    id: int
    sender_role: str
    sender_name: str | None
    message: str
    created_at: datetime

    class Config:
        from_attributes = True