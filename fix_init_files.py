#!/usr/bin/env python3
"""
Fix all __init__.py files with indentation errors
"""
import os
import glob

def fix_init_files():
    """Find and fix all __init__.py files with indentation issues"""
    
    # Find all __init__.py files in the project
    init_files = glob.glob("**/__init__.py", recursive=True)
    
    print(f"Found {len(init_files)} __init__.py files")
    
    for file_path in init_files:
        # Skip venv and backup directories
        if 'venv' in file_path or 'BACKUP' in file_path:
            continue
            
        print(f"Checking: {file_path}")
        
        try:
            # Read the file
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Check if file starts with whitespace/indentation
            if content.startswith(b' ') or content.startswith(b'\t'):
                print(f"  ❌ FIXING: {file_path} - starts with whitespace")
                
                # Write clean content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("# Package init file\n")
                    
            elif len(content.strip()) == 0:
                print(f"  ✅ FIXING: {file_path} - empty file")
                
                # Write clean content  
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("# Package init file\n")
                    
            else:
                print(f"  ✅ OK: {file_path}")
                
        except Exception as e:
            print(f"  ❌ ERROR: {file_path} - {e}")

if __name__ == "__main__":
    print("🔧 Fixing all __init__.py files...")
    fix_init_files()
    print("✅ Done!")
