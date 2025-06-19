"""
GDPR compliance module for MyAvatar
Handles user consent, data access, data export, and account deletion functionalities
"""

import os
import json
import zipfile
import io
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Request
from ..db.database import execute_query
from ..logger.log_handler import log_info, log_error

# GDPR Consent text with MyAvatar specific terms
GDPR_CONSENT_TEXT = """
# Privacy Policy and Data Usage Consent - MyAvatar.dk

## Information We Collect
MyAvatar.dk (operated by Rye Outsourcing) collects the following personal information:
- Name and email address
- User preferences and settings
- Avatar images and video content you create
- Voice recordings and audio files you upload
- Usage analytics and activity logs
- IP address and browser information

## How We Use Your Information
- To authenticate you and provide access to the MyAvatar platform
- To create AI-generated videos using your uploaded content
- To store and manage your avatar and video creations
- To personalize your experience and improve our services
- To communicate with you about account-related matters
- To process your content through third-party AI services (HeyGen)

## Third-Party Services
Your content may be processed by:
- HeyGen (AI video generation service)
- Cloudinary (media storage and processing)
- Other AI and media processing services as required

## Content Liability Disclaimer
**IMPORTANT**: By using MyAvatar.dk, you acknowledge and agree that:
- **NO ENTITY OF RYE OUTSOURCING, INCLUDING MYAVATAR.DK, ACCEPTS ANY RESPONSIBILITY FOR CONTENT BEING PRODUCED**
- You are solely responsible for all content you create, upload, or generate using our platform
- You must ensure you have proper rights and permissions for any content you use
- You must comply with all applicable laws regarding the content you create
- Rye Outsourcing and MyAvatar.dk disclaim all liability for user-generated content

## Your Rights Under GDPR
You have the right to:
- Access your personal data
- Correct inaccurate data
- Delete your personal data ("right to be forgotten")
- Export your data in a machine-readable format
- Withdraw consent at any time
- Object to processing of your data

## Data Storage and Security
All personal data is stored securely with appropriate technical and organizational measures to protect against unauthorized processing, loss, or damage. Data may be stored in the EU and other jurisdictions as required for service delivery.

## Data Retention
We retain your personal data only for as long as necessary to fulfill the purposes for which it was collected, or as required by law.

## Contact Information
For privacy-related questions or requests, contact us at: privacy@myavatar.dk

**By clicking "I Accept and Consent", you acknowledge that you have read and understood this privacy policy and content liability disclaimer, and consent to the collection and processing of your personal data as described.**
"""

