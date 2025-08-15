from app.db.database import execute_query; execute_query('ALTER TABLE user_avatars ALTER COLUMN is_default TYPE INTEGER USING CASE WHEN is_default THEN 1 ELSE 0 END'); print('Migration completed') 
