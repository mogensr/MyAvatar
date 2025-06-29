# Enhanced rebuild_user_avatars.py
# Save this as a NEW FILE: rebuild_user_avatars.py in your project root

import os
import sys
import re
import sqlite3
import psycopg2
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ Loaded environment variables from .env file")
except ImportError:
    print("Warning: python-dotenv not available, relying on system environment variables")
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")

# Add the project root to Python path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import database utilities
try:
    from app.db.database import execute_query, USE_POSTGRES, get_db_connection
    from app.api.heygen import get_available_avatars
    from app.logger.log_handler import log_info, log_error
except ImportError as e:
    print(f"Warning: Could not import app modules: {e}")
    print("Running in standalone mode...")
    
    def log_info(msg, context):
        print(f"[{context}] {msg}")
    
    def log_error(msg, context, exc=None):
        print(f"[{context}] ERROR: {msg}")
        if exc:
            print(f"Exception: {exc}")

# ENHANCED NAMING LOGIC (copied from admin_routes.py)
def generate_user_friendly_name(avatar_data):
    """
    Generate user-friendly names from HeyGen avatar data.
    Prioritizes HeyGen's own avatar_name field first.
    """
    
    # Priority 1: Use HeyGen's avatar_name field directly (this is the best source!)
    if 'avatar_name' in avatar_data and avatar_data['avatar_name']:
        heygen_name = str(avatar_data['avatar_name']).strip()
        if heygen_name and not is_technical_id(heygen_name):
            return heygen_name
    
    # Priority 2: Use other explicit display/user-friendly fields if available
    display_fields = ['display_name', 'title', 'name', 'friendly_name', 'label']
    for field in display_fields:
        if field in avatar_data and avatar_data[field]:
            name = str(avatar_data[field]).strip()
            if name and not is_technical_id(name):
                return name
    
    # Priority 3: Build name from metadata fields
    name_parts = []
    
    # Gender/type information
    if 'gender' in avatar_data:
        gender = avatar_data['gender'].lower()
        if gender in ['male', 'man', 'm']:
            name_parts.append('Man')
        elif gender in ['female', 'woman', 'f']:
            name_parts.append('Woman')
    
    # Style/type information
    style_keywords = {
        'professional': 'Professional',
        'business': 'Business',
        'casual': 'Casual',
        'formal': 'Formal',
        'corporate': 'Corporate',
        'suit': 'Business',
        'dress': 'Professional',
        'shirt': 'Casual'
    }
    
    # Check various fields for style indicators
    style_fields = ['style', 'type', 'category', 'description', 'outfit', 'clothing']
    found_style = False
    
    for field in style_fields:
        if field in avatar_data and avatar_data[field]:
            field_value = str(avatar_data[field]).lower()
            for keyword, style_name in style_keywords.items():
                if keyword in field_value:
                    name_parts.insert(0, style_name)  # Put style first
                    found_style = True
                    break
            if found_style:
                break
    
    # Priority 4: Use original avatar_id but clean it up
    if not name_parts:
        avatar_id = avatar_data.get('avatar_id', '')
        cleaned_name = clean_technical_id(avatar_id)
        if cleaned_name:
            return cleaned_name
    
    # Combine parts or use fallback
    if name_parts:
        final_name = ' '.join(name_parts)
        if len(name_parts) == 1:  # Only gender, add "Avatar"
            final_name += ' Avatar'
        return final_name
    
    # Ultimate fallback
    return 'Avatar'

