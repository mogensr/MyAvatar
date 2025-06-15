import requests

# Login
session = requests.Session()
login = session.post('http://localhost:8000/auth/login', 
                     data={'username': 'admin', 'password': 'admin123'})
print(f"Login status: {login.status_code}")

# Test endpoint
files = {'audio': ('test.webm', b'dummy content', 'audio/webm')}
data = {'title': 'Test', 'avatar_id': '1'}
response = session.post('http://localhost:8000/api/video/generate', 
                       files=files, data=data)
print(f"API status: {response.status_code}")
print(f"Response: {response.text}")