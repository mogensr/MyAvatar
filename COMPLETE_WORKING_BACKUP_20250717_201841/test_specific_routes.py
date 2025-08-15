#!/usr/bin/env python3
"""
Test specific admin routes that are failing
"""
import requests
import json

def test_failing_routes():
    base_url = 'https://app.myavatar.dk'
    login_url = f'{base_url}/login'
    routes_to_test = ['/admin/manage-voices', '/admin/manage-avatars', '/admin/manage-videos']

    # Login first
    session = requests.Session()
    login_data = {'username': 'admin', 'password': 'Admin2025!'}
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
                print(f'  Server error - check logs')
                print(f'  Response text: {response.text[:200]}...')
        except Exception as e:
            print(f'{route}: Error - {e}')

if __name__ == "__main__":
    test_failing_routes()
