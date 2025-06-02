import sqlite3

DB_FILE = "myavatar.db"  # Ret hvis din databasefil hedder noget andet

def migrate_users_table():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Hent kolonnenavne
    cur.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in cur.fetchall()]

    if "useravatar_name" not in cols and "username" in cols:
        print("Migrerer 'username' til 'useravatar_name' ...")
        # Opret ny tabel med korrekt navn
        cur.execute("""
            CREATE TABLE users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                useravatar_name TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Kopier data over
        cur.execute("""
            INSERT INTO users_new (id, useravatar_name, email, hashed_password, is_admin, created_at)
            SELECT id, username, email, hashed_password, is_admin, created_at FROM users
        """)
        # Slet gammel tabel og omdøb ny
        cur.execute("DROP TABLE users")
        cur.execute("ALTER TABLE users_new RENAME TO users")
        conn.commit()
        print("Migration gennemført.")
    else:
        print("Ingen migration nødvendig.")

    conn.close()

if __name__ == "__main__":
    migrate_users_table()