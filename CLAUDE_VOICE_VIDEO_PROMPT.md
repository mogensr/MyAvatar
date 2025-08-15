# Claude Voice-to-Video Fix Instructions

## Current Status
The voice-to-video widget has been restored with a clean template, but avatar display issues persist despite multiple fix attempts.

## What Claude Provided
- Clean, working `voice_recording.html` template with proper JavaScript structure
- Enhanced Generate Video functionality with progress feedback
- Proper error handling and user feedback
- Working record button functionality

## What Cascade Has Done Since Claude's Instructions

### ✅ Fixed Database Error
- **Issue**: Backend was throwing error: `column "updated_at" of relation "videos" does not exist`
- **Fix Applied**: Removed `updated_at = NOW()` references from database UPDATE queries in `main.py` lines 858 and 890
- **Result**: Database error resolved

### ❌ Avatar Display Still Broken
- **Issue**: Avatar images not displaying - shows broken image placeholder
- **Attempted Fix 1**: Simplified avatar query in `app/routes/video_routes.py` voice-to-video route
- **Attempted Fix 2**: Restored "simple working version" of avatar query that was supposedly working before
- **Current Query**: `SELECT id, avatar_name, avatar_image_url, heygen_avatar_id FROM user_avatars WHERE user_id = %s AND avatar_image_url NOT LIKE '%placeholder%' ORDER BY created_at DESC`
- **Result**: Still not working - avatars still not displaying

## Files Modified by Cascade
1. **main.py** - Removed `updated_at` column references from database queries (lines 858, 890)
2. **app/routes/video_routes.py** - Simplified avatar query in `/voice-to-video` route (lines 993-1022)

## Current Problem
- Database error is fixed
- Record button works
- Generate Video button works
- **Avatar images still not displaying** despite query fixes

## What Claude Needs to Investigate
1. Why are avatar images not displaying in the voice-to-video widget?
2. Is the issue in the database query, template rendering, or frontend JavaScript?
3. Are there avatars in the database for the test user?
4. Is the avatar data being passed correctly to the template?

## User Feedback
- User confirmed avatars were working "one upgrade back"
- User frustrated that avatar display fix attempts are not working
- User wants Claude to investigate and fix the avatar display issue

## Files to Check
- `templates/voice_recording.html` - Check if avatars are being rendered correctly
- `app/routes/video_routes.py` - Check avatar query and data processing
- Database - Check if avatars exist for the user
- Frontend JavaScript - Check if avatar selection is working
1. `main.py` - main application file with routes
2. `templates/voice_video_clean.html` - new clean template
3. `app/core/database.py` - database utilities
4. Browser developer console - for JavaScript errors

## DEBUGGING APPROACH
1. **Check if JavaScript function exists and is callable**
2. **Verify button click event is properly attached**
3. **Test API endpoint directly** (Postman/curl)
4. **Check browser console for errors**
5. **Verify authentication and CSRF issues**

## EXPECTED OUTCOME
A working Generate Video button that:
- Responds to clicks
- Makes API calls
- Provides user feedback
- Creates video records

**Focus on the fundamentals: button click → API call → response. Nothing fancy, just working functionality.**

---

## CONTEXT FOR CLAUDE
This is a months-long issue that has been extremely frustrating. The user needs a simple, working solution, not more complex debugging. The goal is to get the basic voice-to-video flow working end-to-end.

**Priority: HIGH - User has been blocked on this core functionality for too long.**
