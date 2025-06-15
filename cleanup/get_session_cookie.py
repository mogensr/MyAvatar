import requests

# Change these if you use a different username/password
username = "admin"
password = "admin123"

login_url = "http://localhost:8000/auth/login"
session = requests.Session()

# Get login page (to establish session)
session.get(login_url)

# Post login credentials
response = session.post(login_url, data={"username": username, "password": password})

if response.status_code == 200 or response.status_code == 302:
    cookies = session.cookies.get_dict()
    print("Session cookies:", cookies)
    if "session" in cookies:
        print("Your session cookie value is also saved to session_cookie.txt")
        with open("session_cookie.txt", "w") as f:
            f.write(cookies["session"])
    else:
        print("Login succeeded but no session cookie found.")
else:
    print("Login failed! Status code:", response.status_code)
    print(response.text)
