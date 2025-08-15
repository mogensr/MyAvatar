"""
MyAvatar Validation Script
Validates the functionality of key components to ensure readiness for deployment.
"""
import os
import sys
import json
import requests
import unittest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define constants
BASE_URL = "http://127.0.0.1:8000"
TEST_USERNAME = "test_user"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test_password"

class MyAvatarValidator:
    def __init__(self):
        self.auth_cookie = None
        self.session = requests.Session()
        self.results = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "details": []
        }
    
    def log_result(self, test_name, passed, message=""):
        """Log test result"""
        status = "PASSED" if passed else "FAILED"
        self.results["tests_run"] += 1
        if passed:
            self.results["tests_passed"] += 1
            print(f"✅ {test_name}: {status}")
        else:
            self.results["tests_failed"] += 1
            print(f"❌ {test_name}: {status} - {message}")
            
        self.results["details"].append({
            "test": test_name,
            "status": status,
            "message": message
        })
    
    def validate_imports(self):
        """Test that all modules import correctly"""
        try:
            # Test app imports
            from app.db import database
            from app.api import heygen, tiingo
            from app.auth import authentication
            from app.logger import log_handler
            from app.storage import file_storage
            from app.utils import avatar_utils
            from app.routes import api_routes, web_routes, finance_routes
            
            # Test main app imports
            import main
            
            self.log_result("Import validation", True)
            return True
        except Exception as e:
            self.log_result("Import validation", False, f"Import error: {str(e)}")
            return False
    
    def validate_server(self):
        """Test that the server responds"""
        try:
            response = self.session.get(f"{BASE_URL}")
            if response.status_code == 200:
                self.log_result("Server validation", True)
                return True
            else:
                self.log_result("Server validation", False, f"Server returned status code {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Server validation", False, f"Connection error: {str(e)}")
            return False
    
    def validate_login(self):
        """Test login functionality"""
        try:
            # First try to log in with existing user
            response = self.session.post(
                f"{BASE_URL}/login",
                data={
                    "username": TEST_USERNAME,
                    "password": TEST_PASSWORD
                },
                allow_redirects=False
            )
            
            if response.status_code in [302, 303]:  # Redirect after successful login
                self.auth_cookie = response.cookies.get("access_token")
                if self.auth_cookie:
                    self.log_result("Login validation", True)
                    return True
                else:
                    self.log_result("Login validation", False, "No auth cookie received")
                    return False
            elif response.status_code == 200:  # Login page with error
                # Create a new test user and try again
                print("Attempting to register test user...")
                reg_response = self.session.post(
                    f"{BASE_URL}/register",
                    data={
                        "username": TEST_USERNAME,
                        "email": TEST_EMAIL,
                        "password": TEST_PASSWORD
                    },
                    allow_redirects=False
                )
                
                if reg_response.status_code in [302, 303]:
                    # Try login again
                    response = self.session.post(
                        f"{BASE_URL}/login",
                        data={
                            "username": TEST_USERNAME,
                            "password": TEST_PASSWORD
                        },
                        allow_redirects=False
                    )
                    
                    if response.status_code in [302, 303]:
                        self.auth_cookie = response.cookies.get("access_token")
                        if self.auth_cookie:
                            self.log_result("Login validation (after registration)", True)
                            return True
                    
                self.log_result("Login validation", False, "Login failed, even after registration attempt")
                return False
            else:
                self.log_result("Login validation", False, f"Unexpected status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Login validation", False, f"Error: {str(e)}")
            return False
    
    def validate_dashboard(self):
        """Test dashboard access"""
        try:
            response = self.session.get(f"{BASE_URL}/dashboard")
            if response.status_code == 200:
                self.log_result("Dashboard validation", True)
                return True
            else:
                self.log_result("Dashboard validation", False, f"Dashboard returned status code {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Dashboard validation", False, f"Error: {str(e)}")
            return False
    
    def validate_api_endpoints(self):
        """Test API endpoints"""
        endpoints = [
            "/api/videos",
            "/api/avatars",
            "/api/voices"
        ]
        
        all_passed = True
        for endpoint in endpoints:
            try:
                response = self.session.get(f"{BASE_URL}{endpoint}")
                if response.status_code in [200, 401]:  # 401 is ok if not logged in
                    self.log_result(f"API endpoint {endpoint}", True)
                else:
                    self.log_result(f"API endpoint {endpoint}", False, f"Status code: {response.status_code}")
                    all_passed = False
            except Exception as e:
                self.log_result(f"API endpoint {endpoint}", False, f"Error: {str(e)}")
                all_passed = False
        
        return all_passed
    
    def validate_finance_endpoints(self):
        """Test finance API endpoints"""
        if not os.getenv("TIINGO_API_KEY"):
            self.log_result("Finance API", False, "TIINGO_API_KEY not found in environment")
            return False
            
        endpoints = [
            "/finance/api/stock-price/AAPL",
            "/finance/api/connection-test"
        ]
        
        all_passed = True
        for endpoint in endpoints:
            try:
                response = self.session.get(f"{BASE_URL}{endpoint}")
                if response.status_code in [200, 401]:  # 401 is ok if not logged in
                    self.log_result(f"Finance endpoint {endpoint}", True)
                else:
                    self.log_result(f"Finance endpoint {endpoint}", False, f"Status code: {response.status_code}")
                    all_passed = False
            except Exception as e:
                self.log_result(f"Finance endpoint {endpoint}", False, f"Error: {str(e)}")
                all_passed = False
        
        return all_passed
    
    def validate_env_vars(self):
        """Validate that critical environment variables are set"""
        required_vars = [
            "HEYGEN_API_KEY", 
            "JWT_SECRET_KEY",
            "TIINGO_API_KEY",
            "CLOUDINARY_CLOUD_NAME",
            "CLOUDINARY_API_KEY",
            "CLOUDINARY_API_SECRET"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if not missing_vars:
            self.log_result("Environment variables", True)
            return True
        else:
            self.log_result("Environment variables", False, f"Missing: {', '.join(missing_vars)}")
            return False
    
    def run_all_validations(self):
        """Run all validation tests"""
        print("\n=== MyAvatar Validation Suite ===")
        print("Running pre-launch validation checks...\n")
        
        # Run validations
        self.validate_imports()
        self.validate_server()
        self.validate_env_vars()
        self.validate_login()
        self.validate_dashboard()
        self.validate_api_endpoints()
        self.validate_finance_endpoints()
        
        # Print summary
        print("\n=== Validation Summary ===")
        print(f"Tests Run: {self.results['tests_run']}")
        print(f"Tests Passed: {self.results['tests_passed']}")
        print(f"Tests Failed: {self.results['tests_failed']}")
        
        if self.results['tests_failed'] > 0:
            print("\nThe following tests failed:")
            for detail in self.results['details']:
                if detail['status'] == 'FAILED':
                    print(f"- {detail['test']}: {detail['message']}")
            
            print("\nPlease address these issues before proceeding with deployment.")
        else:
            print("\n🎉 All tests passed! MyAvatar is ready for deployment.")
        
        # Write results to file
        with open("validation_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        print("\nDetailed results saved to validation_results.json")

if __name__ == "__main__":
    validator = MyAvatarValidator()
    validator.run_all_validations()
