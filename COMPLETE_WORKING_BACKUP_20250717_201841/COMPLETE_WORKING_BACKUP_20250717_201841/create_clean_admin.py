from app.db.database import execute_query
from app.auth.authentication import get_password_hash

# Create a clean admin user
admin_password = 'Admin2025!'
password_hash = get_password_hash(admin_password)

# Delete any existing admin user first
execute_query('DELETE FROM users WHERE username = ?', ('admin',))

# Create new admin user
execute_query(
    'INSERT INTO users (username, email, hashed_password, is_admin, created_at) VALUES (?, ?, ?, ?, datetime("now"))',
    ('admin', 'admin@myavatar.dk', password_hash, 1)
)

print('✅ Clean admin user created!')
print('Username: admin')
print('Password: Admin2025!')
print('Email: admin@myavatar.dk')
