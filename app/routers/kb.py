from fastapi import APIRouter, Depends
from app.auth import require_role
from app.kb_data import KB_ARTICLES

router = APIRouter(prefix="/kb", tags=["kb"])


@router.get("")
def list_kb_articles(current_user=Depends(require_role("agent", "team_lead", "admin"))):
    return KB_ARTICLES