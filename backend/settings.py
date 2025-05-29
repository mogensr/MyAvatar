import os

class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret")
    CLOUDINARY_URL: str = os.getenv("CLOUDINARY_URL", "")
    HEYGEN_API_KEY: str = os.getenv("HEYGEN_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./myavatar.db")

settings = Settings()
