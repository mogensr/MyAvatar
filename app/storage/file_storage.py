"""
File storage module for MyAvatar
Supports both local storage and Cloudinary
"""
import os
import shutil
import uuid
import logging
from fastapi import UploadFile
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

# Use standard Python logging to avoid circular imports
logger = logging.getLogger(__name__)

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
    logger.info("Cloudinary storage is configured")
else:
    logger.info("Cloudinary not configured, using local storage")

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
            logger.info("Cloudinary not available, falling back to local storage")
            return upload_avatar_locally(image_file, user_id)
            
        # Create a temporary file to upload
        file_path = f"temp_{uuid.uuid4()}.{image_file.filename.split('.')[-1]}"
        with open(file_path, "wb") as f:
            f.write(image_file.file.read())
            
        logger.info(f"Uploading avatar for user {user_id} to Cloudinary")
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file_path,
            folder=f"myavatar/avatars/{user_id}",
            public_id=f"avatar_{uuid.uuid4().hex[:8]}",
            overwrite=True
        )
        
        # Remove temporary file
        os.remove(file_path)
        
        logger.info(f"Avatar uploaded to Cloudinary: {result['secure_url']}")
        return result["secure_url"]
    except Exception as e:
        logger.error(f"Failed to upload avatar to Cloudinary: {str(e)}")
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
        
        logger.info(f"Uploading avatar for user {user_id} to local storage")
        
        # Reset file position
        image_file.file.seek(0)
        
        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(image_file.file, f)
            
        logger.info(f"Avatar saved locally at {file_path}")
        return f"/static/uploads/images/{user_id}/{unique_filename}"
    except Exception as e:
        logger.error(f"Failed to save avatar locally: {str(e)}")
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
            logger.info("Cloudinary not available, falling back to local storage")
            return upload_audio_locally(audio_file, user_id)
            
        # Create a temporary file to upload
        file_path = f"temp_{uuid.uuid4()}.{audio_file.filename.split('.')[-1]}"
        with open(file_path, "wb") as f:
            f.write(audio_file.file.read())
            
        logger.info(f"Uploading audio for user {user_id} to Cloudinary")
        
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
        
        logger.info(f"Audio uploaded to Cloudinary: {result['secure_url']}")
        return result["secure_url"]
    except Exception as e:
        logger.error(f"Failed to upload audio to Cloudinary: {str(e)}")
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
        
        logger.info(f"Uploading audio for user {user_id} to local storage")
        
        # Reset file position
        audio_file.file.seek(0)
        
        # Save file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(audio_file.file, f)
            
        logger.info(f"Audio saved locally at {file_path}")
        return f"/static/uploads/audio/{user_id}/{unique_filename}"
    except Exception as e:
        logger.error(f"Failed to save audio locally: {str(e)}")
        raise

def upload_video_to_cloudinary(video_path: str, user_id: int, filename: str = None):
    """
    Upload video file to Cloudinary
    
    Args:
        video_path: Path to the video file (can be temp file)
        user_id: ID of the user
        filename: Original filename (optional)
        
    Returns:
        URL of the uploaded video
    """
    try:
        if not CLOUDINARY_AVAILABLE:
            logger.info("Cloudinary not available, falling back to local storage")
            return upload_video_locally(video_path, user_id, filename)
            
        logger.info(f"🍹 Uploading video for user {user_id} to Cloudinary")
        
        # Generate unique public ID
        unique_id = uuid.uuid4().hex[:8]
        public_id = f"background_fx_{unique_id}"
        
        # Upload to Cloudinary as video
        result = cloudinary.uploader.upload(
            video_path,
            resource_type="video",  # Explicitly set as video
            folder=f"myavatar/videos/{user_id}",
            public_id=public_id,
            overwrite=True,
            eager=[
                {"width": 854, "height": 480, "crop": "scale", "format": "mp4"},  # Standard quality
                {"width": 1280, "height": 720, "crop": "scale", "format": "mp4"}  # HD quality
            ]
        )
        
        video_url = result["secure_url"]
        logger.info(f"🍹 Video uploaded to Cloudinary: {video_url}")
        return video_url
        
    except Exception as e:
        logger.error(f"🍹 Failed to upload video to Cloudinary: {str(e)}")
        # Fallback to local storage
        return upload_video_locally(video_path, user_id, filename)

def upload_video_locally(video_path: str, user_id: int, filename: str = None):
    """
    Upload video file to local storage
    
    Args:
        video_path: Path to the video file 
        user_id: ID of the user
        filename: Original filename (optional)
        
    Returns:
        URL of the uploaded video
    """
    try:
        # Ensure directory exists
        os.makedirs(f"static/uploads/videos/{user_id}", exist_ok=True)
        
        # Generate unique filename
        unique_filename = f"background_fx_{uuid.uuid4().hex[:8]}.mp4"
        local_path = f"static/uploads/videos/{user_id}/{unique_filename}"
        
        logger.info(f"🍹 Uploading video for user {user_id} to local storage")
        
        # Copy file to local storage
        shutil.copy2(video_path, local_path)
            
        video_url = f"/static/uploads/videos/{user_id}/{unique_filename}"
        logger.info(f"🍹 Video saved locally: {video_url}")
        return video_url
        
    except Exception as e:
        logger.error(f"🍹 Failed to save video locally: {str(e)}")
        raise

def upload_video_from_bytes(video_bytes: bytes, user_id: int, filename: str = "background_video.mp4"):
    """
    Upload video from bytes data to Cloudinary
    
    Args:
        video_bytes: Video data as bytes
        user_id: ID of the user
        filename: Filename for the video
        
    Returns:
        URL of the uploaded video
    """
    import tempfile
    
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
            temp_file.write(video_bytes)
            temp_path = temp_file.name
        
        try:
            # Upload using existing function
            video_url = upload_video_to_cloudinary(temp_path, user_id, filename)
            return video_url
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        logger.error(f"🍹 Failed to upload video from bytes: {str(e)}")
        raise