# portal/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# LinkedIn OAuth Settings
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "77xrvbe9mat1kd")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "WPL_AP1.5GJpxuw6LeyIxQzP")
LINKEDIN_REDIRECT_URI = os.getenv(
    "LINKEDIN_REDIRECT_URI", 
    "http://localhost:8001/auth/linkedin/callback"  # Port 8001
)

# JWT Settings
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# Database Settings
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./portal.db")
