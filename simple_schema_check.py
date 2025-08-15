import os
import psycopg2

DATABASE_URL = os.getenv('DATABASE_URL')
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Check if avatar_id is nullable
cur.execute("""
    SELECT is_nullable 
    FROM information_schema.columns 
    WHERE table_name = 'videos' AND column_name = 'avatar_id'
""")

result = cur.fetchone()
if result:
    is_nullable = result[0]
    print(f"avatar_id is_nullable: {is_nullable}")
    
    if is_nullable == 'NO':
        print("SOLUTION: Need to make avatar_id nullable")
    else:
        print("avatar_id is already nullable")
else:
    print("avatar_id column not found")

conn.close()
