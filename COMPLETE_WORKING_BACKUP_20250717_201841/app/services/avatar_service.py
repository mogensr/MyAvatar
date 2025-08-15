import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Import database query function
try:
    from ..db.database import execute_query
except ImportError:
    def execute_query(query, params=(), fetch_one=False, fetch_all=False):
        logger.error("execute_query not available - database import failed")
        return None

class AvatarService:
    """Service for managing user avatars"""
    
    def __init__(self):
        self.default_avatars = [
            {
                'heygen_avatar_id': 'Tyler-insuit-20220721',
                'avatar_name': 'Professional Male',
                'avatar_image_url': 'https://files2.heygen.ai/avatar/v3/25ef6c86b1254a5e8fffe00b32275d93/25ef6c86b1254a5e8fffe00b32275d93.jpg',
                'is_default': 1
            },
            {
                'heygen_avatar_id': 'Kristin_public_2_20240108', 
                'avatar_name': 'Professional Female',
                'avatar_image_url': 'https://files2.heygen.ai/avatar/v3/d0b8f0e4e53143ab8b2e8a4c9b2e2e0d/d0b8f0e4e53143ab8b2e8a4c9b2e2e0d.jpg',
                'is_default': 1
            },
            {
                'heygen_avatar_id': 'josh_lite3_20230714',
                'avatar_name': 'Casual Male',
                'avatar_image_url': 'https://files2.heygen.ai/avatar/v3/josh_lite3_20230714/josh_lite3_20230714.jpg',
                'is_default': 1
            },
            {
                'heygen_avatar_id': 'Susan_public_2_20240108',
                'avatar_name': 'Friendly Female',
                'avatar_image_url': 'https://files2.heygen.ai/avatar/v3/Susan_public_2_20240108/Susan_public_2_20240108.jpg',
                'is_default': 1
            }
        ]
    
    def setup_default_avatars_for_user(self, user_id: int) -> bool:
        """Set up default avatars for new users - FIXED VERSION"""
        try:
            logger.info(f"Setting up default avatars for user ID: {user_id}")
            
            # First, check if user already has avatars to avoid duplicates
            existing_avatars = execute_query(
                "SELECT COUNT(*) as count FROM user_avatars WHERE user_id = %s",
                (user_id,),
                fetch_one=True
            )
            
            if existing_avatars and existing_avatars.get('count', 0) > 0:
                logger.info(f"User {user_id} already has avatars, skipping setup")
                return True
            
            # Add each default avatar
            for avatar_data in self.default_avatars:
                try:
                    # Check if this specific avatar already exists for the user
                    existing_check = execute_query(
                        "SELECT id FROM user_avatars WHERE user_id = %s AND heygen_avatar_id = %s",
                        (user_id, avatar_data['heygen_avatar_id']),
                        fetch_one=True
                    )
                    
                    if existing_check:
                        logger.info(f"Avatar {avatar_data['avatar_name']} already exists for user {user_id}")
                        continue
                    
                    insert_query = """
                    INSERT INTO user_avatars (user_id, heygen_avatar_id, avatar_name, avatar_image_url, is_default, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    
                    result = execute_query(
                        insert_query,
                        (
                            user_id,
                            avatar_data['heygen_avatar_id'],
                            avatar_data['avatar_name'],
                            avatar_data['avatar_image_url'],
                            avatar_data['is_default'],
                            datetime.now()
                        )
                    )
                    
                    if result is not None:
                        logger.info(f"✅ Added default avatar '{avatar_data['avatar_name']}' for user {user_id}")
                    else:
                        logger.error(f"❌ Failed to add avatar '{avatar_data['avatar_name']}' for user {user_id}")
                        
                except Exception as avatar_error:
                    logger.error(f"Error adding individual avatar {avatar_data['avatar_name']} for user {user_id}: {avatar_error}")
            
            # Verify avatars were added
            verification_query = execute_query(
                "SELECT COUNT(*) as count FROM user_avatars WHERE user_id = %s",
                (user_id,),
                fetch_one=True
            )
            
            if verification_query:
                avatar_count = verification_query.get('count', 0)
                logger.info(f"✅ User {user_id} now has {avatar_count} avatars")
                return avatar_count > 0
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Critical error setting up default avatars for user {user_id}: {e}")
            # Try a simpler fallback approach
            return self._setup_fallback_avatar(user_id)
    
    def _setup_fallback_avatar(self, user_id: int) -> bool:
        """Fallback: setup just one simple avatar"""
        try:
            simple_avatar = self.default_avatars[0]  # Use first avatar as fallback
            
            execute_query(
                """INSERT INTO user_avatars (user_id, heygen_avatar_id, avatar_name, avatar_image_url, is_default, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, simple_avatar['heygen_avatar_id'], simple_avatar['avatar_name'], 
                 simple_avatar['avatar_image_url'], simple_avatar['is_default'], datetime.now())
            )
            logger.info(f"✅ Fallback: Added simple default avatar for user {user_id}")
            return True
        except Exception as fallback_error:
            logger.error(f"❌ Even fallback avatar setup failed for user {user_id}: {fallback_error}")
            return False

    def verify_user_avatars_setup(self, user_id: int) -> bool:
        """Verify that user has avatars and fix if missing"""
        try:
            avatars = execute_query(
                "SELECT * FROM user_avatars WHERE user_id = %s",
                (user_id,),
                fetch_all=True
            )
            
            if not avatars or len(avatars) == 0:
                logger.warning(f"🎭 User {user_id} has no avatars - setting up now")
                return self.setup_default_avatars_for_user(user_id)
            else:
                logger.info(f"✅ User {user_id} has {len(avatars)} avatars")
                return True
                
        except Exception as e:
            logger.error(f"Error verifying user avatars: {e}")
            return False
    
    def get_user_avatars(self, user_id: int) -> List[Dict]:
        """Get all avatars for a user"""
        try:
            avatars = execute_query(
                "SELECT * FROM user_avatars WHERE user_id = %s ORDER BY is_default DESC, created_at ASC",
                (user_id,),
                fetch_all=True
            )
            
            if not avatars:
                # Try to set up avatars if none exist
                if self.setup_default_avatars_for_user(user_id):
                    avatars = execute_query(
                        "SELECT * FROM user_avatars WHERE user_id = %s ORDER BY is_default DESC, created_at ASC",
                        (user_id,),
                        fetch_all=True
                    )
            
            # Convert to list of dicts
            avatar_list = []
            if avatars:
                for avatar in avatars:
                    if isinstance(avatar, dict):
                        avatar_list.append(avatar)
                    else:
                        # Convert from row object to dict
                        avatar_dict = dict(avatar) if hasattr(avatar, '_asdict') else dict(avatar)
                        avatar_list.append(avatar_dict)
            
            return avatar_list
            
        except Exception as e:
            logger.error(f"Error getting user avatars: {e}")
            return []
    
    def create_custom_avatar(self, user_id: int, avatar_data: Dict) -> Optional[int]:
        """Create a custom avatar for a user"""
        try:
            insert_query = """
            INSERT INTO user_avatars (user_id, heygen_avatar_id, avatar_name, avatar_image_url, is_default, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """
            
            result = execute_query(
                insert_query,
                (
                    user_id,
                    avatar_data.get('heygen_avatar_id'),
                    avatar_data.get('avatar_name'),
                    avatar_data.get('avatar_image_url'),
                    0,  # Custom avatars are not default
                    datetime.now()
                ),
                fetch_one=True
            )
            
            if result:
                avatar_id = result.get('id')
                logger.info(f"✅ Created custom avatar for user {user_id}: {avatar_id}")
                return avatar_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating custom avatar: {e}")
            return None

# Global avatar service instance
avatar_service = AvatarService()
