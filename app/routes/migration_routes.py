"""
Database migration routes for Railway deployment
"""
from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
from ..db.database import execute_query, USE_POSTGRES
from ..auth.authentication import require_admin

router = APIRouter()

def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        if USE_POSTGRES:
            # PostgreSQL way to check if column exists
            check_query = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = %s
            """
            result = execute_query(check_query, (table_name, column_name), fetch_one=True)
            return result is not None
        else:
            # SQLite way to check if column exists
            check_query = f"PRAGMA table_info({table_name})"
            columns = execute_query(check_query, fetch_all=True)
            return any(col['name'] == column_name for col in columns) if columns else False
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking column: {str(e)}")

@router.post("/admin/migrate/add-description-column")
async def migrate_add_description_column(request: Request):
    """
    Add missing 'description' column to videos table (Admin only)
    Fixes: column "description" of relation "videos" does not exist
    """
    # Require admin access
    require_admin(request)
    
    try:
        # Check if description column already exists
        if check_column_exists('videos', 'description'):
            return {
                "success": True,
                "message": "'description' column already exists in videos table",
                "action": "none"
            }
        
        # Add the missing column
        alter_query = "ALTER TABLE videos ADD COLUMN description TEXT"
        execute_query(alter_query)
        
        # Verify the column was added
        if check_column_exists('videos', 'description'):
            return {
                "success": True,
                "message": "Successfully added 'description' column to videos table",
                "action": "column_added"
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail="Column was added but could not be verified"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Migration failed: {str(e)}"
        )

@router.get("/admin/migrate/check-schema")
async def check_database_schema(request: Request):
    """
    Check database schema for missing columns (Admin only)
    """
    # Require admin access
    require_admin(request)
    
    try:
        schema_issues = []
        
        # Check for description column in videos table
        if not check_column_exists('videos', 'description'):
            schema_issues.append({
                "table": "videos",
                "column": "description",
                "issue": "Missing column",
                "fix": "Run /admin/migrate/add-description-column"
            })
        
        return {
            "database_type": "PostgreSQL" if USE_POSTGRES else "SQLite",
            "schema_issues": schema_issues,
            "issues_found": len(schema_issues),
            "status": "healthy" if len(schema_issues) == 0 else "needs_migration"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Schema check failed: {str(e)}"
        )
