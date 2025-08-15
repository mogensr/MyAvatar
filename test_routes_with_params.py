#!/usr/bin/env python3
"""
Test admin routes with proper parameters
"""
import requests
import json

def test_routes_with_params():
    base_url = 'https://app.myavatar.dk'
    login_url = f'{base_url}/login'

    # Login first
    session = requests.Session()
    login_data = {'username': 'admin', 'password': 'Admin2025!'}
    login_response = session.post(login_url, data=login_data, allow_redirects=False)
    print(f'Login status: {login_response.status_code}')

    # Test routes
    routes_to_test = [
        '/admin/manage-voices',  # Should work now
        '/admin/manage-avatars',  # Should redirect to users (no user_id)
        '/admin/manage-avatars?user_id=1',  # Should work with user_id
        '/admin/manage-videos',  # Should redirect to users (no user_id)
        '/admin/manage-videos?user_id=1',  # Should work with user_id
    ]

    for route in routes_to_test:
        try:
            response = session.get(f'{base_url}{route}', allow_redirects=False)
            print(f'\n{route}: Status {response.status_code}')
            
            if response.status_code == 302:
                location = response.headers.get('Location', 'Unknown')
                print(f'  Redirected to: {location}')
            elif response.status_code == 500:
                try:
                    error_data = response.json()
                    print(f'  Error: {error_data.get("error", "Unknown")}')
                    print(f'  Detail: {error_data.get("detail", "No details")}')
                except:
                    print(f'  Raw response: {response.text[:200]}')
            elif response.status_code == 200:
                print(f'  ✅ Success!')
        except Exception as e:
            print(f'{route}: Connection error - {e}')

if __name__ == "__main__":
    test_routes_with_params()
