import sqlite3

db = 'myavatar.db'  # <-- ret til dit rigtige databasefilnavn
conn = sqlite3.connect(db)
cur = conn.cursor()

# Tjek kolonner
cur.execute("PRAGMA table_info(avatars);")
print("Kolonner i avatars-tabellen:")
for row in cur.fetchall():
    print(row)

# Tilføj avatar_url hvis den mangler
try:
    cur.execute("ALTER TABLE avatars ADD COLUMN avatar_url TEXT;")
    print("Tilføjede avatar_url kolonne.")
except sqlite3.OperationalError:
    print("Kolonnen avatar_url findes allerede.")

# Kopiér data fra image_path hvis nødvendigt
cur.execute("UPDATE avatars SET avatar_url = image_path WHERE avatar_url IS NULL OR avatar_url = ''")
conn.commit()
print("Evt. gamle image_path-værdier kopieret til avatar_url.")

conn.close()
print("Done.")