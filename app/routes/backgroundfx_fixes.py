"""
BACKGROUNDFX FIXES - IMPROVED FILE SAVING
========================================
Enhanced functions to fix the file saving issues in backgroundfx_routes.py

Author: Cascade AI
Date: July 25, 2025
"""

import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import time

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")

def execute_query_with_retry(query: str, params=(), fetch_one=False, fetch_all=False, max_retries=3):
    """Execute database query with retry logic and better error handling"""
    for attempt in range(max_retries):
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            logger.info(f"🔄 Database query attempt {attempt + 1}: {query[:100]}...")
            cur.execute(query, params)
            
            if fetch_one:
                result = cur.fetchone()
            elif fetch_all:
                result = cur.fetchall()
            else:
                result = None
                
            conn.commit()
            logger.info(f"✅ Database query successful on attempt {attempt + 1}")
            return result
            
        except psycopg2.Error as e:
            logger.error(f"❌ Database error on attempt {attempt + 1}: {e}")
            if conn:
                conn.rollback()
            if attempt == max_retries - 1:
                raise
            time.sleep(1)  # Wait before retry
            
        except Exception as e:
            logger.error(f"❌ Unexpected error on attempt {attempt + 1}: {e}")
            if conn:
                conn.rollback()
            raise
            
        finally:
            if conn:
                conn.close()
    
    return None


