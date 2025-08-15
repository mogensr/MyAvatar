"""
MyAvatar Quick Test Script
Run this to test critical functionality of the MyAvatar application
"""
import sys
import requests
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Initialize console with rich formatting
console = Console()

# Base URL for API testing
BASE_URL = "http://127.0.0.1:8000"

def print_header(text):
    """Print a formatted header"""
    console.print(f"\n[bold blue]{text}[/bold blue]")
    console.print("=" * len(text))

def test_endpoint(method, url, auth=None, data=None, expected_status=200, description=""):
    """Test an endpoint and return the result"""
    full_url = f"{BASE_URL}{url}"
    console.print(f"Testing: [cyan]{method} {url}[/cyan] - {description}")
    
    try:
        if method.lower() == "get":
            response = requests.get(full_url, cookies=auth)
        elif method.lower() == "post":
            response = requests.post(full_url, data=data, cookies=auth)
        else:
            console.print(f"[red]Unsupported method: {method}[/red]")
            return False, None
        
        status_match = response.status_code == expected_status
        status_color = "green" if status_match else "red"
        
        console.print(f"  Status: [bold {status_color}]{response.status_code}[/bold {status_color}] (Expected: {expected_status})")
        
        try:
            response_json = response.json()
            console.print(f"  Response: {json.dumps(response_json, indent=2)[:150]}...")
        except:
            console.print(f"  Response: [italic](Non-JSON response, length: {len(response.text)} characters)[/italic]")
        
        return status_match, response
    
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        return False, None

def run_tests():
    """Run all tests"""
    console.print(Panel.fit("MyAvatar Quick Test", style="bold green"))
    
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
    finance_connection, finance_resp = test_endpoint("GET", "/finance/api/connection-test", 
                                                     expected_status=401, 
                                                     description="Finance API connection test")
    
    # Show test summary
    print_header("Test Summary")
    table = Table(show_header=True)
    table.add_column("Test Category", style="bold")
    table.add_column("Status", style="bold")
    
    def add_result(name, success):
        status = "[green]PASS[/green]" if success else "[red]FAIL[/red]"
        table.add_row(name, status)
    
    add_result("Basic Connectivity", root_success)
    add_result("API Endpoints", all([api_videos, api_avatars, api_voices]))
    add_result("Authentication", login_get)
    add_result("Financial Data", finance_connection)
    
    console.print(table)
    
    # Final assessment
    all_success = all([root_success, api_videos, api_avatars, api_voices, login_get, finance_connection])
    if all_success:
        console.print(Panel.fit("✅ All tests passed! The application appears ready for deployment.", 
                              style="bold green"))
    else:
        console.print(Panel.fit("⚠️ Some tests failed. Review the issues before deploying.", 
                              style="bold red"))

if __name__ == "__main__":
    try:
        run_tests()
    except KeyboardInterrupt:
        console.print("\n[yellow]Tests aborted by user.[/yellow]")
        sys.exit(1)
