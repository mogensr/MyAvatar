import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import os

load_dotenv()

# Upload test audio
result = cloudinary.uploader.upload(
    "test_audio.m4a",
    resource_type="video",
    folder="audio"
)

print(f"Cloudinary URL: {result['secure_url']}")
