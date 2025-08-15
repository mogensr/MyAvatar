#!/usr/bin/env python3
"""
Check Railway deployment status and logs
"""
import subprocess
import sys

def check_railway_status():
    """Check Railway deployment status"""
    
    print("🚂 Checking Railway Status...")
    print("=" * 60)
    
    # Check if railway CLI is installed
    try:
        result = subprocess.run(['railway', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Railway CLI: {result.stdout.strip()}")
        else:
            print("❌ Railway CLI not found or not working")
            return
    except Exception as e:
        print(f"❌ Railway CLI error: {e}")
        print("\n💡 Install Railway CLI: npm install -g @railway/cli")
        return
    
    # Check login status
    try:
        result = subprocess.run(['railway', 'whoami'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Logged in as: {result.stdout.strip()}")
        else:
            print("❌ Not logged in to Railway")
            print("💡 Run: railway login")
            return
    except Exception as e:
        print(f"❌ Railway login check failed: {e}")
        return
    
    # Check project status
    try:
        result = subprocess.run(['railway', 'status'], 
                              capture_output=True, text=True, timeout=15)
        print(f"\n📊 Railway Project Status:")
        print(result.stdout)
        if result.stderr:
            print(f"⚠️ Warnings: {result.stderr}")
    except Exception as e:
        print(f"❌ Railway status check failed: {e}")
    
    # Get recent logs
    try:
        print(f"\n📋 Recent Railway Logs (last 20 lines):")
        print("-" * 40)
        result = subprocess.run(['railway', 'logs', '--tail', '20'], 
                              capture_output=True, text=True, timeout=15)
        if result.stdout:
            print(result.stdout)
        else:
            print("No logs available")
        if result.stderr:
            print(f"⚠️ Log errors: {result.stderr}")
    except Exception as e:
        print(f"❌ Railway logs failed: {e}")

if __name__ == "__main__":
    check_railway_status()
