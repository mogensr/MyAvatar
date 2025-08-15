import os
import psycopg2

DATABASE_URL = os.getenv('DATABASE_URL')
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("🔍 Checking for triggers on videos table...")

# Check for triggers
cur.execute("""
    SELECT trigger_name, event_manipulation, action_statement 
    FROM information_schema.triggers 
    WHERE event_object_table = 'videos'
""")

triggers = cur.fetchall()
if triggers:
    print("📋 TRIGGERS FOUND:")
    for trigger in triggers:
        print(f"   {trigger[0]} - {trigger[1]}: {trigger[2]}")
else:
    print("✅ No triggers found on videos table")

# Check actual table definition
print("\n📋 ACTUAL TABLE DEFINITION:")
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns 
    WHERE table_name = 'videos'
    ORDER BY ordinal_position
""")

columns = cur.fetchall()
for col in columns:
    nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
    default = f" DEFAULT {col[3]}" if col[3] else ""
    print(f"   {col[0]} {col[1]} {nullable}{default}")

# Test INSERT without avatar_id
print("\n🧪 TESTING INSERT WITHOUT avatar_id...")
try:
    cur.execute("""
        INSERT INTO videos (user_id, title, video_path, input_url) 
        VALUES (1, 'Test Video', 'test_url', 'test_job') 
        RETURNING id
    """)
    result = cur.fetchone()
    print(f"✅ SUCCESS: Inserted video with ID {result[0]}")
    
    # Clean up test record
    cur.execute("DELETE FROM videos WHERE id = %s", (result[0],))
    conn.commit()
    print("🧹 Test record cleaned up")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    conn.rollback()

conn.close()
