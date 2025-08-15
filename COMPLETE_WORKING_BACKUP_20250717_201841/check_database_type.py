from app.db.database import execute_query, USE_POSTGRES
import os

print("🔍 DATABASE TYPE CHECK:")
print("=" * 50)
print(f"USE_POSTGRES setting: {USE_POSTGRES}")
print(f"DATABASE_URL environment variable: {'SET' if os.getenv('DATABASE_URL') else 'NOT SET'}")

if USE_POSTGRES:
    print("\n🐘 USING POSTGRESQL")
    try:
        # Check PostgreSQL schema
        schema = execute_query('SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s', ('users',), fetch_all=True)
        print('\nPOSTGRESQL USERS TABLE COLUMNS:')
        for col in schema:
            print(f'  {col[0]} - {col[1]}')
    except Exception as e:
        print(f'PostgreSQL Error: {e}')
else:
    print("\n🗄️ USING SQLITE")
    try:
        # Check SQLite schema (we already know this works)
        schema = execute_query('PRAGMA table_info(users)', fetch_all=True)
        print('\nSQLITE USERS TABLE COLUMNS:')
        for col in schema:
            print(f'  {col[1]} - {col[2]}')
    except Exception as e:
        print(f'SQLite Error: {e}')

# List all tables
try:
    if USE_POSTGRES:
        tables = execute_query('SELECT table_name FROM information_schema.tables WHERE table_schema = %s', ('public',), fetch_all=True)
    else:
        tables = execute_query('SELECT name FROM sqlite_master WHERE type="table"', fetch_all=True)
    
    print('\nALL TABLES:')
    for table in tables:
        print(f'  {table[0]}')
except Exception as e:
    print(f'Error listing tables: {e}')
