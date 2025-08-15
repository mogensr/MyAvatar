#!/usr/bin/env python3
"""
Create avatar_voice_parameters table in PostgreSQL - Fixed imports
"""
import os
import psycopg2
from urllib.parse import urlparse

def create_avatar_voice_parameters_table():
    """Create the avatar_voice_parameters table using direct psycopg2"""
    try:
        # Get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL environment variable not found")
            return False
            
        print("🔧 Connecting to PostgreSQL database...")
        
        # Parse database URL
        url = urlparse(database_url)
        
        # Connect to database
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port,
            database=url.path[1:],  # Remove leading slash
            user=url.username,
            password=url.password
        )
        
        cursor = conn.cursor()
        
        print("🔧 Creating avatar_voice_parameters table...")
        
        # Create the table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS avatar_voice_parameters (
            id SERIAL PRIMARY KEY,
            avatar_id VARCHAR(255) NOT NULL,
            user_id INTEGER,
            emotion FLOAT DEFAULT 0.5,
            speed FLOAT DEFAULT 1.0, 
            pitch FLOAT DEFAULT 1.0,
            voice_id VARCHAR(255),
            language VARCHAR(10) DEFAULT 'en-US',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            
            UNIQUE(avatar_id, user_id)
        );
        """
        
        cursor.execute(create_table_sql)
        print("✅ Table avatar_voice_parameters created successfully!")
        
        # Create indexes
        print("🔧 Creating indexes...")
        
        index1_sql = "CREATE INDEX IF NOT EXISTS idx_avatar_voice_params_avatar ON avatar_voice_parameters(avatar_id);"
        cursor.execute(index1_sql)
        print("✅ Index on avatar_id created!")
        
        index2_sql = "CREATE INDEX IF NOT EXISTS idx_avatar_voice_params_user ON avatar_voice_parameters(user_id);"
        cursor.execute(index2_sql)
        print("✅ Index on user_id created!")
        
        # Commit changes
        conn.commit()
        
        # Verify table exists
        verify_sql = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'avatar_voice_parameters'
        ORDER BY ordinal_position;
        """
        
        cursor.execute(verify_sql)
        columns = cursor.fetchall()
        
        print("\n📋 Table structure verified:")
        for col in columns:
            print(f"  - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'} {col[3] or ''}")
            
        print("\n🎉 avatar_voice_parameters table created successfully with all indexes!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error creating table: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    create_avatar_voice_parameters_table()
