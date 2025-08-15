import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env (if present)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set. Please set it in your environment or .env file.")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS input_url TEXT;")
conn.commit()
cur.close()
conn.close()
print("input_url column added to videos table (if it did not exist).")
