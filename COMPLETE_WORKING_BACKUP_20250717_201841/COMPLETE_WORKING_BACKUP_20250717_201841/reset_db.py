from app.db.database import init_database, get_db_connection; import os; os.remove('myavatar.db') if os.path.exists('myavatar.db') else None; init_database(); print('Database reset complete') 
