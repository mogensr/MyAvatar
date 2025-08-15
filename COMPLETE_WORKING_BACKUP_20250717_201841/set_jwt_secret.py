#!/usr/bin/env python
"""
Script to generate a JWT secret key and instructions for setting it
"""
import os
import secrets
import base64

# Generate a secure random key
jwt_secret = secrets.token_urlsafe(32)
print("\n=== JWT SECRET KEY GENERATOR ===")
print(f"\nGenerated JWT Secret Key: {jwt_secret}")
print("\n=== INSTRUCTIONS ===")
print("1. Copy this key and set it as an environment variable in your deployment platform")
print("2. For Railway, go to Settings -> Environment Variables")
print("3. Add a new variable with key: JWT_SECRET_KEY and the generated value")
print("4. Redeploy your application after setting this variable")
print("\nThis will ensure your JWT tokens remain valid between application restarts.")
