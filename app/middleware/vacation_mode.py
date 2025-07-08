import logging
import requests
from datetime import datetime, date
from typing import Tuple, Dict, Optional

# Import config
from ..config.settings import config

# Import database query function
try:
    from ..db.database import execute_query
except ImportError:
    def execute_query(query, params=(), fetch_one=False, fetch_all=False):
        logger.error("execute_query not available - database import failed")
        return None

logger = logging.getLogger(__name__)

def check_emergency_stop() -> Tuple[bool, Optional[str]]:
    """Check if emergency stop is activated"""
    if config.EMERGENCY_STOP:
        return True, "🚧 MyAvatar is temporarily undergoing maintenance to improve our service. Please check back in a few hours!"
    return False, None

def check_user_limits() -> Tuple[bool, Optional[str]]:
    """Check if we've hit user registration limits"""
    try:
        # Check total users
        total_users_result = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        total_users = total_users_result['count'] if total_users_result else 0
        
        if total_users >= config.MAX_TOTAL_USERS:
            return False, f"🎉 Incredible! MyAvatar has reached {config.MAX_TOTAL_USERS} beta users! We're scaling up our infrastructure to handle the amazing demand. Please check back next week for expanded capacity!"
        
        # Check daily registrations
        today = date.today()
        daily_users_result = execute_query(
            "SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = %s", 
            (today,), 
            fetch_one=True
        )
        daily_users = daily_users_result['count'] if daily_users_result else 0
        
        if daily_users >= config.MAX_DAILY_REGISTRATIONS:
            return False, f"🔥 What an amazing day! We've had {config.MAX_DAILY_REGISTRATIONS} new users join MyAvatar today! To ensure the best experience for everyone, we've reached our daily capacity. Please try again tomorrow!"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error checking user limits: {e}")
        return False, "⚠️ Our systems are experiencing high demand right now. Please try again in a few minutes!"

def check_user_video_limits(user_id: int) -> Tuple[bool, Optional[str]]:
    """Check if user has hit video creation limits"""
    try:
        user_videos_result = execute_query(
            "SELECT COUNT(*) as count FROM videos WHERE user_id = %s", 
            (user_id,), 
            fetch_one=True
        )
        user_videos = user_videos_result['count'] if user_videos_result else 0
        
        if user_videos >= config.MAX_VIDEOS_PER_USER:
            return False, f"🎬 Wow! You've created {config.MAX_VIDEOS_PER_USER} amazing videos! You're really exploring MyAvatar's capabilities. To ensure fair access during our beta phase, that's our current limit per user. We're working hard to increase these limits as we scale!"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error checking user video limits: {e}")
        return False, "⚠️ Unable to check video limits right now. Please try again in a moment!"