def get_videos_table_schema():
    """Get the actual schema of the videos table to understand required fields"""
    try:
        schema_query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'videos' 
        ORDER BY ordinal_position;
        """
        
        columns = execute_query_with_retry(schema_query, fetch_all=True)
        
        if columns:
            logger.info("📋 Videos table schema:")
            for col in columns:
                logger.info(f"   {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
            return {col['column_name']: col for col in columns}
        else:
            logger.warning("⚠️ Could not retrieve videos table schema")
            return {}
            
    except Exception as e:
        logger.error(f"❌ Error getting table schema: {e}")
        return {}


def save_processed_video_to_database_improved(user_id, cloudinary_url, job_id, video_title=None):
    """
    IMPROVED: Save processed video with comprehensive error handling and field validation
    """
    try:
        logger.info(f"💾 IMPROVED SAVE: Starting save process...")
        logger.info(f"💾 User ID: {user_id}")
        logger.info(f"💾 Cloudinary URL: {cloudinary_url}")
        logger.info(f"💾 Job ID: {job_id}")
        
        # Get table schema to understand what fields are required
        schema = get_videos_table_schema()
        
        # Prepare video data with all potentially required fields
        video_data = {
            'user_id': user_id,
            'title': video_title or f"BackgroundFX Cinema-Quality Video {job_id}",
            'video_path': cloudinary_url,
            'input_url': job_id,  # Store job_id for reference
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        # Add optional fields that might be required (with safe defaults)
        optional_fields = {
            'avatar_id': 'backgroundfx',  # Safe default for background replacement
            'heygen_avatar_id': 'backgroundfx',
            'voice_id': None,
            'script': 'Background replacement video',
            'status': 'completed',
            'processing_status': 'completed',
            'duration': None,
            'file_size': None,
            'thumbnail_url': None,
            'is_public': False,
            'is_featured': False
        }
        
        # Only add optional fields if they exist in the schema
        for field, default_value in optional_fields.items():
            if field in schema:
                video_data[field] = default_value
                logger.info(f"💾 Added optional field {field}: {default_value}")
        
        # Build dynamic INSERT query based on available data
        fields = list(video_data.keys())
        placeholders = ', '.join(['%s'] * len(fields))
        field_names = ', '.join(fields)
        values = [video_data[field] for field in fields]
        
        insert_query = f"""
        INSERT INTO videos ({field_names}) 
        VALUES ({placeholders}) 
        RETURNING id, title, video_path
        """
        
        logger.info(f"💾 Executing INSERT query with {len(fields)} fields")
        logger.info(f"💾 Fields: {fields}")
        
        # Execute the insert
        result = execute_query_with_retry(insert_query, tuple(values), fetch_one=True)
        
        if result:
            video_id = result['id']
            logger.info(f"✅ SUCCESS! Video saved with ID: {video_id}")
            logger.info(f"✅ Title: {result['title']}")
            logger.info(f"✅ Video Path: {result['video_path']}")
            
            # Verify the save by querying back
            verify_query = "SELECT id, title, video_path, user_id FROM videos WHERE id = %s"
            verification = execute_query_with_retry(verify_query, (video_id,), fetch_one=True)
            
            if verification:
                logger.info(f"✅ VERIFICATION: Video {video_id} confirmed in database")
                return video_id
            else:
                logger.error(f"❌ VERIFICATION FAILED: Video {video_id} not found after insert")
                return None
        else:
            logger.error("❌ INSERT returned no result")
            return None
            
    except psycopg2.IntegrityError as e:
        logger.error(f"💾 INTEGRITY ERROR: {e}")
        logger.error("💾 This usually means a required field is missing or a constraint is violated")
        
        # Try to identify the specific constraint issue
        error_msg = str(e).lower()
        if 'not null' in error_msg:
            logger.error("💾 Likely cause: Required field is NULL")
        elif 'foreign key' in error_msg:
            logger.error("💾 Likely cause: Foreign key constraint violation")
        elif 'unique' in error_msg:
            logger.error("💾 Likely cause: Duplicate value in unique field")
        
        return None
        
    except Exception as e:
        logger.error(f"💾 GENERAL ERROR: {str(e)}")
        logger.error(f"💾 Error type: {type(e)}")
        import traceback
        logger.error(f"💾 Traceback: {traceback.format_exc()}")
        return None


def validate_hf_space_result(result):
    """Validate and normalize HF Space processing result"""
    try:
        logger.info(f"🔍 VALIDATING HF RESULT: {type(result)}")
        logger.info(f"🔍 Result content: {result}")
        
        if not result:
            return None, "No result returned from HF Space"
        
        # Handle different result formats
        if isinstance(result, (list, tuple)):
            if len(result) >= 2:
                output_path, status = result[0], result[1]
                
                # Validate output path
                if not output_path:
                    return None, "No output path in result"
                
                if isinstance(output_path, str) and not os.path.exists(output_path):
                    return None, f"Output file does not exist: {output_path}"
                
                # Validate status
                status_str = str(status).upper()
                success_indicators = ["COMPLETE", "SUCCESS", "FINISHED", "DONE"]
                
                if any(indicator in status_str for indicator in success_indicators):
                    logger.info(f"✅ HF Space result validated: {output_path}")
                    return output_path, "Processing completed successfully"
                else:
                    return None, f"Processing not completed: {status}"
            else:
                return None, f"Unexpected result format: expected 2+ items, got {len(result)}"
        
        elif isinstance(result, dict):
            # Handle dictionary result format
            output_path = result.get('output_path') or result.get('video_path') or result.get('result')
            status = result.get('status') or result.get('message', 'unknown')
            
            if output_path and os.path.exists(output_path):
                return output_path, str(status)
            else:
                return None, f"Invalid output path in dict result: {output_path}"
        
        else:
            return None, f"Unsupported result type: {type(result)}"
            
    except Exception as e:
        logger.error(f"❌ Error validating HF result: {e}")
        return None, f"Validation error: {str(e)}"


def upload_to_cloudinary_with_retry(video_content, job_id, max_retries=3):
    """Upload video to Cloudinary with retry logic and better error handling"""
    try:
        import cloudinary
        import cloudinary.uploader
        
        logger.info(f"☁️ CLOUDINARY UPLOAD: Starting upload for job {job_id}")
        logger.info(f"☁️ Video size: {len(video_content)} bytes ({len(video_content) / 1024 / 1024:.2f} MB)")
        
        # Check file size limits (Cloudinary free tier has limits)
        max_size_mb = 100  # Adjust based on your Cloudinary plan
        size_mb = len(video_content) / 1024 / 1024
        
        if size_mb > max_size_mb:
            logger.warning(f"⚠️ Video size ({size_mb:.2f} MB) exceeds recommended limit ({max_size_mb} MB)")
        
        for attempt in range(max_retries):
            try:
                logger.info(f"☁️ Upload attempt {attempt + 1}/{max_retries}")
                
                upload_result = cloudinary.uploader.upload(
                    video_content,
                    resource_type="video",
                    public_id=f"myavatar/processed/{job_id}",
                    folder="myavatar/processed",
                    timeout=120,  # Increase timeout for large files
                    chunk_size=6000000,  # 6MB chunks for better reliability
                    use_filename=True,
                    overwrite=True
                )
                
                cloudinary_url = upload_result.get("secure_url")
                
                if cloudinary_url:
                    logger.info(f"✅ CLOUDINARY SUCCESS: {cloudinary_url}")
                    logger.info(f"✅ Upload details: {upload_result.get('bytes', 0)} bytes, format: {upload_result.get('format', 'unknown')}")
                    return cloudinary_url
                else:
                    logger.error(f"❌ No secure_url in upload result: {upload_result}")
                    
            except Exception as e:
                logger.error(f"❌ Cloudinary upload attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Cloudinary upload completely failed: {e}")
        return None


def process_hf_space_result_improved(result, user_id, job_id):
    """
    IMPROVED: Process HF Space result with comprehensive validation and error handling
    """
    try:
        logger.info("🎬 IMPROVED HF PROCESSING: Starting result processing...")
        
        # Step 1: Validate HF Space result
        output_video_path, status_message = validate_hf_space_result(result)
        
        if not output_video_path:
            logger.error(f"❌ HF Space validation failed: {status_message}")
            return {
                "success": False,
                "error": f"HF Space processing failed: {status_message}"
            }
        
        logger.info(f"✅ HF Space result validated: {output_video_path}")
        
        # Step 2: Verify file exists and get info
        if not os.path.exists(output_video_path):
            logger.error(f"❌ Output file does not exist: {output_video_path}")
            return {
                "success": False,
                "error": "Output video file not found"
            }
        
        file_size = os.path.getsize(output_video_path)
        logger.info(f"📁 Output file size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        if file_size == 0:
            logger.error("❌ Output file is empty")
            return {
                "success": False,
                "error": "Output video file is empty"
            }
        
        # Step 3: Read video content
        try:
            with open(output_video_path, 'rb') as f:
                video_content = f.read()
            logger.info(f"✅ Video content read successfully: {len(video_content)} bytes")
        except Exception as e:
            logger.error(f"❌ Failed to read video file: {e}")
            return {
                "success": False,
                "error": f"Failed to read video file: {str(e)}"
            }
        
        # Step 4: Upload to Cloudinary with retry
        cloudinary_url = upload_to_cloudinary_with_retry(video_content, job_id)
        
        if not cloudinary_url:
            logger.error("❌ Cloudinary upload failed")
            return {
                "success": False,
                "error": "Failed to upload to cloud storage"
            }
        
        # Step 5: Save to database with improved function
        video_title = f"BackgroundFX Cinema-Quality Video {job_id}"
        video_id = save_processed_video_to_database_improved(user_id, cloudinary_url, job_id, video_title)
        
        if video_id:
            logger.info(f"✅ COMPLETE SUCCESS! Video saved with ID: {video_id}")
            return {
                "success": True,
                "job_id": job_id,
                "status": "completed",
                "message": "Video processed and saved successfully",
                "output_url": cloudinary_url,
                "video_id": video_id,
                "file_size": file_size
            }
        else:
            logger.error("❌ Database save failed")
            return {
                "success": False,
                "error": "Failed to save video to database"
            }
            
    except Exception as e:
        logger.error(f"❌ PROCESSING ERROR: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": f"Processing failed: {str(e)}"
        }


# Test function to validate the fixes
def test_database_connection():
    """Test database connection and table structure"""
    try:
        logger.info("🧪 TESTING: Database connection...")
        
        # Test basic connection
        test_query = "SELECT version();"
        result = execute_query_with_retry(test_query, fetch_one=True)
        
        if result:
            logger.info(f"✅ Database connected: {result}")
        
        # Test videos table structure
        schema = get_videos_table_schema()
        logger.info(f"✅ Videos table has {len(schema)} columns")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False


if __name__ == "__main__":
    # Run tests
    test_database_connection()