def store_user_consent(user_id: int, email: str, consent_given: bool = False, 
                      ip_address: str = None, user_agent: str = None) -> bool:
    """Store user's GDPR consent status in database"""
    try:
        # Update user table
        execute_query(
            """
            UPDATE users 
            SET gdpr_consent_given = ?, gdpr_consent_timestamp = ?, gdpr_consent_version = ?
            WHERE id = ?
            """,
            (consent_given, datetime.utcnow().isoformat(), "1.0", user_id)
        )
        
        # Log consent action
        execute_query(
            """
            INSERT INTO gdpr_consent_log 
            (user_id, email, consent_given, consent_version, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, email, consent_given, "1.0", ip_address, user_agent)
        )
        
        log_info(f"GDPR consent stored for user {email}: {consent_given}", "GDPR")
        return True
        
    except Exception as e:
        log_error(f"Error storing GDPR consent for {email}: {e}", "GDPR", e)
        return False

def has_user_given_consent(user_id: int) -> bool:
    """Check if user has given GDPR consent"""
    try:
        result = execute_query(
            "SELECT gdpr_consent_given FROM users WHERE id = ?",
            (user_id,),
            fetch_one=True
        )
        return result.get("gdpr_consent_given", False) if result else False
    except Exception as e:
        log_error(f"Error checking GDPR consent for user {user_id}: {e}", "GDPR", e)
        return False

def get_user_consent_data(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user's consent data"""
    try:
        result = execute_query(
            """
            SELECT gdpr_consent_given, gdpr_consent_timestamp, gdpr_consent_version
            FROM users WHERE id = ?
            """,
            (user_id,),
            fetch_one=True
        )
        return result if result else None
    except Exception as e:
        log_error(f"Error getting consent data for user {user_id}: {e}", "GDPR", e)
        return None

def export_user_data(user_id: int) -> bytes:
    """Export all user data as ZIP file"""
    try:
        # Get user data
        user_data = execute_query(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
            fetch_one=True
        )
        
        if not user_data:
            raise ValueError("User not found")
        
        # Get user's videos
        videos = execute_query(
            "SELECT * FROM videos WHERE user_id = ?",
            (user_id,),
            fetch_all=True
        )
        
        # Get user's avatars
        avatars = execute_query(
            "SELECT * FROM avatars WHERE user_id = ?",
            (user_id,),
            fetch_all=True
        )
        
        # Get consent log
        consent_log = execute_query(
            "SELECT * FROM gdpr_consent_log WHERE user_id = ?",
            (user_id,),
            fetch_all=True
        )
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add user profile
            user_profile = dict(user_data)
            # Remove sensitive data
            user_profile.pop('hashed_password', None)
            zip_file.writestr('user_profile.json', json.dumps(user_profile, indent=4, default=str))
            
            # Add videos data
            if videos:
                videos_data = [dict(video) for video in videos]
                zip_file.writestr('videos.json', json.dumps(videos_data, indent=4, default=str))
            
            # Add avatars data
            if avatars:
                avatars_data = [dict(avatar) for avatar in avatars]
                zip_file.writestr('avatars.json', json.dumps(avatars_data, indent=4, default=str))
            
            # Add consent log
            if consent_log:
                consent_data = [dict(log) for log in consent_log]
                zip_file.writestr('consent_log.json', json.dumps(consent_data, indent=4, default=str))
            
            # Add README
            readme_text = f"""
MyAvatar.dk Data Export
Generated on: {datetime.utcnow().isoformat()}
User: {user_data.get('email', 'Unknown')}

This archive contains all personal data associated with your MyAvatar account:
- user_profile.json: Your account information
- videos.json: Your created videos and metadata
- avatars.json: Your avatar information
- consent_log.json: Your GDPR consent history

If you have any questions about this data, please contact privacy@myavatar.dk
"""
            zip_file.writestr('README.txt', readme_text)
        
        zip_buffer.seek(0)
        return zip_buffer.read()
        
    except Exception as e:
        log_error(f"Error exporting user data for user {user_id}: {e}", "GDPR", e)
        raise

def delete_user_account(user_id: int, admin_user_id: Optional[int] = None) -> bool:
    """Delete user account and all associated data (GDPR right to be forgotten)"""
    try:
        # Get user info before deletion
        user_data = execute_query(
            "SELECT email FROM users WHERE id = ?",
            (user_id,),
            fetch_one=True
        )
        
        if not user_data:
            return False
        
        email = user_data['email']
        
        # Log the deletion before actually deleting
        execute_query(
            """
            INSERT INTO account_deletion_log (email, user_id, admin_user_id)
            VALUES (?, ?, ?)
            """,
            (email, user_id, admin_user_id)
        )
        
        # Delete user's videos (cascade should handle this, but being explicit)
        execute_query("DELETE FROM videos WHERE user_id = ?", (user_id,))
        
        # Delete user's avatars (cascade should handle this, but being explicit)
        execute_query("DELETE FROM avatars WHERE user_id = ?", (user_id,))
        
        # Delete GDPR consent log (cascade should handle this, but being explicit)
        execute_query("DELETE FROM gdpr_consent_log WHERE user_id = ?", (user_id,))
        
        # Finally delete the user
        execute_query("DELETE FROM users WHERE id = ?", (user_id,))
        
        log_info(f"User account deleted: {email} (ID: {user_id})", "GDPR")
        return True
        
    except Exception as e:
        log_error(f"Error deleting user account {user_id}: {e}", "GDPR", e)
        return False

def get_consent_statistics() -> Dict[str, Any]:
    """Get GDPR consent statistics for admin dashboard"""
    try:
        # Total users
        total_users = execute_query(
            "SELECT COUNT(*) as count FROM users",
            fetch_one=True
        )['count']
        
        # Users with consent
        consented_users = execute_query(
            "SELECT COUNT(*) as count FROM users WHERE gdpr_consent_given = true",
            fetch_one=True
        )['count']
        
        # Recent consent actions (last 30 days)
        recent_consents = execute_query(
            """
            SELECT COUNT(*) as count FROM gdpr_consent_log 
            WHERE consent_timestamp > NOW() - INTERVAL '30 days'
            """,
            fetch_one=True
        )['count']
        
        consent_rate = (consented_users / total_users * 100) if total_users > 0 else 0
        
        return {
            'total_users': total_users,
            'consented_users': consented_users,
            'consent_rate': round(consent_rate, 1),
            'recent_consents': recent_consents
        }
        
    except Exception as e:
        log_error(f"Error getting consent statistics: {e}", "GDPR", e)
        return {
            'total_users': 0,
            'consented_users': 0,
            'consent_rate': 0,
            'recent_consents': 0
        }

def get_users_without_consent() -> list:
    """Get list of users who haven't given GDPR consent"""
    try:
        users = execute_query(
            """
            SELECT id, username, email, created_at 
            FROM users 
            WHERE gdpr_consent_given = false OR gdpr_consent_given IS NULL
            ORDER BY created_at DESC
            """,
            fetch_all=True
        )
        return [dict(user) for user in users] if users else []
    except Exception as e:
        log_error(f"Error getting users without consent: {e}", "GDPR", e)
        return []

def get_deletion_log() -> list:
    """Get account deletion log for admin review"""
    try:
        deletions = execute_query(
            """
            SELECT 
                adl.*,
                u.username as admin_username
            FROM account_deletion_log adl
            LEFT JOIN users u ON adl.admin_user_id = u.id
            ORDER BY adl.deletion_timestamp DESC
            """,
            fetch_all=True
        )
        return [dict(deletion) for deletion in deletions] if deletions else []
    except Exception as e:
        log_error(f"Error getting deletion log: {e}", "GDPR", e)
        return []

def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for forwarded headers first (for reverse proxies)
    forwarded_ip = request.headers.get("X-Forwarded-For")
    if forwarded_ip:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_ip.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"

def require_gdpr_consent(user_id: int) -> bool:
    """Check if user needs to provide GDPR consent before using the system"""
    return not has_user_given_consent(user_id)