"""
LinkedIn AI Content Generator - Video Analysis & Content Creation
Analyzes videos and generates professional LinkedIn posts with AI
"""

import os
import requests
import json
import time
import logging
from typing import Dict, List, Optional, Tuple
import openai
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class LinkedInAIContentGenerator:
    """AI-powered content generation for LinkedIn from video analysis"""
    
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
        
        # Content templates and styles
        self.post_styles = {
            "professional": {
                "tone": "professional and authoritative",
                "emojis": ["💼", "📈", "🎯", "✅", "🚀", "💡"],
                "hashtags": ["#Leadership", "#Business", "#Professional", "#Growth", "#Innovation"]
            },
            "thought_leader": {
                "tone": "insightful and thought-provoking",
                "emojis": ["🧠", "💭", "🔍", "📊", "🌟", "🎓"],
                "hashtags": ["#ThoughtLeadership", "#Insights", "#Strategy", "#Future", "#Trends"]
            },
            "casual": {
                "tone": "friendly and approachable",
                "emojis": ["😊", "👍", "🎉", "💪", "🔥", "✨"],
                "hashtags": ["#Motivation", "#Tips", "#Learning", "#Community", "#Success"]
            },
            "storytelling": {
                "tone": "narrative and engaging",
                "emojis": ["📖", "🎬", "💫", "🌈", "🎭", "🔮"],
                "hashtags": ["#Story", "#Journey", "#Experience", "#Lessons", "#Growth"]
            }
        }
        
        # Industry-specific hashtags
        self.industry_hashtags = {
            "technology": ["#Tech", "#AI", "#Innovation", "#DigitalTransformation", "#SaaS"],
            "marketing": ["#Marketing", "#DigitalMarketing", "#ContentMarketing", "#SocialMedia", "#Branding"],
            "finance": ["#Finance", "#Investment", "#FinTech", "#Economy", "#Business"],
            "healthcare": ["#Healthcare", "#MedTech", "#Wellness", "#Innovation", "#PatientCare"],
            "education": ["#Education", "#Learning", "#Training", "#Development", "#Knowledge"],
            "consulting": ["#Consulting", "#Strategy", "#Business", "#Transformation", "#Advisory"],
            "sales": ["#Sales", "#B2B", "#Revenue", "#Growth", "#CustomerSuccess"]
        }
    
    def analyze_video_content(self, video_path: str, video_title: str = "", video_description: str = "") -> Dict[str, any]:
        """Analyze video content and extract key information"""
        try:
            analysis_result = {
                "title": video_title,
                "description": video_description,
                "key_topics": [],
                "sentiment": "neutral",
                "industry": "general",
                "duration_category": "short",
                "content_type": "presentation"
            }
            
            # Basic analysis from title and description
            if video_title or video_description:
                content_text = f"{video_title} {video_description}".lower()
                
                # Detect industry
                for industry, keywords in {
                    "technology": ["tech", "ai", "software", "digital", "innovation"],
                    "marketing": ["marketing", "brand", "campaign", "social", "content"],
                    "finance": ["finance", "investment", "money", "financial", "economy"],
                    "healthcare": ["health", "medical", "patient", "care", "wellness"],
                    "education": ["education", "learning", "training", "teach", "knowledge"],
                    "consulting": ["consulting", "strategy", "advisory", "business"],
                    "sales": ["sales", "revenue", "customer", "client", "growth"]
                }.items():
                    if any(keyword in content_text for keyword in keywords):
                        analysis_result["industry"] = industry
                        break
                
                # Detect key topics
                topic_keywords = {
                    "leadership": ["leader", "management", "team", "guide"],
                    "innovation": ["innovation", "creative", "new", "future"],
                    "growth": ["growth", "scale", "expand", "increase"],
                    "strategy": ["strategy", "plan", "approach", "method"],
                    "success": ["success", "achieve", "accomplish", "win"],
                    "tips": ["tip", "advice", "how to", "guide"],
                    "trends": ["trend", "future", "emerging", "next"],
                    "case_study": ["case", "example", "story", "experience"]
                }
                
                for topic, keywords in topic_keywords.items():
                    if any(keyword in content_text for keyword in keywords):
                        analysis_result["key_topics"].append(topic)
                
                # Detect sentiment
                positive_words = ["success", "great", "amazing", "excellent", "best", "win", "achieve"]
                negative_words = ["problem", "issue", "challenge", "difficult", "fail", "mistake"]
                
                positive_count = sum(1 for word in positive_words if word in content_text)
                negative_count = sum(1 for word in negative_words if word in content_text)
                
                if positive_count > negative_count:
                    analysis_result["sentiment"] = "positive"
                elif negative_count > positive_count:
                    analysis_result["sentiment"] = "negative"
            
            logger.info(f"✅ Video content analyzed: {analysis_result['industry']} industry, {len(analysis_result['key_topics'])} topics")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ Video analysis error: {e}")
            return {
                "title": video_title,
                "description": video_description,
                "key_topics": ["general"],
                "sentiment": "neutral",
                "industry": "general",
                "duration_category": "short",
                "content_type": "presentation"
            }
    
    def generate_linkedin_post(self, video_analysis: Dict, style: str = "professional", custom_prompt: str = "") -> Dict[str, any]:
        """Generate LinkedIn post content based on video analysis"""
        try:
            if not self.openai_api_key:
                return self._generate_template_post(video_analysis, style)
            
            # Build AI prompt
            style_config = self.post_styles.get(style, self.post_styles["professional"])
            industry_tags = self.industry_hashtags.get(video_analysis["industry"], [])
            
            prompt = f"""
            Create a compelling LinkedIn post based on this video analysis:
            
            Video Title: {video_analysis['title']}
            Description: {video_analysis['description']}
            Industry: {video_analysis['industry']}
            Key Topics: {', '.join(video_analysis['key_topics'])}
            Sentiment: {video_analysis['sentiment']}
            
            Style Requirements:
            - Tone: {style_config['tone']}
            - Length: 150-300 words
            - Include 3-5 relevant emojis from: {', '.join(style_config['emojis'])}
            - Include 5-8 hashtags mixing general and industry-specific
            - Add a clear call-to-action
            - Make it engaging and professional
            
            {custom_prompt if custom_prompt else ''}
            
            Format the response as JSON with these fields:
            - "post_text": the main LinkedIn post content
            - "emojis": array of emojis used
            - "hashtags": array of hashtags used
            - "cta": the call-to-action text
            - "key_message": one-sentence summary of the post
            """
            
            # Call OpenAI API
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional LinkedIn content creator who generates engaging, high-performing posts."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            # Parse AI response
            ai_content = response.choices[0].message.content
            
            try:
                # Try to parse as JSON
                content_data = json.loads(ai_content)
            except json.JSONDecodeError:
                # Fallback: extract content manually
                content_data = self._parse_ai_response(ai_content)
            
            # Enhance with additional suggestions
            content_data["style"] = style
            content_data["industry"] = video_analysis["industry"]
            content_data["generated_at"] = datetime.now().isoformat()
            
            logger.info(f"✅ AI LinkedIn post generated: {style} style, {len(content_data.get('hashtags', []))} hashtags")
            return content_data
            
        except Exception as e:
            logger.error(f"❌ AI post generation error: {e}")
            return self._generate_template_post(video_analysis, style)
    
    def _generate_template_post(self, video_analysis: Dict, style: str) -> Dict[str, any]:
        """Generate template-based LinkedIn post when AI is unavailable"""
        style_config = self.post_styles.get(style, self.post_styles["professional"])
        industry_tags = self.industry_hashtags.get(video_analysis["industry"], [])
        
        # Template post based on video content
        title = video_analysis.get("title", "My Latest Video")
        topics = video_analysis.get("key_topics", ["insights"])
        
        post_templates = {
            "professional": f"🎯 Just shared some valuable insights in my latest video: '{title}'\n\nKey takeaways:\n• {topics[0] if topics else 'Professional insights'}\n• Actionable strategies for growth\n• Real-world applications\n\nWhat's your experience with {topics[0] if topics else 'this topic'}? Share your thoughts below! 👇",
            
            "thought_leader": f"💭 Been reflecting on {topics[0] if topics else 'industry trends'} lately...\n\nIn my latest video '{title}', I explore:\n🔍 Current market dynamics\n📊 Data-driven insights\n🌟 Future implications\n\nThe landscape is evolving rapidly. What trends are you seeing in your field?",
            
            "casual": f"Hey LinkedIn! 👋\n\nJust dropped a new video: '{title}' 🎬\n\nCovered some really cool stuff about {topics[0] if topics else 'growth strategies'}. Always love sharing what I've learned with this amazing community!\n\nCheck it out and let me know what you think! 💪",
            
            "storytelling": f"📖 Here's a story that changed my perspective...\n\nIn my latest video '{title}', I share:\n✨ Personal experiences\n🎭 Lessons learned\n🌈 Key insights\n\nSometimes the best learning comes from real stories. What's a story that shaped your professional journey?"
        }
        
        post_text = post_templates.get(style, post_templates["professional"])
        
        # Combine hashtags
        all_hashtags = style_config["hashtags"][:3] + industry_tags[:3] + ["#Video", "#Content"]
        
        return {
            "post_text": post_text,
            "emojis": style_config["emojis"][:4],
            "hashtags": all_hashtags[:8],
            "cta": "Share your thoughts below! 👇",
            "key_message": f"Sharing insights about {topics[0] if topics else 'professional growth'}",
            "style": style,
            "industry": video_analysis["industry"],
            "generated_at": datetime.now().isoformat()
        }
    
    def _parse_ai_response(self, ai_content: str) -> Dict[str, any]:
        """Parse AI response when JSON parsing fails"""
        try:
            # Extract post text (usually the main content)
            post_text = ai_content.strip()
            
            # Extract hashtags
            hashtags = re.findall(r'#\w+', ai_content)
            
            # Extract emojis
            emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+')
            emojis = emoji_pattern.findall(ai_content)
            
            # Clean post text (remove hashtags from main text)
            clean_text = re.sub(r'#\w+', '', post_text).strip()
            
            return {
                "post_text": clean_text,
                "emojis": list(set(emojis))[:5],
                "hashtags": list(set(hashtags))[:8],
                "cta": "What are your thoughts?",
                "key_message": "Video insights and professional content"
            }
            
        except Exception:
            return {
                "post_text": ai_content[:500],
                "emojis": ["💼", "🎯"],
                "hashtags": ["#Professional", "#Content"],
                "cta": "Share your thoughts!",
                "key_message": "Professional video content"
            }
    
    def generate_multiple_variations(self, video_analysis: Dict, styles: List[str] = None) -> List[Dict[str, any]]:
        """Generate multiple LinkedIn post variations"""
        if not styles:
            styles = ["professional", "thought_leader", "casual"]
        
        variations = []
        for style in styles:
            if style in self.post_styles:
                variation = self.generate_linkedin_post(video_analysis, style)
                variation["variation_name"] = f"{style.title()} Style"
                variations.append(variation)
        
        return variations
    
    def suggest_posting_times(self, industry: str = "general") -> List[Dict[str, str]]:
        """Suggest optimal posting times for LinkedIn"""
        # Industry-specific optimal times (based on LinkedIn best practices)
        optimal_times = {
            "general": [
                {"day": "Tuesday", "time": "10:00 AM", "reason": "Peak engagement"},
                {"day": "Wednesday", "time": "11:00 AM", "reason": "High activity"},
                {"day": "Thursday", "time": "1:00 PM", "reason": "Lunch break browsing"}
            ],
            "technology": [
                {"day": "Tuesday", "time": "9:00 AM", "reason": "Tech professionals active"},
                {"day": "Wednesday", "time": "2:00 PM", "reason": "Afternoon engagement"},
                {"day": "Thursday", "time": "11:00 AM", "reason": "Mid-week peak"}
            ],
            "finance": [
                {"day": "Monday", "time": "8:00 AM", "reason": "Week start planning"},
                {"day": "Wednesday", "time": "12:00 PM", "reason": "Market hours"},
                {"day": "Friday", "time": "3:00 PM", "reason": "Week wrap-up"}
            ]
        }
        
        return optimal_times.get(industry, optimal_times["general"])
    
    def analyze_hashtag_performance(self, hashtags: List[str]) -> Dict[str, any]:
        """Analyze and score hashtag effectiveness"""
        hashtag_scores = {}
        
        # Popular LinkedIn hashtags with engagement scores
        popular_hashtags = {
            "#Leadership": 95, "#Innovation": 90, "#Technology": 88,
            "#Business": 85, "#Marketing": 82, "#Growth": 80,
            "#Success": 78, "#Motivation": 75, "#Tips": 72,
            "#Strategy": 85, "#AI": 92, "#DigitalTransformation": 87
        }
        
        for hashtag in hashtags:
            score = popular_hashtags.get(hashtag, 50)  # Default score
            hashtag_scores[hashtag] = {
                "score": score,
                "category": "high" if score >= 80 else "medium" if score >= 60 else "low"
            }
        
        return {
            "hashtag_scores": hashtag_scores,
            "average_score": sum(h["score"] for h in hashtag_scores.values()) / len(hashtag_scores) if hashtag_scores else 0,
            "recommendations": self._get_hashtag_recommendations(hashtags)
        }
    
    def _get_hashtag_recommendations(self, current_hashtags: List[str]) -> List[str]:
        """Get hashtag recommendations to improve engagement"""
        high_performing = ["#Leadership", "#Innovation", "#Growth", "#Success", "#AI", "#Strategy"]
        recommendations = []
        
        for tag in high_performing:
            if tag not in current_hashtags:
                recommendations.append(tag)
                if len(recommendations) >= 3:
                    break
        
        return recommendations

# Global AI content generator instance
linkedin_ai_generator = LinkedInAIContentGenerator()
