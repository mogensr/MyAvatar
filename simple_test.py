"""
MyAvatar Simple Test Script
Basic functionality test without fancy formatting
"""
import requests
import json

# Base URL for API testing
BASE_URL = "http://127.0.0.1:8000"

def print_header(text):
    """Print a formatted header"""
    print(f"\n{text}")
    print("=" * len(text))

def test_endpoint(method, url, auth=None, data=None, expected_status=200, description=""):
    """Test an endpoint and return the result"""
    full_url = f"{BASE_URL}{url}"
    print(f"Testing: {method} {url} - {description}")
    
    try:
        if method.lower() == "get":
            response = requests.get(full_url, cookies=auth)
        elif method.lower() == "post":
            response = requests.post(full_url, data=data, cookies=auth)
        else:
            print(f"Unsupported method: {method}")
            return False, None
        
        status_match = response.status_code == expected_status
        status_text = "PASS" if status_match else "FAIL"
        
        print(f"  Status: {response.status_code} (Expected: {expected_status}) - {status_text}")
        
        try:
            response_json = response.json()
            # Only show first 150 chars of the response
            print(f"  Response: {json.dumps(response_json, indent=2)[:150]}...")
        except:
            print(f"  Response: Non-JSON response, length: {len(response.text)} characters")
        
        return status_match, response
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return False, None

def run_tests():
    """Run all tests"""
    print("\nMyAvatar Quick Test")
    print("==================")
    
    # Test basic connectivity
    print_header("Basic Connectivity Tests")
    root_success, _ = test_endpoint("GET", "/", expected_status=200, description="Application root")
    
    # Test API endpoints
    print_header("API Endpoints")
    api_videos, _ = test_endpoint("GET", "/api/videos", expected_status=401, description="Videos API (unauthenticated)")
    api_avatars, _ = test_endpoint("GET", "/api/avatars", expected_status=401, description="Avatars API (unauthenticated)")
    api_voices, _ = test_endpoint("GET", "/api/voices", expected_status=401, description="Voices API (unauthenticated)")
    
    # Test authentication
    print_header("Authentication")
    login_get, _ = test_endpoint("GET", "/login", expected_status=200, description="Login page")
    
    # Test finance endpoints
    print_header("Financial Data")
    finance_connection, _ = test_endpoint("GET", "/finance/api/connection-test", 
                                         expected_status=401, 
                                         description="Finance API connection test")
    
    # Show test summary
    print_header("Test Summary")
    print(f"Basic Connectivity: {'PASS' if root_success else 'FAIL'}")
    print(f"API Endpoints: {'PASS' if all([api_videos, api_avatars, api_voices]) else 'FAIL'}")
    print(f"Authentication: {'PASS' if login_get else 'FAIL'}")
    print(f"Financial Data: {'PASS' if finance_connection else 'FAIL'}")
    
    # Final assessment
    all_success = all([root_success, api_videos, api_avatars, api_voices, login_get, finance_connection])
    if all_success:
        print("\n✅ All tests passed! The application appears ready for deployment.")
    else:
        print("\n⚠️ Some tests failed. Review the issues before deploying.")

if __name__ == "__main__":
    try:
        run_tests()
    except KeyboardInterrupt:
        print("\nTests aborted by user.")
        import sys
        sys.exit(1)