def is_technical_id(name):
    """Check if a name looks like a technical ID rather than user-friendly name."""
    if not name:
        return True
        
    name_lower = name.lower()
    
    # Don't consider good names as technical
    good_patterns = [
        'adrian', 'anna', 'josh', 'professional', 'business', 'casual', 'woman', 'man'
    ]
    
    # If it contains good words, it's probably not technical
    for pattern in good_patterns:
        if pattern in name_lower:
            return False
    
    # Check for long hex strings (like Avatar 7c58319b4e02412cb5d83732fb64e93e)
    if 'avatar' in name_lower and len(name) > 20:
        # Look for hex pattern after "Avatar "
        hex_part = name.replace('Avatar ', '').replace('avatar ', '')
        if len(hex_part) > 16 and all(c in '0123456789abcdefABCDEF' for c in hex_part.replace(' ', '')):
            return True
    
    # Technical ID indicators
    technical_patterns = [
        'camera', 'costume', 'lite', 'v1', 'v2', 'test',
        '20220', '20230', '20240', '20250',  # Years
        'dev', 'prod', 'staging'
    ]
    
    # Check for technical patterns
    for pattern in technical_patterns:
        if pattern in name_lower:
            return True
    
    # Check for mostly lowercase with numbers/underscores (but not names like "adrian in blue suit")
    if any(c in name for c in '_-') and name.islower() and not any(word in name_lower for word in ['in', 'with', 'and']):
        return True
        
    # Check for camelCase or snake_case patterns
    if '_' in name and not ' ' in name:  # snake_case without spaces
        return True
    
    return False

def clean_technical_id(avatar_id):
    """Convert technical ID to more readable format as last resort."""
    if not avatar_id:
        return None
    
    # Remove common technical suffixes/prefixes
    cleaned = avatar_id
    
    # Remove technical suffixes
    suffixes_to_remove = ['_cameraA', '_cameraB', '_camera1', '_camera2', 
                         '_costume1', '_costume2', '_lite', '_lite2', '_v1', '_v2']
    for suffix in suffixes_to_remove:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
            break
    
    # Remove date patterns (e.g., _20220721)
    cleaned = re.sub(r'_\d{8}', '', cleaned)
    cleaned = re.sub(r'_\d{6}', '', cleaned)
    
    # Capitalize first letter and replace underscores
    if cleaned:
        cleaned = cleaned.replace('_', ' ').title()
        # Don't return single letters or very short names
        if len(cleaned) > 2:
            return cleaned
    
    return None

# STANDALONE DATABASE CONNECTION FUNCTIONS
def get_connection():
    """Get database connection (works with both PostgreSQL and SQLite)"""
    
    # Try PostgreSQL first (Railway)
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgres"):
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(database_url)
            conn.autocommit = True
            return conn, True  # Return (connection, is_postgres)
        except Exception as e:
            print(f"Failed to connect to PostgreSQL: {e}")
            
    # Fallback to SQLite
    try:
        import sqlite3
        db_path = "myavatar.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # This makes rows behave like dictionaries
        return conn, False  # Return (connection, is_postgres)
    except Exception as e:
        print(f"Failed to connect to SQLite: {e}")
        return None, False

def execute_db_query(conn, is_postgres, query, params=None, fetch_one=False, fetch_all=False):
    """Execute database query with proper parameter style"""
    
    if is_postgres:
        # Convert ? to %s for PostgreSQL
        pg_query = query.replace('?', '%s')
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(pg_query, params or ())
    else:
        # SQLite
        cursor = conn.cursor()
        cursor.execute(query, params or ())
    
    if fetch_one:
        result = cursor.fetchone()
        cursor.close()
        return dict(result) if result else None
    elif fetch_all:
        results = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in results] if results else []
    else:
        cursor.close()
        return None

def check_database_schema(conn, is_postgres):
    """Check the actual schema of user_avatars table"""
    print("Checking database schema...")
    
    try:
        if is_postgres:
            # PostgreSQL schema query
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'user_avatars'
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            cursor.close()
        else:
            # SQLite schema query
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(user_avatars)")
            columns = cursor.fetchall()
            cursor.close()
            # Convert SQLite format to consistent format
            columns = [{'column_name': col[1], 'data_type': col[2]} for col in columns]
        
        print(f"user_avatars table columns:")
        for col in columns:
            print(f"  - {col['column_name']} ({col['data_type']})")
        
        return columns
        
    except Exception as e:
        print(f"Error checking schema: {e}")
        return []

