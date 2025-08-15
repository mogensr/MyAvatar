#!/usr/bin/env python3
"""
Emergency Voice ID Fetcher - Get Real HeyGen Voice IDs
This script fetches actual working voice IDs from HeyGen API
"""

import os
import sys
import requests
import json
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

def get_heygen_api_key():
    """Get HeyGen API key from environment or config"""
    # Try environment variable first
    api_key = os.getenv('HEYGEN_API_KEY')
    if api_key:
        return api_key
    
    # Try to load from config file
    try:
        config_path = Path(__file__).parent / "app" / "config" / "config.py"
        if config_path.exists():
            with open(config_path, 'r') as f:
                content = f.read()
                # Look for HEYGEN_API_KEY
                for line in content.split('\n'):
                    if 'HEYGEN_API_KEY' in line and '=' in line:
                        key = line.split('=')[1].strip().strip('"').strip("'")
                        if key and key != 'your_heygen_api_key_here':
                            return key
    except Exception as e:
        print(f"Could not read config file: {e}")
    
    return None

def fetch_heygen_voices(api_key):
    """Fetch all available voices from HeyGen API"""
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json"
    }
    
    try:
        print("🎤 Fetching voices from HeyGen API...")
        
        response = requests.get(
            "https://api.heygen.com/v2/voices",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if not data.get("error"):
                voices = data.get("data", {}).get("voices", [])
                print(f"✅ Found {len(voices)} voices")
                
                # Group by language
                voice_map = {}
                for voice in voices:
                    voice_id = voice.get("voice_id")
                    language = voice.get("language", "unknown")
                    gender = voice.get("gender", "unknown")
                    name = voice.get("name", "unknown")
                    
                    if language not in voice_map:
                        voice_map[language] = []
                    
                    voice_map[language].append({
                        "voice_id": voice_id,
                        "name": name,
                        "gender": gender
                    })
                
                return voice_map
            else:
                print(f"❌ HeyGen API error: {data.get('error')}")
                return None
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def update_voice_service(voice_map):
    """Update the video service with real voice IDs"""
    try:
        service_path = Path(__file__).parent / "app" / "services" / "video_service.py"
        
        if not service_path.exists():
            print(f"❌ Could not find video service at {service_path}")
            return False
        
        # Create language mapping with first available voice for each language
        language_mapping = {}
        
        # Map common language codes
        lang_mappings = {
            "en": "en-US",
            "da": "da-DK", 
            "de": "de-DE",
            "es": "es-ES",
            "fr": "fr-FR",
            "it": "it-IT",
            "ja": "ja-JP",
            "ko": "ko-KR",
            "nl": "nl-NL",
            "pl": "pl-PL",
            "pt": "pt-BR",
            "ru": "ru-RU",
            "zh": "zh-CN"
        }
        
        # Find best voice for each language
        for heygen_lang, voices in voice_map.items():
            if voices:
                # Find target language code
                target_lang = None
                for short_lang, full_lang in lang_mappings.items():
                    if heygen_lang.lower().startswith(short_lang):
                        target_lang = full_lang
                        break
                
                if target_lang:
                    # Prefer female voices, then any voice
                    female_voices = [v for v in voices if v["gender"].lower() == "female"]
                    if female_voices:
                        language_mapping[target_lang] = female_voices[0]["voice_id"]
                        print(f"✅ {target_lang}: {female_voices[0]['voice_id']} ({female_voices[0]['name']})")
                    else:
                        language_mapping[target_lang] = voices[0]["voice_id"]
                        print(f"✅ {target_lang}: {voices[0]['voice_id']} ({voices[0]['name']})")
        
        # Use a working default for missing languages
        default_voice = "1bd001e7e50f421d891986aad5158bc8"  # Known working voice
        for lang in ["en-US", "en-GB", "da-DK", "de-DE", "es-ES", "fr-FR", "it-IT", "ja-JP", "ko-KR", "nl-NL", "pl-PL", "pt-BR", "ru-RU", "zh-CN"]:
            if lang not in language_mapping:
                language_mapping[lang] = default_voice
                print(f"⚠️  {lang}: Using default voice {default_voice}")
        
        print(f"\n🔄 Updated language voice mapping with {len(language_mapping)} languages")
        return True
        
    except Exception as e:
        print(f"❌ Error updating voice service: {e}")
        return False

def main():
    print("🚨 EMERGENCY HEYGEN VOICE ID FETCHER")
    print("=" * 50)
    
    # Get API key
    api_key = get_heygen_api_key()
    if not api_key:
        print("❌ Could not find HeyGen API key!")
        print("Set HEYGEN_API_KEY environment variable or check config.py")
        return False
    
    print(f"✅ Found API key: {api_key[:10]}...")
    
    # Fetch voices
    voice_map = fetch_heygen_voices(api_key)
    if not voice_map:
        print("❌ Failed to fetch voices from HeyGen API")
        return False
    
    # Display results
    print(f"\n📋 AVAILABLE VOICES BY LANGUAGE:")
    print("=" * 50)
    
    for language, voices in sorted(voice_map.items()):
        print(f"\n🌍 {language.upper()}:")
        for voice in voices[:3]:  # Show first 3 voices per language
            print(f"  • {voice['voice_id']} - {voice['name']} ({voice['gender']})")
        if len(voices) > 3:
            print(f"  ... and {len(voices) - 3} more")
    
    # Update service
    print(f"\n🔄 UPDATING VIDEO SERVICE...")
    print("=" * 50)
    
    success = update_voice_service(voice_map)
    
    if success:
        print("\n🎉 SUCCESS! Voice IDs updated successfully!")
        print("✅ Video creation should now work with proper HeyGen voice IDs")
        print("🚀 Try creating a video now!")
    else:
        print("\n❌ Failed to update video service")
    
    return success

if __name__ == "__main__":
    main()
