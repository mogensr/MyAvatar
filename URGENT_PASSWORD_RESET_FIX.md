# 🚨 URGENT: Password Reset Fix Required ASAP

## PROBLEM SUMMARY
Password reset in admin panel consistently fails with `?error=update_failed` despite multiple fix attempts.

## CURRENT STATUS
- ✅ Admin panel accessible
- ✅ Edit User page loads correctly  
- ✅ Password field with show/hide functionality added
- ❌ Backend password update ALWAYS fails

## LATEST ERROR LOGS
```
2025-08-05 11:01:39,058 - MyAvatar - ERROR - [Database] PostgreSQL query error - Code: 42804: column "is_admin" is of type integer but expression is of type boolean
psycopg2.errors.DatatypeMismatch: column "is_admin" is of type integer but expression is of type boolean
Query parameters: ('testuser', 'test@example.com', True, False, '$2b$12$Xugrw9sg4k5o49oKOIBnROjQyweINM71HhsiSFZcA15Mgj4/VNAV.', 2)
```

## ATTEMPTED FIXES (ALL FAILED)
1. ❌ Fixed bcrypt import → Used passlib instead
2. ❌ Fixed boolean→integer conversion for is_admin/is_premium  
3. ❌ Added proper error handling
4. ❌ Fixed requirements.txt conflicts

## CURRENT CODE LOCATION
File: `c:\Brugere\mogen\Projects\python\CHATGPT\MyAvatar\app\routes\admin_routes.py`
Function: `admin_edit_user_save()` (line ~447)

## CURRENT PROBLEMATIC CODE
```python
@router.post("/edit-user/{user_id}")
async def admin_edit_user_save(request: Request, user_id: int):
    """Save user edits with optional password reset"""
    try:
        admin_user = require_admin(request)
        if not admin_user:
            return RedirectResponse(url="/login", status_code=302)
        
        form = await request.form()
        username = str(form.get("username", "")).strip()
        email = str(form.get("email", "")).strip()
        is_premium = 1 if form.get("is_premium") else 0
        is_admin = 1 if form.get("is_admin") else 0
        new_password = str(form.get("new_password", "")).strip()
        
        if not username or not email:
            return RedirectResponse(url=f"/admin/edit-user/{user_id}?error=missing_fields", status_code=302)
        
        # Check if password reset is requested
        if new_password:
            if len(new_password) < 6:
                return RedirectResponse(url=f"/admin/edit-user/{user_id}?error=password_too_short", status_code=302)
            
            # Import password hashing from existing auth system
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            # Hash the new password
            hashed_password = pwd_context.hash(new_password)
            
            # Update user with password
            update_query = """
            UPDATE users 
            SET username = %s, email = %s, is_premium = %s, is_admin = %s, hashed_password = %s 
            WHERE id = %s
            """
            
            result = execute_query(update_query, (username, email, is_premium, is_admin, hashed_password, user_id))
            
            if result is not None:
                logger.info(f"🔐 Admin {admin_user.get('username')} updated user {username} (ID: {user_id}) with password reset - Premium: {is_premium}")
                return RedirectResponse(url=f"/admin/users?success=user_updated_with_password&username={username}", status_code=302)
            else:
                return RedirectResponse(url=f"/admin/edit-user/{user_id}?error=update_failed", status_code=302)
        else:
            # Update user without password change
            update_query = """
            UPDATE users 
            SET username = %s, email = %s, is_premium = %s, is_admin = %s 
            WHERE id = %s
            """
            
            result = execute_query(update_query, (username, email, is_premium, is_admin, user_id))
            
            if result is not None:
                logger.info(f"Admin {admin_user.get('username')} updated user {username} (ID: {user_id}) - Premium: {is_premium}")
                return RedirectResponse(url="/admin/users?success=user_updated", status_code=302)
            else:
                return RedirectResponse(url=f"/admin/edit-user/{user_id}?error=update_failed", status_code=302)
            
    except Exception as e:
        logger.error(f"Edit user save error: {e}")
        return RedirectResponse(url=f"/admin/edit-user/{user_id}?error=update_failed", status_code=302)
```

## DATABASE SCHEMA INFO
- Table: `users`
- Password column: `hashed_password` (TEXT)
- Admin column: `is_admin` (INTEGER 0/1)
- Premium column: `is_premium` (INTEGER 0/1)

## REQUIREMENTS
- Reset password for user `testuser` (ID: 2) to `Test123`
- Reset password for user `Lars-Christian` (ID: 4) to `L-C.B123`
- Fix must work in production Railway environment

## CLAUDE TASK
1. **Debug why execute_query() returns None**
2. **Fix the database update issue**
3. **Ensure password reset works end-to-end**
4. **Test with both users**

## PRIORITY: URGENT - ASAP FIX REQUIRED

The user needs this working immediately for production use.
