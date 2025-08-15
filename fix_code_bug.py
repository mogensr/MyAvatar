#!/usr/bin/env python3
"""
Fix the video_path bug in api_routes.py

Replace all instances of 'UPDATE videos SET video_path' with 'UPDATE videos SET video_url'
"""

import os

def main():
    """Main function"""
    api_file = "app/routes/api_routes.py"
    
    if not os.path.exists(api_file):
        print(f"ERROR: File not found: {api_file}")
        return
    
    # Read the file
    with open(api_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count instances before fix
    before_count = content.count('UPDATE videos SET video_path')
    print(f"Found {before_count} instances of 'UPDATE videos SET video_path'")
    
    if before_count == 0:
        print("No instances found - bug may already be fixed!")
        return
    
    # Replace all instances
    fixed_content = content.replace(
        'UPDATE videos SET video_path',
        'UPDATE videos SET video_url'
    )
    
    # Count instances after fix
    after_count = fixed_content.count('UPDATE videos SET video_path')
    fixed_count = before_count - after_count
    
    # Write the fixed content back
    with open(api_file, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"SUCCESS: Fixed {fixed_count} instances")
    print(f"Remaining instances: {after_count}")
    
    if after_count == 0:
        print("✅ All instances of the bug have been fixed!")
    else:
        print("⚠️  Some instances may still remain")

if __name__ == "__main__":
    main()
