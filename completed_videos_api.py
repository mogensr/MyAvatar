# New API endpoint for completed videos
@router.get("/api/completed-videos")
async def get_completed_videos_api(request: Request):
    """Get only completed videos with URLs - clean approach"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"videos": [], "count": 0, "error": "Not authenticated"}
            )
        
        # Direct SQL query - bypass existing methods
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT id, title, video_url, thumbnail_url, duration, created_at, heygen_video_id
            FROM videos 
            WHERE user_id = %s 
            AND status = 'completed' 
            AND video_url IS NOT NULL 
            AND video_url != ''
            ORDER BY created_at DESC
        """, (user["id"],))
        
        videos = cur.fetchall()
        conn.close()
        
        # Convert to dict and format dates
        video_list = []
        for video in videos:
            video_dict = dict(video)
            if video_dict.get('created_at'):
                video_dict['created_at'] = video_dict['created_at'].strftime('%b %d, %Y')
            video_list.append(video_dict)
        
        logger.info(f"✅ Completed videos API: Found {len(video_list)} videos for user {user['id']}")
        
        return JSONResponse(
            content={
                "videos": video_list,
                "count": len(video_list),
                "success": True
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error fetching completed videos: {e}")
        return JSONResponse(
            status_code=500,
            content={"videos": [], "count": 0, "error": str(e)}
        )
