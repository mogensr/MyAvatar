#!/usr/bin/env python3
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Connect to production database (Railway)
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor(cursor_factory=RealDictCursor)

print("🔍 Checking PRODUCTION database schema...")

# Get all columns in videos table
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns 
    WHERE table_name = 'videos'
    ORDER BY ordinal_position;
""")

columns = cur.fetchall()

print(f"\n📊 Found {len(columns)} columns in 'videos' table:")
print("-" * 50)

for col in columns:
    print(f"  {col['column_name']:20} | {col['data_type']:15} | {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")

print("\n🔍 Looking for video URL columns specifically:")
video_url_columns = [col for col in columns if 'video' in col['column_name'].lower() and ('url' in col['column_name'].lower() or 'path' in col['column_name'].lower())]

if video_url_columns:
    for col in video_url_columns:
        print(f"  ✅ {col['column_name']} ({col['data_type']})")
else:
    print("  ❌ No video URL/path columns found!")

# Also check a sample record to see what data exists
print("\n🎬 Sample video record:")
cur.execute("SELECT * FROM videos WHERE status = 'completed' LIMIT 1")
sample = cur.fetchone()

if sample:
    for key, value in sample.items():
        if 'video' in key.lower():
            print(f"  {key}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
else:
    print("  No completed videos found")

cur.close()
conn.close()
