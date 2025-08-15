# debug_create_admin.py
"""
Dette script genskaber (eller opretter) en admin-bruger og en testbruger direkte i din database.
- Admin:    username='admin',    password='admin123'
- Testbruger: username='Mogens R', password='Test123'
Kør scriptet fra projektmappen:  python debug_create_admin.py
"""

import os
import sys
from passlib.context import CryptContext
import sqlite3

DB_PATH = 'myavatar.db'

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_USERNAME = 'admin'
ADMIN_EMAIL = 'admin@myavatar.com'
ADMIN_PASSWORD = 'admin123'

TEST_USERNAME = 'Mogens R'
TEST_EMAIL = 'mogensr@myavatar.com'
TEST_PASSWORD = 'Test123'

def ensure_user(conn, username, email, password, is_admin=False):
    cursor = conn.cursor()
    hashed = pwd_context.hash(password)
    cursor.execute("SELECT id FROM users WHERE username=? OR email=?", (username, email))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE users SET hashed_password=?, is_admin=? WHERE id=?", (hashed, int(is_admin), row[0]))
        print(f"[OK] Opdaterede bruger: {username}")
    else:
        cursor.execute("INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)", (username, email, hashed, int(is_admin)))
        print(f"[OK] Oprettede bruger: {username}")
    conn.commit()

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database '{DB_PATH}' findes ikke!")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_user(conn, ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD, is_admin=True)
        ensure_user(conn, TEST_USERNAME, TEST_EMAIL, TEST_PASSWORD, is_admin=False)
        print("✅ Admin og testbruger er klar!")
    except Exception as e:
        print(f"FEJL: {e}")
    finally:
        conn.close()
