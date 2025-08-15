#!/usr/bin/env python3
import datetime

# The expiry timestamp from your video URL
expires_timestamp = 1752577369

# Convert to readable date
expiry_date = datetime.datetime.fromtimestamp(expires_timestamp)
current_date = datetime.datetime.now()

print(f"URL expires on: {expiry_date}")
print(f"Current time:   {current_date}")
print(f"URL is {'EXPIRED' if current_date > expiry_date else 'VALID'}")

if current_date > expiry_date:
    print("\n❌ The video URLs in your database are EXPIRED!")
    print("   This is why you get 'Access Denied' errors.")
    print("   We need to refresh them using HeyGen API.")
else:
    print("\n✅ URLs should still be valid.")
