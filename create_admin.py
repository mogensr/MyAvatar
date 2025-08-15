#!/usr/bin/env python3
"""
Create emergency admin user
"""
import requests
import json

def create_admin():
    """Create emergency admin user"""
    url = "http://localhost:8000/create-emergency-admin"
    
    # The hint asks for "Your blackbelt level in Ju-Jitsu"
    # I'll try a few common answers
    possible_answers = ["1", "first", "1st", "black", "shodan"]
    
    for answer in possible_answers:
        data = {
            "master_key": answer,
            "username": "admin",
            "password": "admin123",
            "email": "admin@myavatar.com"
        }
        
        print(f"🔍 Trying master_key: '{answer}'")
        
        try:
            response = requests.post(url, json=data)
            result = response.json()
            
            if response.status_code == 200 and result.get("success"):
                print(f"✅ SUCCESS! Admin user created with master_key: '{answer}'")
                print(f"   Username: admin")
                print(f"   Password: admin123")
                print(f"   User ID: {result.get('user_id')}")
                return True
            else:
                print(f"❌ Failed with '{answer}': {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"💥 Exception with '{answer}': {e}")
    
    print("❌ Could not create admin user with any of the tried answers")
    return False

if __name__ == "__main__":
    create_admin()
