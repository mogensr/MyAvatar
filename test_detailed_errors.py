#!/usr/bin/env python3
"""
Get detailed error information for failing admin routes
"""
import requests
import json

def test_detailed_errors():
    base_url = 'https://app.myavatar.dk'
    login_url = f'{base_url}/login'
    routes_to_test = ['/admin/manage-voices', '/admin/manage-avatars', '/admin/manage-videos']

    # Login first
    session = requests.Session()
    login_data = {'username': 'admin', 'password': 'Admin2025!'}
    login_response = session.post(login_url, data=login_data, allow_redirects=False)
    print(f'Login status: {login_response.status_code}')

    # Test each route and get full error details
    for route in routes_to_test:
        try:
            response = session.get(f'{base_url}{route}', allow_redirects=False)
            print(f'\n{route}: Status {response.status_code}')
            if response.status_code == 500:
                try:
                    error_data = response.json()
                    print(f'  Error: {error_data.get("error", "Unknown")}')
                    print(f'  Detail: {error_data.get("detail", "No details")}')
                except:
                    print(f'  Raw response: {response.text[:500]}')
            elif response.status_code == 200:
                print(f'  ✅ Success!')
        except Exception as e:
            print(f'{route}: Connection error - {e}')

if __name__ == "__main__":
    test_detailed_errors()
