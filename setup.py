import subprocess
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# List of requirements from the app.py script
requirements = [
    "torch>=2.0.0",
    "torchvision>=0.15.0",
    "opencv-python>=4.8.0",
    "pillow>=9.0.0",
    "numpy>=1.21.0",
    "scipy>=1.9.0",
    "scikit-image>=0.19.0",
    "matplotlib>=3.5.0",
    "gradio>=4.0.0",
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "python-multipart>=0.0.6",
    "requests>=2.28.0",
    "cloudinary>=1.34.0",
    "librosa>=0.10.0",
    "soundfile>=0.12.0",
    "psutil>=5.9.0",
    "python-dotenv>=1.0.0",
    "passlib[bcrypt]>=1.7.4",
    "python-jose[cryptography]>=3.3.0",
    "psycopg2-binary>=2.9.0",
    "gradio-client>=0.6.0"
]

def install_packages():
    """Install all required Python packages."""
    logging.info("🐍 Starting installation of Python requirements...")
    for req in requirements:
        try:
            logging.info(f"Installing {req}...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", req, "--quiet"
            ])
            logging.info(f"✅ Successfully installed {req}")
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Failed to install {req}: {e}")
            # Decide if you want to exit on failure
            # sys.exit(1)

    logging.info("✅ All Python requirements are installed.")

if __name__ == "__main__":
    install_packages()
