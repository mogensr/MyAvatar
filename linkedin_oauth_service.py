"""
LinkedIn OAuth Service - Professional LinkedIn Integration
Handles OAuth flow, token management, and LinkedIn API interactions
"""

import os
import requests
import secrets
import time
from typing import Dict, Optional, List
from urllib.parse import urlencode, parse_qs, urlparse
import logging

logger = logging.getLogger(__name__)

class LinkedInOAuthService:
    """Professional LinkedIn OAuth and API service"""
    
    def __init__(self):
        self.client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
        self.client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "")
        self.redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI", "https://app.myavatar.dk/auth/linkedin/callback")
        
        # LinkedIn OAuth URLs
        self.auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        self.api_base = "https://api.linkedin.com/v2"
        
        # Required scopes for posting and profile access
        self.scopes = [
            "r_liteprofile",
            "r_emailaddress", 
            "w_member_social",
            "rw_organization_admin"  # For company pages
        ]
    
    def generate_auth_url(self, user_id: int) -> Dict[str, str]:
        """Generate LinkedIn OAuth authorization URL"""
        try:
            # Generate secure state parameter
            state = f"{user_id}_{secrets.token_urlsafe(32)}"
            
            params = {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "state": state,
                "scope": " ".join(self.scopes)
            }
            
            auth_url = f"{self.auth_url}?{urlencode(params)}"
            
            logger.info(f"🔗 Generated LinkedIn auth URL for user {user_id}")
            
            return {
                "success": True,
                "auth_url": auth_url,
                "state": state
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to generate LinkedIn auth URL: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def exchange_code_for_token(self, code: str, state: str) -> Dict[str, any]:
        """Exchange authorization code for access token"""
        try:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            
            response = requests.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Get user profile info
                profile = self.get_user_profile(token_data["access_token"])
                
                logger.info(f"🔗 Successfully exchanged LinkedIn code for token")
                
                return {
                    "success": True,
                    "access_token": token_data["access_token"],
                    "expires_in": token_data.get("expires_in", 5184000),  # 60 days default
                    "profile": profile
                }
            else:
                logger.error(f"❌ LinkedIn token exchange failed: {response.text}")
                return {
                    "success": False,
                    "error": f"Token exchange failed: {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"❌ LinkedIn token exchange error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_user_profile(self, access_token: str) -> Dict[str, any]:
        """Get LinkedIn user profile information"""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Get basic profile
            profile_response = requests.get(
                f"{self.api_base}/people/~:(id,firstName,lastName,profilePicture(displayImage~:playableStreams))",
                headers=headers
            )
            
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                
                # Get email
                email_response = requests.get(
                    f"{self.api_base}/emailAddress?q=members&projection=(elements*(handle~))",
                    headers=headers
                )
                
                email = None
                if email_response.status_code == 200:
                    email_data = email_response.json()
                    if email_data.get("elements"):
                        email = email_data["elements"][0]["handle~"]["emailAddress"]
                
                return {
                    "id": profile_data["id"],
                    "first_name": profile_data["firstName"]["localized"].get("en_US", ""),
                    "last_name": profile_data["lastName"]["localized"].get("en_US", ""),
                    "email": email,
                    "profile_picture": self._extract_profile_picture(profile_data)
                }
            else:
                logger.error(f"❌ Failed to get LinkedIn profile: {profile_response.text}")
                return {}
                
        except Exception as e:
            logger.error(f"❌ LinkedIn profile fetch error: {e}")
            return {}
    
    def _extract_profile_picture(self, profile_data: Dict) -> Optional[str]:
        """Extract profile picture URL from LinkedIn response"""
        try:
            picture_data = profile_data.get("profilePicture", {}).get("displayImage~", {})
            elements = picture_data.get("elements", [])
            
            if elements:
                # Get the largest available image
                largest = max(elements, key=lambda x: x.get("data", {}).get("com.linkedin.digitalmedia.mediaartifact.StillImage", {}).get("storageSize", {}).get("width", 0))
                identifiers = largest.get("identifiers", [])
                if identifiers:
                    return identifiers[0].get("identifier")
            
            return None
            
        except Exception:
            return None
    
    def post_to_linkedin(self, access_token: str, content: Dict[str, any]) -> Dict[str, any]:
        """Post content to LinkedIn"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            }
            
            # Build LinkedIn post payload
            post_data = {
                "author": f"urn:li:person:{content['author_id']}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": content["text"]
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            # Add media if provided
            if content.get("media_url"):
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "VIDEO"
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [{
                    "status": "READY",
                    "description": {
                        "text": content.get("media_description", "")
                    },
                    "media": content["media_url"],
                    "title": {
                        "text": content.get("media_title", "")
                    }
                }]
            
            response = requests.post(
                f"{self.api_base}/ugcPosts",
                headers=headers,
                json=post_data
            )
            
            if response.status_code == 201:
                post_id = response.headers.get("x-restli-id")
                logger.info(f"🔗 Successfully posted to LinkedIn: {post_id}")
                
                return {
                    "success": True,
                    "post_id": post_id,
                    "post_url": f"https://www.linkedin.com/feed/update/{post_id}"
                }
            else:
                logger.error(f"❌ LinkedIn post failed: {response.text}")
                return {
                    "success": False,
                    "error": f"Post failed: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            logger.error(f"❌ LinkedIn post error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def validate_token(self, access_token: str) -> bool:
        """Validate if LinkedIn access token is still valid"""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(f"{self.api_base}/people/~", headers=headers)
            return response.status_code == 200
            
        except Exception:
            return False
    
    def get_company_pages(self, access_token: str) -> List[Dict[str, any]]:
        """Get user's company pages for posting"""
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = requests.get(
                f"{self.api_base}/organizationAcls?q=roleAssignee&role=ADMINISTRATOR&projection=(elements*(organization~(id,name,logoV2(original~:playableStreams))))",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                companies = []
                
                for element in data.get("elements", []):
                    org = element.get("organization~", {})
                    companies.append({
                        "id": org.get("id"),
                        "name": org.get("name"),
                        "logo": self._extract_company_logo(org)
                    })
                
                return companies
            else:
                logger.error(f"❌ Failed to get company pages: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Company pages fetch error: {e}")
            return []
    
    def _extract_company_logo(self, org_data: Dict) -> Optional[str]:
        """Extract company logo URL"""
        try:
            logo_data = org_data.get("logoV2", {}).get("original~", {})
            elements = logo_data.get("elements", [])
            
            if elements:
                identifiers = elements[0].get("identifiers", [])
                if identifiers:
                    return identifiers[0].get("identifier")
            
            return None
            
        except Exception:
            return None

# Global LinkedIn service instance
linkedin_service = LinkedInOAuthService()
