import psycopg2

# Update these values with your actual database credentials
conn = psycopg2.connect(
    dbname='your_db_name',
    user='your_db_user',
    password='your_db_password',
    host='your_db_host',
    port='your_db_port'
)

cur = conn.cursor()
cur.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS input_url TEXT;")
conn.commit()
cur.close()
conn.close()
print("input_url column added to videos table.")
