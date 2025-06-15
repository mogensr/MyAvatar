import os
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import tempfile

# Indlæs miljøvariabler
load_dotenv()

# Konfigurer Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Lav en test-fil (denne gang simulerer vi en lydfil)
with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp:
    temp.write(b"Dette er en test")
    temp_file_path = temp.name

print(f"Test fil oprettet: {temp_file_path}")

# Test upload med resource_type="auto" 
try:
    result = cloudinary.uploader.upload(
        temp_file_path, 
        resource_type="auto"  # Vigtigt! Specifiker resource_type
    )
    print(f"Upload succesfuld! URL: {result['secure_url']}")
except Exception as e:
    print(f"Upload fejl: {e}")

# Opryd
os.unlink(temp_file_path)