def get_avatar_name_column(columns):
    """Determine which column contains the avatar name"""
    
    # Look for common name column patterns
    name_candidates = [
        'name', 'avatar_name', 'display_name', 'title', 'friendly_name'
    ]
    
    column_names = [col['column_name'].lower() for col in columns]
    
    for candidate in name_candidates:
        if candidate in column_names:
            # Return the actual column name (with proper case)
            for col in columns:
                if col['column_name'].lower() == candidate:
                    return col['column_name']
    
    return None
    """
    Rebuild avatar names in the database using enhanced naming logic.
    Run this script on your Railway deployment.
    """
    
    print("=== MYAVATAR AVATAR NAME REBUILD SCRIPT ===")
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    # Check environment variables
    HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
    if not HEYGEN_API_KEY:
        print("ERROR: HEYGEN_API_KEY environment variable not found")
        return False
    
    print("✓ HeyGen API key found")
    
    # Connect to database
    conn, is_postgres = get_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        return False
    
    db_type = "PostgreSQL" if is_postgres else "SQLite"
    print(f"✓ Connected to {db_type} database")
    
    try:
        # Import HeyGen API function
        try:
            from app.api.heygen import get_available_avatars
        except ImportError:
            print("ERROR: Could not import HeyGen API module")
            print("Make sure you're running this from the project root directory")
            return False
        
        # Fetch fresh avatar data from HeyGen
        print("Fetching avatar data from HeyGen API...")
        try:
            heygen_response = get_available_avatars(HEYGEN_API_KEY)
        except Exception as e:
            print(f"ERROR: Failed to fetch from HeyGen API: {e}")
            return False
        
        if not heygen_response or not heygen_response.get('success', False):
            print("ERROR: HeyGen API returned unsuccessful response")
            print(f"Response: {heygen_response}")
            return False
        
        avatars_data = heygen_response.get('avatars', [])
        print(f"✓ Fetched {len(avatars_data)} avatars from HeyGen")
        
        # Get current avatars from database
        try:
            db_avatars = execute_db_query(
                conn, is_postgres, 
                "SELECT avatar_id, name FROM user_avatars", 
                fetch_all=True
            )
        except Exception as e:
            print(f"ERROR: Failed to query database: {e}")
            return False
        
        print(f"✓ Found {len(db_avatars)} avatars in database")
        
        if not db_avatars:
            print("No avatars found in database. Nothing to rebuild.")
            return True
        
        # Create lookup for HeyGen data
        heygen_lookup = {avatar['avatar_id']: avatar for avatar in avatars_data}
        
        # Track updates
        updates_made = 0
        technical_names_found = 0
        
        print("\nAnalyzing and updating avatar names...")
        print("-" * 60)
        
        # Process each avatar in database
        for db_avatar in db_avatars:
            avatar_id = db_avatar['avatar_id']
            current_name = db_avatar['name']
            
            # Check if current name looks technical
            if is_technical_id(current_name):
                technical_names_found += 1
                
                # Get corresponding HeyGen data
                if avatar_id in heygen_lookup:
                    heygen_data = heygen_lookup[avatar_id]
                    new_name = generate_user_friendly_name(heygen_data)
                    
                    # Update if the new name is different and better
                    if new_name != current_name and not is_technical_id(new_name):
                        try:
                            execute_db_query(
                                conn, is_postgres,
                                "UPDATE user_avatars SET name = ? WHERE avatar_id = ?",
                                (new_name, avatar_id)
                            )
                            print(f"Updated: '{current_name}' → '{new_name}'")
                            updates_made += 1
                        except Exception as e:
                            print(f"ERROR updating {avatar_id}: {e}")
                    else:
                        print(f"Kept: '{current_name}' (no better alternative found)")
                else:
                    print(f"Warning: Avatar {avatar_id} not found in HeyGen data")
            else:
                # Name looks good, keep it
                print(f"Good: '{current_name}' (already user-friendly)")
        
        # Summary
        print(f"\n{'='*60}")
        print(f"REBUILD SUMMARY")
        print(f"{'='*60}")
        print(f"Database type: {db_type}")
        print(f"Total avatars in database: {len(db_avatars)}")
        print(f"Technical names found: {technical_names_found}")
        print(f"Names updated: {updates_made}")
        print(f"Names unchanged: {technical_names_found - updates_made}")
        
        # Show some examples of current names
        try:
            sample_avatars = execute_db_query(
                conn, is_postgres,
                "SELECT name FROM user_avatars LIMIT 10",
                fetch_all=True
            )
            print(f"\nSample avatar names after update:")
            for avatar in sample_avatars:
                print(f"  - {avatar['name']}")
        except Exception as e:
            print(f"Could not fetch sample names: {e}")
        
        conn.close()
        print(f"\n✓ Rebuild completed successfully at {datetime.now().isoformat()}")
        return True
        
    except Exception as e:
        print(f"ERROR during rebuild: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def dry_run_rebuild():
    """
    Test the rebuild logic without making database changes.
    """
    print("=== DRY RUN MODE - NO CHANGES WILL BE MADE ===\n")
    
    HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
    if not HEYGEN_API_KEY:
        print("ERROR: HEYGEN_API_KEY not found")
        return False
    
    conn, is_postgres = get_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        return False
    
    db_type = "PostgreSQL" if is_postgres else "SQLite"
    print(f"Connected to {db_type} database")
    
    # Check database schema first
    columns = check_database_schema(conn, is_postgres)
    if not columns:
        print("ERROR: Could not determine database schema")
        return False
    
    # Find the correct name column
    name_column = get_avatar_name_column(columns)
    if not name_column:
        print("ERROR: Could not find name column in user_avatars table")
        print("Available columns:", [col['column_name'] for col in columns])
        return False
    
    print(f"✓ Using column '{name_column}' for avatar names")
    
    try:
        # Import HeyGen API
        from app.api.heygen import get_available_avatars
        
        # Get HeyGen data
        heygen_response = get_available_avatars(HEYGEN_API_KEY)
        if not heygen_response or not heygen_response.get('success', False):
            print("ERROR: Could not fetch HeyGen data")
            return False
            
        avatars_data = heygen_response.get('avatars', [])
        heygen_lookup = {avatar['avatar_id']: avatar for avatar in avatars_data}
        
        # Analyze current names using the correct column
        db_avatars = execute_db_query(
            conn, is_postgres,
            f"SELECT avatar_id, {name_column} FROM user_avatars LIMIT 20",
            fetch_all=True
        )
        
        print("Current names vs proposed names:")
        print("-" * 60)
        print(f"{'STATUS':<10} | {'CURRENT NAME':<25} | {'PROPOSED NAME'}")
        print("-" * 60)
        
        technical_count = 0
        
        for db_avatar in db_avatars:
            avatar_id = db_avatar['avatar_id']
            current_name = db_avatar[name_column]
            
            if avatar_id in heygen_lookup:
                heygen_data = heygen_lookup[avatar_id]
                proposed_name = generate_user_friendly_name(heygen_data)
                
                status = "TECHNICAL" if is_technical_id(current_name) else "GOOD"
                change_indicator = "→" if proposed_name != current_name else "✓"
                
                if is_technical_id(current_name):
                    technical_count += 1
                
                print(f"{status:<10} | {current_name:<25} | {proposed_name}")
            else:
                print(f"{'MISSING':<10} | {current_name:<25} | (not in HeyGen)")
        
        print(f"\nSummary: {technical_count} technical names found that could be improved")
        print(f"Name column used: {name_column}")
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        print("Running in DRY RUN mode...")
        success = dry_run_rebuild()
    else:
        print("Running FULL REBUILD...")
        print("This will modify your database!")
        print("Use --dry-run flag to test first.")
        print()
        
        # Ask for confirmation in interactive mode
        if sys.stdin.isatty():  # Only ask if running interactively
            response = input("Continue? (y/N): ").strip().lower()
            if response != 'y':
                print("Cancelled.")
                sys.exit(0)
        
        success = rebuild_avatar_names()
    
    sys.exit(0 if success else 1)