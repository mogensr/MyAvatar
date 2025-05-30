# portal/register.py

# ============================
# BLOK 1: Imports og Setup
# ============================
from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from .models import User, Organization
from .database import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================
# BLOK 2: GET Route til Registrering
# ============================
@router.get("/auth/register")
def register_form(request: Request):
    return templates.TemplateResponse("portal/register.html", {"request": request})

# ============================
# BLOK 3: POST Route til Oprettelse
# ============================
@router.post("/auth/register")
def register_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return templates.TemplateResponse("portal/register.html", {"request": request, "error": "Email er allerede registreret."})

    # Find eller opret standard-organisation
    org = db.query(Organization).first()
    if not org:
        org = Organization(name="MyAvatar Demo", subdomain="demo")
        db.add(org)
        db.commit()
        db.refresh(org)

    # Opret ny bruger
    user = User(
        name=name,
        email=email,
        password_hash=pwd_context.hash(password),
        organization_id=org.id,
        is_admin=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
