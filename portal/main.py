# portal/main.py

# ============================
# BLOK 1: Imports og Setup
# ============================
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from . import models, auth, register
from .database import engine

# ============================
# BLOK 2: Initialisering af App
# ============================
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="MyAvatar Portal")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ============================
# BLOK 3: Registrering af Routers
# ============================
app.include_router(auth.router, tags=["authentication"])
app.include_router(register.router, tags=["register"])

# ============================
# BLOK 4: Root Endpoint (valgfri)
# ============================
@app.get("/")
def root():
    return {"message": "Velkommen til MyAvatar Portal"}
