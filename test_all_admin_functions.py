#!/usr/bin/env python3
"""
Comprehensive Admin Function Testing Script
Tests all admin routes and functions while USER is away
"""

import requests
import json
from urllib.parse import urljoin
import time

class AdminTester:
    def __init__(self, base_url="https://app.myavatar.dk"):
        self.base_url = base_url
        self.session = requests.Session()
        self.admin_credentials = {
            "username": "admin",
            "password": "Admin2025!"
        }
        self.logged_in = False
        
    def login(self):
        """Login as admin user"""
        print("🔐 Attempting admin login...")
        
        # First get the login page to get any CSRF tokens
        login_page = self.session.get(f"{self.base_url}/login")
        print(f"Login page status: {login_page.status_code}")
        
        # Attempt login
        login_data = {
            "username": self.admin_credentials["username"],
            "password": self.admin_credentials["password"]
        }
        
        login_response = self.session.post(
            f"{self.base_url}/login",
            data=login_data,
            allow_redirects=False
        )
        
        print(f"Login response status: {login_response.status_code}")
        print(f"Login response headers: {dict(login_response.headers)}")
        
        # Check if login was successful (should redirect)
        if login_response.status_code in [302, 303]:
            self.logged_in = True
            print("✅ Admin login successful!")
            return True
        else:
            print("❌ Admin login failed!")
            print(f"Response: {login_response.text[:500]}")
            return False
    
    def test_route(self, route, description):
        """Test a specific admin route"""
        print(f"\n🧪 Testing {description}")
        print(f"Route: {route}")
        
        try:
            response = self.session.get(f"{self.base_url}{route}")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Route accessible")
                # Check if it's actually the admin page (not redirected to login)
                if "login" in response.url.lower() or "Login" in response.text:
                    print("⚠️  Redirected to login - authentication issue")
                    return False
                else:
                    print("✅ Admin page loaded successfully")
                    return True
            elif response.status_code in [302, 303]:
                print(f"↩️  Redirected to: {response.headers.get('Location', 'Unknown')}")
                return False
            else:
                print(f"❌ Error: {response.status_code}")
                if response.text:
                    print(f"Error details: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
            return False
    
    def test_all_admin_routes(self):
        """Test all known admin routes"""
        admin_routes = [
            ("/admin", "Main Admin Page"),
            ("/admin/dashboard", "Admin Dashboard"),
            ("/admin/users", "User Management"),
            ("/admin/manage-passwords", "Password Management"),
            ("/admin/manage-voices", "Voice Management"),
            ("/admin/manage-avatars", "Avatar Management"),
            ("/admin/manage-videos", "Video Management"),
            ("/admin/emergency-controls", "Emergency Controls"),
        ]
        
        results = {}
        
        print("\n" + "="*50)
        print("🔍 TESTING ALL ADMIN ROUTES")
        print("="*50)
        
        for route, description in admin_routes:
            results[route] = self.test_route(route, description)
            time.sleep(1)  # Be nice to the server
        
        return results
    
    def generate_report(self, results):
        """Generate a comprehensive test report"""
        print("\n" + "="*50)
        print("📊 ADMIN TESTING REPORT")
        print("="*50)
        
        working_routes = [route for route, status in results.items() if status]
        broken_routes = [route for route, status in results.items() if not status]
        
        print(f"\n✅ Working Routes ({len(working_routes)}):")
        for route in working_routes:
            print(f"  - {route}")
        
        print(f"\n❌ Broken Routes ({len(broken_routes)}):")
        for route in broken_routes:
            print(f"  - {route}")
        
        print(f"\n📈 Success Rate: {len(working_routes)}/{len(results)} ({len(working_routes)/len(results)*100:.1f}%)")
        
        return {
            "working": working_routes,
            "broken": broken_routes,
            "success_rate": len(working_routes)/len(results)*100
        }

def main():
    print("🚀 Starting Comprehensive Admin Testing")
    print("="*50)
    
    tester = AdminTester()
    
    # Step 1: Login
    if not tester.login():
        print("❌ Cannot proceed without admin login")
        return
    
    # Step 2: Test all routes
    results = tester.test_all_admin_routes()
    
    # Step 3: Generate report
    report = tester.generate_report(results)
    
    # Step 4: Save results for USER
    with open("admin_test_results.json", "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": results,
            "summary": report
        }, f, indent=2)
    
    print(f"\n💾 Results saved to admin_test_results.json")
    print("🎯 Testing complete!")

if __name__ == "__main__":
    main()
