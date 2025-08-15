#!/usr/bin/env python3
"""
Test admin routes locally
"""
import requests
import json

def test_local_routes():
    base_url = 'http://localhost:8000'
    login_url = f'{base_url}/login'
    routes_to_test = ['/admin/manage-voices', '/admin/manage-avatars', '/admin/manage-videos', '/admin/emergency-controls']

    # Login first
    session = requests.Session()
    login_data = {'username': 'admin', 'password': 'Admin2025!'}
    
    try:
        login_response = session.post(login_url, data=login_data, allow_redirects=False)
        print(f'Login status: {login_response.status_code}')
        
        # Test each route
        for route in routes_to_test:
            try:
                response = session.get(f'{base_url}{route}', allow_redirects=False)
                print(f'{route}: Status {response.status_code}')
                if response.status_code == 302:
                    location = response.headers.get('Location', 'Unknown')
                    print(f'  Redirected to: {location}')
                elif response.status_code == 500:
                    print(f'  Server error')
                    print(f'  Response: {response.text[:200]}...')
                elif response.status_code == 200:
                    print(f'  ✅ Success!')
            except Exception as e:
                print(f'{route}: Error - {e}')
    except Exception as e:
        print(f'Connection error: {e}')

if __name__ == "__main__":
    test_local_routes()
