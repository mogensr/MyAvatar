#!/usr/bin/env python3
"""
AUTO-EXECUTE: Emergency premium fix on startup
==============================================
This will run the emergency fix automatically when the app starts
"""

import subprocess
import sys
import os

def run_emergency_fix():
    """Run the emergency premium fix automatically"""
    print("🚨 AUTO-EXECUTING EMERGENCY PREMIUM FIX...")
    
    try:
        # Run the emergency fix script
        result = subprocess.run([
            sys.executable, 
            'emergency_premium_database_fix.py'
        ], capture_output=True, text=True, cwd=os.path.dirname(__file__))
        
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("✅ Emergency fix completed successfully!")
        else:
            print(f"❌ Emergency fix failed with code: {result.returncode}")
            
    except Exception as e:
        print(f"❌ Error running emergency fix: {e}")

if __name__ == "__main__":
    run_emergency_fix()
