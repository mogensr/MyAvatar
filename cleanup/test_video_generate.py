import requests

url = "http://localhost:8000/api/video/generate"
files = {'audio': open('test_audio.m4a', 'rb')}
data = {'avatar_id': 3}

session_cookie = "eyJ1c2VyIjogeyJpZCI6IDEsICJ1c2VybmFtZSI6ICJhZG1pbiIsICJpc19hZG1pbiI6IDF9fQ==.aDyraA._rRCfpyUpSGW7BN10-hVk_b5hxE"
cookies = {"session": session_cookie}

response = requests.post(url, files=files, data=data, cookies=cookies)
print("Status code:", response.status_code)
print("Response:", response.text)
