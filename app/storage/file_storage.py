"""
File storage module for MyAvatar
Supports both local storage and Cloudinary
"""
import os
import shutil
import uuid
from fastapi import UploadFile
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from ..logger.log_handler import log_info, log_error

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# Check if Cloudinary is properly configured
CLOUDINARY_AVAILABLE = all([
    os.getenv("CLOUDINARY_CLOUD_NAME"),
    os.getenv("CLOUDINARY_API_KEY"),
    os.getenv("CLOUDINARY_API_SECRET")
])

if CLOUDINARY_AVAILABLE:
    log_info("Cloudinary storage is configured", "Storage")
else:
    log_info("Cloudinary not configured, using local storage", "Storage")

def upload_avatar_to_cloudinary(image_file: UploadFile, user_id: int):
    """
    Upload avatar image to Cloudinary
    
    Args:
        image_file: Image file to upload
        user_id: ID of the user
        
    Returns:
        URL of the uploaded image
    """
    try:
        if not CLOUDINARY_AVAILABLE:
            log_info("Cloudinary not available, falling back to local storage", "Storage")
            return upload_avatar_locally(image_file, user_id)
            
        # Create a temporary file to upload
        file_path = f"temp_{uuid.uuid4()}.{image_file.filename.split('.')[-1]}"
        with open(file_path, "wb") as f:
            f.write(image_file.file.read())
            
        log_info(f"Uploading avatar for user {user_id} to Cloudinary", "Storage")
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file_path,
            folder=f"myavatar/avatars/{user_id}",
            public_id=f"avatar_{uuid.uuid4().hex[:8]}",
            overwrite=True
        )
        
        # Remove temporary file
        os.remove(file_path)
        
        log_info(f"Avatar uploaded to Cloudinary: {result['secure_url']}", "Storage")
        return result["secure_url"]
    except Exception as e:
        log_error(f"Failed to upload avatar to Cloudinary", "Storage", e)
        # Fallback to local storage
        return upload_avatar_locally(image_file, user_id)

def upload_avatar_locally(image_file: UploadFile, user_id: int):
    """
    Upload avatar image to local storage
    
    Args:
        image_file: Image file to upload
        user_id: ID of the user
        
    Returns:
        URL of the uploaded image
    """
    try:
        # Ensure directory exists
        os.makedirs(f"static/uploads/images/{user_id}", exist_ok=True)
        
        # Generate unique filename
        file_extension = image_file.filename.split(".")[-1]
        unique_filename = f"avatar_{uuid.uuid4().hex[:8]}.{file_extension}"
        file_path = f"static/uploads/images/{user_id}/{unique_filename}"
        
        log_info(f"Uploading avatar for user {user_id} to local storage", "Storage")
        
        # Reset file position
        image_file.file.seek(0)
        
        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(image_file.file, f)
            
        log_info(f"Avatar saved locally at {file_path}", "Storage")
        return f"/static/uploads/images/{user_id}/{unique_filename}"
    except Exception as e:
        log_error(f"Failed to save avatar locally", "Storage", e)
        raise

def upload_audio_to_cloudinary(audio_file: UploadFile, user_id: int):
    """
    Upload audio file to Cloudinary
    
    Args:
        audio_file: Audio file to upload
        user_id: ID of the user
        
    Returns:
        URL of the uploaded audio
    """
    try:
        if not CLOUDINARY_AVAILABLE:
            log_info("Cloudinary not available, falling back to local storage", "Storage")
            return upload_audio_locally(audio_file, user_id)
            
        # Create a temporary file to upload
        file_path = f"temp_{uuid.uuid4()}.{audio_file.filename.split('.')[-1]}"
        with open(file_path, "wb") as f:
            f.write(audio_file.file.read())
            
        log_info(f"Uploading audio for user {user_id} to Cloudinary", "Storage")
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file_path,
            resource_type="auto",  # Let Cloudinary detect resource type
            folder=f"myavatar/audio/{user_id}",
            public_id=f"audio_{uuid.uuid4().hex[:8]}",
            overwrite=True
        )
        
        # Remove temporary file
        os.remove(file_path)
        
        log_info(f"Audio uploaded to Cloudinary: {result['secure_url']}", "Storage")
        return result["secure_url"]
    except Exception as e:
        log_error(f"Failed to upload audio to Cloudinary", "Storage", e)
        # Fallback to local storage
        return upload_audio_locally(audio_file, user_id)

def upload_audio_locally(audio_file: UploadFile, user_id: int):
    """
    Upload audio file to local storage
    
    Args:
        audio_file: Audio file to upload
        user_id: ID of the user
        
    Returns:
        URL of the uploaded audio
    """
    try:
        # Ensure directory exists
        os.makedirs(f"static/uploads/audio/{user_id}", exist_ok=True)
        
        # Generate unique filename
        file_extension = audio_file.filename.split(".")[-1]
        unique_filename = f"audio_{uuid.uuid4().hex[:8]}.{file_extension}"
        file_path = f"static/uploads/audio/{user_id}/{unique_filename}"
        
        log_info(f"Uploading audio for user {user_id} to local storage", "Storage")
        
        # Reset file position
        audio_file.file.seek(0)
        
        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(audio_file.file, f)
            
        log_info(f"Audio saved locally at {file_path}", "Storage")
        return f"/static/uploads/audio/{user_id}/{unique_filename}"
    except Exception as e:
        log_error(f"Failed to save audio locally", "Storage", e)
        raise
