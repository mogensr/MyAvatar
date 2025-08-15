import shutil
import os
from datetime import datetime

# Create backup folder with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_folder = f"COMPLETE_WORKING_BACKUP_{timestamp}"
os.makedirs(backup_folder)

print("🔄 Creating complete backup of working system...")

# Backup the entire project (excluding certain folders)
exclude_folders = {
    '__pycache__', 
    '.git', 
    'node_modules', 
    '.venv', 
    'venv',
    '.railway',
    'logs'
}

exclude_files = {
    '.env',
    '.gitignore',
    'backup_working_system.py'
}

# Walk through all files and folders
for root, dirs, files in os.walk('.'):
    # Skip excluded directories
    dirs[:] = [d for d in dirs if d not in exclude_folders]
    
    for file in files:
        if file not in exclude_files:
            # Get the full path
            file_path = os.path.join(root, file)
            
            # Create the backup path
            relative_path = os.path.relpath(file_path, '.')
            backup_path = os.path.join(backup_folder, relative_path)
            
            # Create directories if needed
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Copy the file
            try:
                shutil.copy2(file_path, backup_path)
                print(f"✅ {relative_path}")
            except Exception as e:
                print(f"⚠️ Skipped {relative_path}: {e}")

print(f"\n🎉 COMPLETE BACKUP FINISHED!")
print(f"📁 Backup location: {backup_folder}")
print(f"💾 All your working files are safe!")
