"""
Password Reset Routes for MyAvatar
=================================
Handles forgot password functionality with email verification
"""

import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ..auth.authentication import get_password_hash, validate_password_strength
from ..db.database import execute_query
from ..logger.log_handler import log_info, log_error

# Configure router and templates
router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USERNAME)

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Display forgot password form"""
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@router.post("/forgot-password")
async def request_password_reset(request: Request, email: str = Form(...)):
    """Send password reset email"""
    try:
        # Check if user exists
        user = execute_query(
            "SELECT id, username, email FROM users WHERE LOWER(email) = LOWER(?)",
            (email.strip(),),
            fetch_one=True
        )
        
        if not user:
            # Don't reveal if email exists or not for security
            return JSONResponse(
                content={
                    "success": True, 
                    "message": "If this email exists in our system, you will receive a password reset link."
                }
            )
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)  # Token expires in 1 hour
        
        # Store reset token in database
        execute_query(
            """INSERT OR REPLACE INTO password_reset_tokens 
               (user_id, token, expires_at, created_at) 
               VALUES (?, ?, ?, datetime('now'))""",
            (user[0], reset_token, expires_at)
        )
        
        # Send reset email
        reset_url = f"{request.base_url}reset-password?token={reset_token}"
        
        if await send_reset_email(user[2], user[1], reset_url):
            log_info(f"Password reset email sent to {email}", "PasswordReset")
            return JSONResponse(
                content={
                    "success": True,
                    "message": "Password reset email sent! Check your inbox."
                }
            )
        else:
            return JSONResponse(
                content={
                    "success": False,
                    "error": "Failed to send reset email. Please try again later."
                },
                status_code=500
            )
            
    except Exception as e:
        log_error(f"Error in password reset request: {str(e)}", "PasswordReset")
        return JSONResponse(
            content={
                "success": False,
                "error": "An error occurred. Please try again later."
            },
            status_code=500
        )

@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    """Display password reset form"""
    try:
        # Verify token is valid and not expired
        reset_record = execute_query(
            """SELECT pr.user_id, pr.expires_at, u.email, u.username 
               FROM password_reset_tokens pr 
               JOIN users u ON pr.user_id = u.id 
               WHERE pr.token = ? AND pr.expires_at > datetime('now')""",
            (token,),
            fetch_one=True
        )
        
        if not reset_record:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Invalid or expired reset token",
                "message": "Please request a new password reset."
            })
        
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "token": token,
            "email": reset_record[2]
        })
        
    except Exception as e:
        log_error(f"Error displaying reset password page: {str(e)}", "PasswordReset")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "An error occurred",
            "message": "Please try again later."
        })

@router.post("/reset-password")
async def process_password_reset(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    """Process password reset"""
    try:
        # Validate passwords match
        if new_password != confirm_password:
            return JSONResponse(
                content={"success": False, "error": "Passwords do not match"},
                status_code=400
            )
        
        # Validate password strength
        is_strong, message = validate_password_strength(new_password)
        if not is_strong:
            return JSONResponse(
                content={"success": False, "error": message},
                status_code=400
            )
        
        # Verify token is valid and not expired
        reset_record = execute_query(
            """SELECT pr.user_id, u.email, u.username 
               FROM password_reset_tokens pr 
               JOIN users u ON pr.user_id = u.id 
               WHERE pr.token = ? AND pr.expires_at > datetime('now')""",
            (token,),
            fetch_one=True
        )
        
        if not reset_record:
            return JSONResponse(
                content={"success": False, "error": "Invalid or expired reset token"},
                status_code=400
            )
        
        user_id = reset_record[0]
        
        # Hash new password
        hashed_password = get_password_hash(new_password)
        
        # Update user password
        execute_query(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_password, user_id)
        )
        
        # Delete used reset token
        execute_query(
            "DELETE FROM password_reset_tokens WHERE token = ?",
            (token,)
        )
        
        # Clean up expired tokens
        execute_query(
            "DELETE FROM password_reset_tokens WHERE expires_at <= datetime('now')"
        )
        
        log_info(f"Password reset successful for user {reset_record[2]}", "PasswordReset")
        
        return JSONResponse(
            content={
                "success": True,
                "message": "Password reset successful! You can now login with your new password."
            }
        )
        
    except Exception as e:
        log_error(f"Error processing password reset: {str(e)}", "PasswordReset")
        return JSONResponse(
            content={
                "success": False,
                "error": "An error occurred. Please try again."
            },
            status_code=500
        )

async def send_reset_email(to_email: str, username: str, reset_url: str) -> bool:
    """Send password reset email"""
    try:
        if not SMTP_USERNAME or not SMTP_PASSWORD:
            log_error("SMTP credentials not configured", "PasswordReset")
            return False
        
        # Create email content
        subject = "MyAvatar - Password Reset Request"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0;">MyAvatar</h1>
                <p style="color: white; margin: 5px 0;">Password Reset Request</p>
            </div>
            
            <div style="padding: 30px; background: #f9f9f9;">
                <h2 style="color: #333;">Hello {username},</h2>
                
                <p style="color: #666; line-height: 1.6;">
                    We received a request to reset your password for your MyAvatar account.
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" 
                       style="background: #667eea; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Reset Password
                    </a>
                </div>
                
                <p style="color: #666; line-height: 1.6;">
                    This link will expire in 1 hour for security reasons.
                </p>
                
                <p style="color: #666; line-height: 1.6;">
                    If you didn't request this password reset, please ignore this email.
                </p>
                
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                
                <p style="color: #999; font-size: 12px;">
                    If the button doesn't work, copy and paste this link into your browser:<br>
                    <a href="{reset_url}" style="color: #667eea;">{reset_url}</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        
        # Add HTML content
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
        
    except Exception as e:
        log_error(f"Failed to send reset email to {to_email}: {str(e)}", "PasswordReset")
        return False

# Initialize password reset tokens table
def init_password_reset_table():
    """Create password reset tokens table if it doesn't exist"""
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        log_info("Password reset tokens table initialized", "PasswordReset")
    except Exception as e:
        log_error(f"Failed to initialize password reset table: {str(e)}", "PasswordReset")

# Initialize table on import
init_password_reset_table()
