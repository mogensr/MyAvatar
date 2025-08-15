#!/usr/bin/env python3
"""
Test user-specific admin routes that the buttons should link to
"""
import requests

def test_user_specific_routes():
    base_url = 'https://app.myavatar.dk'
    login_url = f'{base_url}/login'

    # Login first
    session = requests.Session()
    login_data = {'username': 'admin', 'password': 'Admin2025!'}
    login_response = session.post(login_url, data=login_data, allow_redirects=False)
    print(f'Login status: {login_response.status_code}')

    # Test user-specific routes (using user ID 1 from the screenshot)
    routes_to_test = [
        '/admin/manage-avatars/1',  # Avatare button for admin user
        '/admin/manage-videos/1',   # Videoer button for admin user
        '/admin/manage-avatars/2',  # Avatare button for testuser
        '/admin/manage-videos/2',   # Videoer button for testuser
    ]

    for route in routes_to_test:
        try:
            response = session.get(f'{base_url}{route}', allow_redirects=False)
            print(f'\n{route}: Status {response.status_code}')
            
            if response.status_code == 200:
                print(f'  ✅ Success!')
            elif response.status_code == 302:
                location = response.headers.get('Location', 'Unknown')
                print(f'  🔄 Redirected to: {location}')
            elif response.status_code == 404:
                print(f'  ❌ Route not found')
            elif response.status_code == 500:
                try:
                    error_data = response.json()
                    print(f'  💥 Error: {error_data.get("error", "Unknown")}')
                    print(f'  Detail: {error_data.get("detail", "No details")}')
                except:
                    print(f'  💥 Server error (no JSON response)')
        except Exception as e:
            print(f'{route}: Connection error - {e}')

if __name__ == "__main__":
    test_user_specific_routes()
