"""
Setup script to install specific libraryFX modules for MyAvatar
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

# Available modules in libraryFX
AVAILABLE_MODULES = ["core", "notifications", "billing", "media", "distribution"]

def install_module(module_name):
    """Install a specific libraryFX module"""
    # Path to libraryFX
    library_fx_path = os.path.join(Path.home(), "Projects", "Python", "libraryFX")
    
    if not os.path.exists(library_fx_path):
        print(f"Error: libraryFX not found at {library_fx_path}")
        return False
    
    # Path to the specific module
    module_path = os.path.join(library_fx_path, module_name)
    
    if not os.path.exists(module_path):
        print(f"Error: Module '{module_name}' not found at {module_path}")
        return False
    
    try:
        print(f"Installing libraryFX.{module_name} module from {module_path}...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", module_path],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Successfully installed libraryFX.{module_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing libraryFX.{module_name}: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Install specific libraryFX modules')
    parser.add_argument('modules', nargs='*', default=['core', 'notifications'], 
                        help=f'Modules to install. Available: {", ".join(AVAILABLE_MODULES)}')
    parser.add_argument('--all', action='store_true', help='Install all available modules')
    args = parser.parse_args()
    
    modules_to_install = AVAILABLE_MODULES if args.all else args.modules
    
    print(f"Installing the following libraryFX modules: {', '.join(modules_to_install)}\n")
    
    success_count = 0
    for module in modules_to_install:
        if module in AVAILABLE_MODULES:
            if install_module(module):
                success_count += 1
        else:
            print(f"Warning: Unknown module '{module}'. Skipping.")
    
    if success_count == len(modules_to_install):
        print("\nSetup complete! All requested modules were installed.")
        print("\nYou can now import specific libraries as needed:")
        if "core" in modules_to_install:
            print("  from libraryFX.core.config import load_config")
        if "notifications" in modules_to_install:
            print("  from libraryFX.notifications.alerts import send_alert")
    else:
        print(f"\nPartial setup: {success_count}/{len(modules_to_install)} modules installed.")
        print("Check the error messages above for failed modules.")
        
    return success_count == len(modules_to_install)

if __name__ == "__main__":
    main()
