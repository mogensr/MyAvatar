#!/usr/bin/env python3
"""
Reverse fix: Change video_url database column references back to video_path
Since we now know the actual database column is video_path
"""
import os
import re

def reverse_fix_database_column_references():
    """Change video_url database column references back to video_path"""
    
    # Files to check (main application files)
    files_to_check = [
        'app/routes/web_routes.py',
        'app/routes/api_routes.py', 
        'app/db/user_manager.py',
        'working_web_routes.py'
    ]
    
    # Patterns to reverse fix (database column references only)
    patterns_to_fix = [
        # SQL SELECT statements (but keep the alias)
        # We want: SELECT video_path as video_url (not change this)
        
        # SQL UPDATE statements  
        ('UPDATE videos SET video_url', 'UPDATE videos SET video_path'),
        
        # SQL WHERE clauses for database columns
        ('WHERE.*video_url IS NOT NULL', lambda m: m.group(0).replace('video_url', 'video_path')),
        ('WHERE.*video_url !=', lambda m: m.group(0).replace('video_url', 'video_path')),
        
        # SQL AND clauses for database columns
        ('AND video_url IS NOT NULL', 'AND video_path IS NOT NULL'),
        ('AND video_url !=', 'AND video_path !='),
        
        # Dictionary access for database columns (but be careful - we want to keep video_url in the result)
        # Don't change these - they should stay as video_url since we alias the column
    ]
    
    total_fixes = 0
    
    for file_path in files_to_check:
        if not os.path.exists(file_path):
            print(f"⚠️  File not found: {file_path}")
            continue
            
        print(f"\n🔍 Checking {file_path}...")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        file_fixes = 0
        
        for pattern, replacement in patterns_to_fix:
            if callable(replacement):
                # Use regex substitution with function
                matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
                if matches:
                    new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.MULTILINE)
                    if new_content != content:
                        print(f"   ✅ Fixed {len(matches)} instances of: {pattern}")
                        file_fixes += len(matches)
                        content = new_content
            else:
                # Simple string replacement
                if pattern in content:
                    changes = content.count(pattern)
                    new_content = content.replace(pattern, replacement)
                    if new_content != content:
                        print(f"   ✅ Fixed {changes} instances of: {pattern}")
                        file_fixes += changes
                        content = new_content
        
        if content != original_content:
            # Write the fixed content back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"   💾 Saved {file_fixes} fixes to {file_path}")
            total_fixes += file_fixes
        else:
            print(f"   ✅ No database column fixes needed")
    
    print(f"\n🎯 SUMMARY: Fixed {total_fixes} database column references")
    
    if total_fixes > 0:
        print("\n📝 Next steps:")
        print("   1. Test the application")
        print("   2. git add . && git commit -m 'Reverse fix: Use video_path for database operations'")
        print("   3. git push")
    else:
        print("\n✅ All database column references are already correct!")

if __name__ == "__main__":
    reverse_fix_database_column_references()
