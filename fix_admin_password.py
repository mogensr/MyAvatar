from app.database.database_manager import DatabaseManager
from werkzeug.security import generate_password_hash

# Update admin password
db = DatabaseManager()
password_hash = generate_password_hash('admin123')

query = "UPDATE users SET password = %s WHERE username = 'admin'"
db.execute_query(query, (password_hash,))

print("Admin password updated successfully!")