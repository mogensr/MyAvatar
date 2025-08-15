"""
Initialize MyAvatar Database
Run this script to create all necessary tables and an admin user
"""
import sqlite3
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_database():
    # Connect to database
    conn = sqlite3.connect("myavatar.db")
    cur = conn.cursor()
    
    # Create users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create avatars table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS avatars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            avatar_name TEXT NOT NULL,
            avatar_url TEXT,
            heygen_avatar_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # Create videos table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            avatar_id INTEGER,
            title TEXT NOT NULL,
            script TEXT,
            video_url TEXT,
            heygen_job_id TEXT,
            status TEXT DEFAULT 'pending',
            video_format TEXT DEFAULT '16:9',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (avatar_id) REFERENCES avatars (id)
        )
    """)
    
    # Create admin user if not exists
    cur.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not cur.fetchone():
        hashed_password = pwd_context.hash("admin123")
        cur.execute("""
            INSERT INTO users (username, email, hashed_password, is_admin) 
            VALUES (?, ?, ?, ?)
        """, ("admin", "admin@myavatar.com", hashed_password, 1))
        print("✅ Admin user created:")
        print("   Username: admin")
        print("   Password: admin123")
    else:
        print("ℹ️  Admin user already exists")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print("\n✅ Database initialized successfully!")
    print("📁 Database file: myavatar.db")
    print("\nTables created:")
    print("  - users")
    print("  - avatars")
    print("  - videos")

if __name__ == "__main__":
    init_database()
