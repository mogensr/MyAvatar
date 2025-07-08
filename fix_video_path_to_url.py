#!/usr/bin/env python3
"""
Smart fix for video_path -> video_url database column references
Only fixes database column references, not file path variables
"""
import os
import re

def fix_database_column_references():
    """Fix video_path database column references to video_url"""
    
    # Files to check (main application files)
    files_to_check = [
        'app/routes/web_routes.py',
        'app/routes/api_routes.py', 
        'app/db/user_manager.py',
        'working_web_routes.py'
    ]
    
    # Patterns to fix (database column references only)
    patterns_to_fix = [
        # SQL SELECT statements
        (r'SELECT.*?video_path', lambda m: m.group(0).replace('video_path', 'video_url')),
        # SQL UPDATE statements  
        (r'UPDATE videos SET video_path', 'UPDATE videos SET video_url'),
        # SQL WHERE clauses
        (r'WHERE.*?video_path', lambda m: m.group(0).replace('video_path', 'video_url')),
        # SQL AND clauses
        (r'AND video_path', 'AND video_url'),
        # Dictionary access for database columns
        (r"video\.get\('video_path'\)", "video.get('video_url')"),
        (r'video_dict\.get\(\'video_path\'\)', 'video_dict.get(\'video_url\')'),
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
                new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.MULTILINE)
            else:
                # Simple string replacement
                new_content = content.replace(pattern, replacement)
            
            if new_content != content:
                changes = content.count(pattern) if not callable(replacement) else len(re.findall(pattern, content, re.IGNORECASE | re.MULTILINE))
                if changes > 0:
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
        print("   2. git add . && git commit -m 'Fix video_path database column references'")
        print("   3. git push")
    else:
        print("\n✅ All database column references are already correct!")

if __name__ == "__main__":
    fix_database_column_references()
