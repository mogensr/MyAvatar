"""
Avatar utility functions for MyAvatar
"""
from ..db.database import execute_query
from ..logger.log_handler import log_info, log_error

def ensure_avatar_persistence(user):
    """
    Ensure user has a persistent avatar_id in their profile
    This helps solve the issue where newly setup avatars are not remembered
    
    Args:
        user: User dict from get_current_user
        
    Returns:
        avatar_id if one is found, None otherwise
    """
    try:
        # Get user's avatar ID
        avatar_id = user.get("avatar_id")
        
        # If no avatar_id in user record, check for a default avatar
        if not avatar_id:
            log_info(f"No avatar_id in user record for {user['username']}, checking default avatars", "AvatarUtils")
            
            # First try to find a default avatar
            avatar = execute_query(
                "SELECT avatar_id FROM user_avatars WHERE user_id = ? AND is_default = 1",
                (user["id"],),
                fetch_one=True
            )
            
            if avatar:
                avatar_id = avatar["avatar_id"]
                # Update user record with this default avatar for future use
                execute_query(
                    "UPDATE users SET avatar_id = ? WHERE id = ?",
                    (avatar_id, user["id"])
                )
                log_info(f"Updated user record with default avatar: {avatar_id}", "AvatarUtils")
            else:
                # Check for ANY avatar for this user if no default is set
                avatar = execute_query(
                    "SELECT avatar_id FROM user_avatars WHERE user_id = ? LIMIT 1",
                    (user["id"],),
                    fetch_one=True
                )
                
                if avatar:
                    avatar_id = avatar["avatar_id"]
                    # Set this as default since there's no other default
                    execute_query(
                        "UPDATE user_avatars SET is_default = 1 WHERE avatar_id = ? AND user_id = ?",
                        (avatar_id, user["id"])
                    )
                    # Update user record
                    execute_query(
                        "UPDATE users SET avatar_id = ? WHERE id = ?",
                        (avatar_id, user["id"])
                    )
                    log_info(f"Set avatar {avatar_id} as default for user {user['username']}", "AvatarUtils")
                else:
                    log_info(f"No avatars found for user {user['username']}", "AvatarUtils")
                    return None
                    
        return avatar_id
        
    except Exception as e:
        log_error(f"Error in ensure_avatar_persistence: {str(e)}", "AvatarUtils")
        return None
