#!/usr/bin/env python3
"""
Create avatar_voice_parameters table in PostgreSQL
"""
import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from db.database import execute_query

def create_avatar_voice_parameters_table():
    """Create the avatar_voice_parameters table"""
    try:
        print("🔧 Creating avatar_voice_parameters table...")
        
        # Create the table
        create_table_sql = """
        CREATE TABLE avatar_voice_parameters (
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
        
        execute_query(create_table_sql)
        print("✅ Table avatar_voice_parameters created successfully!")
        
        # Create indexes
        print("🔧 Creating indexes...")
        
        index1_sql = "CREATE INDEX idx_avatar_voice_params_avatar ON avatar_voice_parameters(avatar_id);"
        execute_query(index1_sql)
        print("✅ Index on avatar_id created!")
        
        index2_sql = "CREATE INDEX idx_avatar_voice_params_user ON avatar_voice_parameters(user_id);"
        execute_query(index2_sql)
        print("✅ Index on user_id created!")
        
        # Verify table exists
        verify_sql = """
        SELECT table_name, column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'avatar_voice_parameters'
        ORDER BY ordinal_position;
        """
        
        columns = execute_query(verify_sql, fetch_all=True)
        
        print("\n📋 Table structure verified:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]}) {'NULL' if col[3] == 'YES' else 'NOT NULL'} {col[4] or ''}")
            
        print("\n🎉 avatar_voice_parameters table created successfully with all indexes!")
        
    except Exception as e:
        print(f"❌ Error creating table: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    create_avatar_voice_parameters_table()
