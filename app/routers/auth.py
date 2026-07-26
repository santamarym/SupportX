import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, RoleEnum
from app.schemas import UserCreate, Token, UserOut, ForgotPasswordRequest, ResetPasswordRequest, MassEmailRequest
from app.auth import hash_password, verify_password, create_access_token, require_role
from app.email_utils import send_reset_email, send_incident_email

RESET_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut)
def signup(user_in: UserCreate, db: Session = Depends(get_db)):
    """Public self-registration. Always creates a CUSTOMER — role is never
    taken from the request body, so nobody can sign themselves up as admin."""
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        role=RoleEnum.customer,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Plain email + password login. No role selector on the frontend —
    the role is looked up from the DB and embedded in the token here."""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return Token(access_token=access_token, role=user.role, name=user.name)


@router.post("/admin/create-user", response_model=UserOut)
def admin_create_user(
    name: str,
    email: str,
    password: str,
    role: RoleEnum,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    """Only an Admin can create Agent / Team Lead / Admin accounts.
    This is the 'internal roles created via admin panel' flow discussed earlier."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        team_id=team_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.get("/admin/users", response_model=list[UserOut])
def list_all_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    return db.query(User).order_by(User.role, User.name).all()

@router.post("/admin/mass-email")
def send_mass_email(
    payload: MassEmailRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    """Admin selects specific customers to notify — e.g. about a known
    issue and estimated resolution time. Only sends to the IDs given,
    not all customers automatically."""
    customers = db.query(User).filter(
        User.id.in_(payload.customer_ids), User.role == RoleEnum.customer
    ).all()

    results = []
    for c in customers:
        sent = send_incident_email(c.email, payload.subject, payload.message)
        results.append({"email": c.email, "sent": sent})

    return {"results": results}

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Generates a reset token and emails it via SendGrid."""
    user = db.query(User).filter(User.email == payload.email).first()

    generic_response = {"message": "If that email is registered, a reset link has been sent to it."}

    if not user:
        return generic_response

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    db.commit()

    send_reset_email(user.email, token)

    return generic_response


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == payload.token).first()

    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired")

    user.hashed_password = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    return {"message": "Password has been reset. You can now log in with your new password."}


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(require_role(
    "customer", "agent", "team_lead", "admin"
))):
    """Lets the frontend confirm who's logged in and route to the right dashboard."""
    return current_user
