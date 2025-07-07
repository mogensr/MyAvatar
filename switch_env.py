#!/usr/bin/env python3
"""
Environment switcher for MyAvatar project
"""
import shutil
import os
import sys

def switch_environment(env):
    """Switch between development and production environments"""
    
    if env not in ['dev', 'prod', 'development', 'production']:
        print("❌ Invalid environment. Use: dev, prod, development, or production")
        return False
    
    # Normalize environment names
    if env in ['dev', 'development']:
        env_file = '.env.development'
        env_name = 'DEVELOPMENT'
    else:
        env_file = '.env.production'
        env_name = 'PRODUCTION'
    
    source_file = env_file
    target_file = '.env'
    
    if not os.path.exists(source_file):
        print(f"❌ {source_file} not found!")
        return False
    
    try:
        # Copy the environment file to .env
        shutil.copy2(source_file, target_file)
        print(f"🔄 Switched to {env_name} environment")
        print(f"✅ Copied {source_file} → {target_file}")
        
        # Show current database
        with open(target_file, 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    db_url = line.strip().split('=', 1)[1]
                    if 'caboose' in db_url:
                        print("🔗 Using: Railway DEV database")
                    elif 'crossover' in db_url:
                        print("🔗 Using: Railway PROD database")
                    break
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to switch environment: {e}")
        return False

def show_current_env():
    """Show current environment"""
    if not os.path.exists('.env'):
        print("❌ No .env file found")
        return
    
    with open('.env', 'r') as f:
        for line in f:
            if line.startswith('DATABASE_URL='):
                db_url = line.strip().split('=', 1)[1]
                if 'caboose' in db_url:
                    print("📍 Current: DEVELOPMENT environment (Railway DEV)")
                elif 'crossover' in db_url:
                    print("📍 Current: PRODUCTION environment (Railway PROD)")
                else:
                    print("📍 Current: Unknown environment")
                break

if __name__ == "__main__":
    print("🔄 MyAvatar Environment Switcher")
    print("=" * 40)
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python switch_env.py dev     # Switch to development")
        print("  python switch_env.py prod    # Switch to production")
        print("  python switch_env.py status  # Show current environment")
        print()
        show_current_env()
    elif sys.argv[1] == 'status':
        show_current_env()
    else:
        switch_environment(sys.argv[1])