async def get_real_railway_costs() -> Optional[Dict]:
    """Get actual Railway billing data using API"""
    try:
        railway_api_key = config.RAILWAY_API_KEY
        if not railway_api_key or railway_api_key == "your-railway-api-key":
            logger.warning("No valid Railway API key found")
            return None
        
        headers = {
            "Authorization": f"Bearer {railway_api_key}",
            "Content-Type": "application/json"
        }
        
        # Railway GraphQL API query for current month usage
        query = """
        query {
            me {
                currentUsage {
                    amount
                    measurement
                }
                estimatedUsage {
                    amount
                    measurement  
                }
            }
        }
        """
        
        response = requests.post(
            "https://backboard.railway.app/graphql",
            json={"query": query},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'me' in data['data'] and data['data']['me']:
                me_data = data['data']['me']
                current_usage = me_data.get('currentUsage', {}).get('amount', 0)
                estimated_usage = me_data.get('estimatedUsage', {}).get('amount', 0)
                
                return {
                    "current_cost": current_usage / 100,  # Convert cents to dollars
                    "estimated_cost": estimated_usage / 100,
                    "currency": "USD",
                    "status": "success",
                    "budget_limit": config.RAILWAY_BUDGET
                }
        
        logger.error(f"Railway API error: {response.status_code} - {response.text}")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching Railway costs: {e}")
        return None

async def get_heygen_usage_stats() -> Optional[Dict]:
    """Get actual HeyGen API usage and costs"""
    try:
        heygen_api_key = config.HEYGEN_API_KEY
        if not heygen_api_key or heygen_api_key == "your-heygen-api-key":
            logger.warning("No valid HeyGen API key found")
            return None
        
        headers = {
            "X-API-Key": heygen_api_key,
            "Content-Type": "application/json"
        }
        
        # Get quota/usage info from HeyGen
        response = requests.get(
            "https://api.heygen.com/v1/user/quota",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 100:  # HeyGen success code
                quota_data = data.get('data', {})
                
                # Estimate costs based on usage (rough calculation)
                quota_used = quota_data.get('quota_used', 0)
                estimated_cost = quota_used * 0.08  # Rough estimate: $0.08 per credit
                
                return {
                    "quota_used": quota_used,
                    "quota_total": quota_data.get('quota_total', 0), 
                    "quota_remaining": quota_data.get('quota_remaining', 0),
                    "current_month_usage": quota_data.get('current_month_usage', 0),
                    "estimated_cost": estimated_cost,
                    "budget_limit": config.HEYGEN_BUDGET,
                    "status": "success"
                }
        
        logger.error(f"HeyGen API error: {response.status_code} - {response.text}")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching HeyGen usage: {e}")
        return None

async def check_budget_limits() -> Tuple[bool, Optional[str]]:
    """Check if we've exceeded budget limits"""
    try:
        railway_costs = await get_real_railway_costs()
        heygen_usage = await get_heygen_usage_stats()
        
        railway_percentage = 0
        heygen_percentage = 0
        
        if railway_costs:
            railway_percentage = (railway_costs['current_cost'] / config.RAILWAY_BUDGET) * 100
        
        if heygen_usage:
            heygen_percentage = (heygen_usage['estimated_cost'] / config.HEYGEN_BUDGET) * 100
        
        # Check Railway budget
        if railway_percentage >= 90:
            return False, f"🚨 We're experiencing such high demand that we've reached our infrastructure capacity! We're working on expanding and will be back soon with even better service!"
        
        # Check HeyGen budget  
        if heygen_percentage >= 90:
            return False, f"🎬 MyAvatar is so popular that we've used up our video generation capacity for this period! We're increasing our limits and will be back with more video creation power soon!"
        
        # Warning at 80%
        if railway_percentage >= 80 or heygen_percentage >= 80:
            logger.warning(f"🚨 BUDGET WARNING: Railway {railway_percentage:.1f}%, HeyGen {heygen_percentage:.1f}%")
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error checking budget limits: {e}")
        return True, None

def get_system_stats() -> Dict:
    """Get current system usage stats"""
    try:
        stats = {}
        
        # Total users
        total_users_result = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        stats['total_users'] = total_users_result['count'] if total_users_result else 0
        
        # Total videos
        total_videos_result = execute_query("SELECT COUNT(*) as count FROM videos", fetch_one=True)
        stats['total_videos'] = total_videos_result['count'] if total_videos_result else 0
        
        # Today's registrations
        today = date.today()
        daily_users_result = execute_query(
            "SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = %s", 
            (today,), 
            fetch_one=True
        )
        stats['daily_registrations'] = daily_users_result['count'] if daily_users_result else 0
        
        # Usage percentages
        stats['users_percentage'] = round((stats['total_users'] / config.MAX_TOTAL_USERS) * 100, 1)
        stats['daily_percentage'] = round((stats['daily_registrations'] / config.MAX_DAILY_REGISTRATIONS) * 100, 1)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        return {
            'total_users': 0,
            'total_videos': 0,
            'daily_registrations': 0,
            'users_percentage': 0,
            'daily_percentage': 0
        }

async def log_api_cost_event(service: str, endpoint: str, cost_estimate: float):
    """Log API calls for cost tracking"""
    try:
        execute_query(
            """INSERT INTO api_usage_log (service, endpoint, cost_estimate, created_at) 
               VALUES (%s, %s, %s, %s)""",
            (service, endpoint, cost_estimate, datetime.now())
        )
    except Exception as e:
        logger.error(f"Error logging API call: {e}")
