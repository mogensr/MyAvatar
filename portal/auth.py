"""portal/auth.py – samlet, opdateret version

✓ E‑mail/password‑login returnerer nu 303‑redirect + cookie
✓ get_current_user henter token fra cookie **eller** Authorization‑header
✓ LinkedIn‑OAuth‑flow uændret (sætter allerede cookie + redirect)
✓ Alle redirects bruger nu absolutte URLs med port 8001
✓ Secure cookie flag sat til False for lokal udvikling

"""

# ============================
# BLOK 1: Imports og Setup
# ============================
from datetime import datetime, timedelta
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
import httpx
import jwt
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, Organization, Avatar, Video  # Video bruges i dashboard
from .config import (
    LINKEDIN_CLIENT_ID,
    LINKEDIN_CLIENT_SECRET,
    LINKEDIN_REDIRECT_URI,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Swagger / API-klienter må stadig bruge Authorization‑header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Frontend URL med korrekt port
FRONTEND_BASE_URL = "http://localhost:8001"

# ============================
# BLOK 2: Helper‑funktioner
# ============================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    request: Request,
    token_header: str = Depends(oauth2_scheme),  # tom streng hvis ikke sat
    db: Session = Depends(get_db),
):
    """Returnér User‑objektet, hvis en gyldig JWT findes i cookie eller header."""

    token = request.cookies.get("access_token") or token_header
    if not token:
        return None

    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub", 0))
    except jwt.PyJWTError:
        return None

    return db.query(User).filter(User.id == user_id).first()

# ============================
# BLOK 3: Login‑view (HTML‑form)
# ============================

@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("portal/login.html", {"request": request})

# ============================
# BLOK 4: LinkedIn‑OAuth Login
# ============================

@router.get("/client/{client_id}/login/linkedin")
async def login_linkedin(client_id: str):
    redirect_uri = LINKEDIN_REDIRECT_URI.replace(":id", client_id)
    linkedin_auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code&client_id={LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
    )
    return RedirectResponse(url=linkedin_auth_url, status_code=302)


@router.get("/client/{client_id}/auth/linkedin/callback")
async def linkedin_callback(
    client_id: str,
    request: Request,
    code: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    if error:
        return templates.TemplateResponse("portal/login.html", {"request": request, "error": f"LinkedIn error: {error}"})
    if not code:
        return templates.TemplateResponse("portal/login.html", {"request": request, "error": "No LinkedIn code received"})

    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    redirect_uri = LINKEDIN_REDIRECT_URI.replace(":id", client_id)

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_url, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": LINKEDIN_CLIENT_ID,
            "client_secret": LINKEDIN_CLIENT_SECRET,
        })
    token_data = token_resp.json()
    if token_data.get("error"):
        return templates.TemplateResponse("portal/login.html", {"request": request, "error": "Token error from LinkedIn"})

    headers = {"Authorization": f"Bearer {token_data['access_token']}"}

    async with httpx.AsyncClient() as client:
        profile_data = (await client.get("https://api.linkedin.com/v2/me", headers=headers)).json()
        email_data = (
            await client.get(
                "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
                headers=headers,
            )
        ).json()

    linkedin_id = profile_data.get("id")
    name = f"{profile_data.get('localizedFirstName','')} {profile_data.get('localizedLastName','')}".strip()
    email = email_data["elements"][0]["handle~"]["emailAddress"]

    # ▸ Find eller opret bruger
    user = db.query(User).filter(User.linkedin_id == linkedin_id).first()
    if not user:
        org = db.query(Organization).first()
        if not org:
            org = Organization(name="MyAvatar Demo", subdomain="demo")
            db.add(org)
            db.commit()
            db.refresh(org)
            db.add_all([
                Avatar(heygen_avatar_id="b5038ba7bd9b4d94ac6b5c9ea70f8d28", name="Standard", type="seated", organization_id=org.id),
                Avatar(heygen_avatar_id="ba93f97aacb84960a423b01278c8dd77", name="Alternativ", type="standing", organization_id=org.id),
            ])
            db.commit()
        user = User(linkedin_id=linkedin_id, name=name, email=email, organization_id=org.id)
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token({"sub": str(user.id), "org": user.organization_id})
    # Opdateret til at bruge frontend-URL med korrekt port
    resp = RedirectResponse(url=f"{FRONTEND_BASE_URL}/client/{client_id}/dashboard", status_code=302)
    resp.set_cookie(
        key="access_token", 
        value=f"Bearer {token}", 
        httponly=True, 
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, 
        samesite="lax", 
        secure=False  # Ændret til False for lokal HTTP-udvikling
    )
    return resp

# ============================
# BLOK 5: E‑mail + Password Login
# ============================

@router.get("/auth/register")
async def register_form(request: Request):
    return templates.TemplateResponse("portal/register.html", {"request": request})


@router.post("/auth/register")
async def register_user(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    org = db.query(Organization).first()
    if not org:
        org = Organization(name="MyAvatar Demo", subdomain="demo")
        db.add(org)
        db.commit()
        db.refresh(org)

    user = User(
        name=name,
        email=email,
        password_hash=pwd_context.hash(password),
        organization_id=org.id,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "User created", "user_id": user.id}


@router.post("/auth/login")
async def login_user(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash or not pwd_context.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "org": user.organization_id})

    # ► Opdateret til absolutte URLs med port 8001
    resp = RedirectResponse(f"{FRONTEND_BASE_URL}/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False,  # Ændret til False for lokal HTTP-udvikling
    )
    return resp

# ============================
# BLOK 6: Dashboard‑visning
# ============================

@router.get("/dashboard")
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    if not current_user:
        # Opdateret til absolutte URLs med port 8001
        return RedirectResponse(f"{FRONTEND_BASE_URL}/login", status_code=302)

    avatars = db.query(Avatar).filter(Avatar.organization_id == current_user.organization_id).all()
    videos = db.query(Video).filter(Video.user_id == current_user.id).order_by(Video.created_at.desc()).all()

    return templates.TemplateResponse(
        "portal/dashboard.html",
        {
            "request": request,
            "user": current_user,
            "organization": current_user.organization,
            "avatars": avatars,
            "videos": videos,
        },
    )

# ============================
# BLOK 7: Diverse/debug
# ============================

@router.get("/debug/test")
async def debug_test():
    return {"message": "debug virker"}