from app.db.database import execute_query
import sqlite3

# Get table info for users table
try:
    schema = execute_query('PRAGMA table_info(users)', fetch_all=True)
    print('USERS TABLE COLUMNS:')
    for col in schema:
        print(f'  {col[1]} - {col[2]}')
except Exception as e:
    print(f'Error: {e}')

# List all tables
try:
    tables = execute_query('SELECT name FROM sqlite_master WHERE type="table"', fetch_all=True)
    print('\nALL TABLES:')
    for table in tables:
        print(f'  {table[0]}')
except Exception as e:
    print(f'Error: {e}')