"""
Standalone test script to check HeyGen voices
Reads API key from .env file automatically
"""
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv  # Import dotenv

# Load environment variables from .env file
load_dotenv()

def log_test(message):
    """Simple logging for test"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def test_heygen_voices():
    """
    Test script to check all voices in HeyGen
    """
    # Get API key from .env file
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        log_test("ERROR: HEYGEN_API_KEY not found in .env file")
        log_test("Make sure your .env file has: HEYGEN_API_KEY=your_actual_key")
        return None
    
    log_test(f"Found API key: {api_key[:10]}...{api_key[-4:]}")
    
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json"
    }
    
    try:
        log_test("=== TESTING HEYGEN VOICES API ===")
        response = requests.get(
            "https://api.heygen.com/v2/voices",
            headers=headers,
            timeout=30
        )
        
        log_test(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            voices_data = response.json()
            
            if voices_data.get("error") is None and "data" in voices_data:
                voices = voices_data["data"].get("voices", [])
                log_test(f"\n=== FOUND {len(voices)} TOTAL VOICES ===")
                
                # Look for custom voices and specific names
                custom_voices = []
                mogens_voices = []
                phoenix_voices = []
                
                for i, voice in enumerate(voices):
                    voice_name = voice.get("name", "")
                    voice_name_lower = voice_name.lower()
                    voice_id = voice.get("voice_id", "")
                    language = voice.get("language", "")
                    gender = voice.get("gender", "")
                    
                    # Check for your specific avatars
                    is_mogens = "mogens" in voice_name_lower
                    is_phoenix = "phønix" in voice_name_lower or "phoenix" in voice_name_lower
                    
                    # Check if custom voice (not standard HeyGen voices)
                    standard_names = ["sara", "paul", "rex", "angela", "daisy", "monica", "lina", "cheerful", "friendly"]
                    is_custom = not any(standard in voice_name_lower for standard in standard_names)
                    
                    log_test(f"\nVoice {i+1}:")
                    log_test(f"  Name: {voice_name}")
                    log_test(f"  ID: {voice_id}")
                    log_test(f"  Language: {language}")
                    log_test(f"  Gender: {gender}")
                    
                    if is_mogens:
                        mogens_voices.append(voice)
                        log_test(f"  *** MOGENS VOICE FOUND! ***")
                    
                    if is_phoenix:
                        phoenix_voices.append(voice)
                        log_test(f"  *** PHØNIX VOICE FOUND! ***")
                    
                    if is_custom:
                        custom_voices.append(voice)
                        log_test(f"  Type: CUSTOM/CLONED VOICE")
                    else:
                        log_test(f"  Type: Standard HeyGen Voice")
                
                # Summary
                log_test(f"\n=== SUMMARY ===")
                log_test(f"Total Voices: {len(voices)}")
                log_test(f"Custom/Cloned Voices: {len(custom_voices)}")
                log_test(f"Mogens Voices: {len(mogens_voices)}")
                log_test(f"Phønix Voices: {len(phoenix_voices)}")
                
                # Show results for each avatar
                if mogens_voices:
                    log_test(f"\n=== MOGENS VOICE DETAILS ===")
                    for voice in mogens_voices:
                        log_test(f"Voice ID: {voice.get('voice_id')}")
                        log_test(f"Name: {voice.get('name')}")
                        log_test(f"Use this ID for Mogens avatar!")
                
                if phoenix_voices:
                    log_test(f"\n=== PHØNIX VOICE DETAILS ===")
                    for voice in phoenix_voices:
                        log_test(f"Voice ID: {voice.get('voice_id')}")
                        log_test(f"Name: {voice.get('name')}")
                        log_test(f"Use this ID for Phønix avatar!")
                
                if custom_voices and not mogens_voices and not phoenix_voices:
                    log_test(f"\n=== OTHER CUSTOM VOICES ===")
                    for voice in custom_voices[:5]:  # Show first 5
                        log_test(f"  - {voice.get('name')} (ID: {voice.get('voice_id')})")
                
                # Return first found custom voice or None
                if mogens_voices:
                    return mogens_voices[0].get('voice_id')
                elif phoenix_voices:
                    return phoenix_voices[0].get('voice_id')
                elif custom_voices:
                    return custom_voices[0].get('voice_id')
                else:
                    log_test(f"\n=== NO CUSTOM VOICES FOUND ===")
                    log_test("Only standard HeyGen voices available")
                    return None
                    
            else:
                log_test(f"ERROR in API response: {voices_data}")
                return None
        else:
            log_test(f"API request failed: {response.status_code}")
            log_test(f"Response text: {response.text}")
            return None
            
    except Exception as e:
        log_test(f"Exception during test: {e}")
        return None

def test_heygen_avatars():
    """
    Test script to see all avatars
    """
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        log_test("ERROR: HEYGEN_API_KEY not found in .env file")
        return
    
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json"
    }
    
    try:
        log_test("\n=== TESTING HEYGEN AVATARS API ===")
        response = requests.get(
            "https://api.heygen.com/v2/avatars",
            headers=headers,
            timeout=30
        )
        
        log_test(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            avatars_data = response.json()
            
            if avatars_data.get("error") is None and "data" in avatars_data:
                avatars = avatars_data["data"].get("avatars", [])
                log_test(f"\n=== FOUND {len(avatars)} TOTAL AVATARS ===")
                
                your_avatars = ["b5038ba7bd9b4d94ac6b5c9ea70f8d28", "5cbf622acb164d92bc0d816fc60a2be6", "cf04ddd19e254f15a6bcc015631a79f2"]
                
                for i, avatar in enumerate(avatars):
                    avatar_name = avatar.get("avatar_name", "")
                    avatar_id = avatar.get("avatar_id", "")
                    
                    log_test(f"\nAvatar {i+1}:")
                    log_test(f"  Name: {avatar_name}")
                    log_test(f"  ID: {avatar_id}")
                    log_test(f"  Gender: {avatar.get('gender', 'Unknown')}")
                    
                    # Check if this matches your known avatars
                    if avatar_id in your_avatars:
                        log_test(f"  *** YOUR AVATAR! ***")
                        if avatar_id == "b5038ba7bd9b4d94ac6b5c9ea70f8d28":
                            log_test(f"  (This is Mogens from your database)")
                
            else:
                log_test(f"ERROR in avatars API response: {avatars_data}")
        else:
            log_test(f"Avatars API request failed: {response.status_code}")
            log_test(f"Response text: {response.text}")
            
    except Exception as e:
        log_test(f"Exception during avatars test: {e}")

if __name__ == "__main__":
    log_test("=== HeyGen Voice & Avatar Test (from .env) ===")
    
    # Test both APIs
    voice_id = test_heygen_voices()
    test_heygen_avatars()
    
    if voice_id:
        log_test(f"\n=== SUCCESS! ===")
        log_test(f"Found voice_id: {voice_id}")
        log_test(f"You can use this in your text-to-video API calls")
    else:
        log_test(f"\n=== NEXT STEPS ===")
        log_test(f"Check if you have cloned voices set up in HeyGen")
        log_test(f"Or use a default voice for now")
    
    log_test("\nTest completed!")

def log_test(message):
    """Simple logging for test"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def test_heygen_voices_internal(api_key):
    """
    Test script to find voices in HeyGen
    """
    log_test(f"Testing with API key: {api_key[:10]}...{api_key[-4:]}")
    
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json"
    }
    
    try:
        log_test("=== TESTING HEYGEN VOICES API ===")
        response = requests.get(
            "https://api.heygen.com/v2/voices",
            headers=headers,
            timeout=30
        )
        
        log_test(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            voices_data = response.json()
            
            if voices_data.get("error") is None and "data" in voices_data:
                voices = voices_data["data"].get("voices", [])
                log_test(f"\n=== FOUND {len(voices)} TOTAL VOICES ===")
                
                # Categorize voices
                custom_voices = []
                standard_voices = []
                
                for i, voice in enumerate(voices):
                    voice_name = voice.get("name", "").lower()
                    voice_id = voice.get("voice_id", "")
                    language = voice.get("language", "")
                    gender = voice.get("gender", "")
                    
                    log_test(f"\nVoice {i+1}:")
                    log_test(f"  Name: {voice.get('name', 'Unknown')}")
                    log_test(f"  ID: {voice_id}")
                    log_test(f"  Language: {language}")
                    log_test(f"  Gender: {gender}")
                    
                    # Categorize voices
                    standard_names = ["sara", "paul", "rex", "angela", "daisy", "monica", "lina"]
                    if any(standard in voice_name for standard in standard_names):
                        standard_voices.append(voice)
                        log_test(f"  Type: Standard HeyGen Voice")
                    else:
                        custom_voices.append(voice)
                        log_test(f"  Type: *** CUSTOM/CLONED VOICE ***")
                
                # Summary
                log_test(f"\n=== SUMMARY ===")
                log_test(f"Total Voices: {len(voices)}")
                log_test(f"Standard HeyGen Voices: {len(standard_voices)}")
                log_test(f"Custom/Cloned Voices: {len(custom_voices)}")
                
                if custom_voices:
                    log_test(f"\n=== CUSTOM VOICES FOUND ===")
                    for voice in custom_voices:
                        log_test(f"Voice: {voice.get('name')} (ID: {voice.get('voice_id')})")
                    
                    return custom_voices[0].get('voice_id')  # Return first custom voice
                else:
                    log_test(f"\n=== NO CUSTOM VOICES FOUND ===")
                    return None
                    
            else:
                log_test(f"ERROR in API response: {voices_data}")
                return None
        else:
            log_test(f"API request failed: {response.status_code}")
            log_test(f"Response text: {response.text}")
            return None
            
    except Exception as e:
        log_test(f"Exception during test: {e}")
        return None

def test_find_specific_voice(api_key, search_name):
    """
    Search for a specific voice by name
    """
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json"
    }
    
    try:
        log_test(f"Searching for voice matching: {search_name}")
        response = requests.get(
            "https://api.heygen.com/v2/voices",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            voices_data = response.json()
            
            if voices_data.get("error") is None and "data" in voices_data:
                voices = voices_data["data"].get("voices", [])
                
                # Search for matching voice
                matches = []
                for voice in voices:
                    voice_name = voice.get("name", "").lower()
                    if search_name.lower() in voice_name:
                        matches.append(voice)
                        log_test(f"MATCH FOUND: {voice.get('name')} (ID: {voice.get('voice_id')})")
                
                if matches:
                    return matches[0].get('voice_id')
                else:
                    log_test(f"No voice found matching '{search_name}'")
                    log_test("Available custom voices:")
                    for voice in voices:
                        voice_name = voice.get("name", "").lower()
                        standard_names = ["sara", "paul", "rex", "angela", "daisy", "monica", "lina"]
                        if not any(standard in voice_name for standard in standard_names):
                            log_test(f"  - {voice.get('name')} (ID: {voice.get('voice_id')})")
                    return None
            else:
                log_test(f"ERROR in API response: {voices_data}")
                return None
        else:
            log_test(f"API request failed: {response.status_code}")
            return None
            
    except Exception as e:
        log_test(f"Exception during search: {e}")
        return None

def test_heygen_avatars_internal(api_key):
    """
    Test script to see all avatars
    """
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json"
    }
    
    try:
        log_test("\n=== TESTING HEYGEN AVATARS API ===")
        response = requests.get(
            "https://api.heygen.com/v2/avatars",
            headers=headers,
            timeout=30
        )
        
        log_test(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            avatars_data = response.json()
            
            if avatars_data.get("error") is None and "data" in avatars_data:
                avatars = avatars_data["data"].get("avatars", [])
                log_test(f"\n=== FOUND {len(avatars)} TOTAL AVATARS ===")
                
                for i, avatar in enumerate(avatars):
                    avatar_name = avatar.get("avatar_name", "")
                    avatar_id = avatar.get("avatar_id", "")
                    
                    log_test(f"\nAvatar {i+1}:")
                    log_test(f"  Name: {avatar_name}")
                    log_test(f"  ID: {avatar_id}")
                    log_test(f"  Gender: {avatar.get('gender', 'Unknown')}")
                    
                    # Check if this matches the known database avatar
                    if avatar_id == "b5038ba7bd9b4d94ac6b5c9ea70f8d28":
                        log_test(f"  *** MATCHES DATABASE AVATAR ID! ***")
                
            else:
                log_test(f"ERROR in avatars API response: {avatars_data}")
        else:
            log_test(f"Avatars API request failed: {response.status_code}")
            log_test(f"Response text: {response.text}")
            
    except Exception as e:
        log_test(f"Exception during avatars test: {e}")

def test_heygen_voices():
    """Legacy function - now redirects to internal version"""
    return test_heygen_voices_internal(os.getenv("HEYGEN_API_KEY"))

def test_heygen_avatars():
    """Legacy function - now redirects to internal version"""
    return test_heygen_avatars_internal(os.getenv("HEYGEN_API_KEY"))

if __name__ == "__main__":
    log_test("=== HeyGen Voice & Avatar Test ===")
    
    # Get API key from user
    api_key = input("Enter your HeyGen API key: ").strip()
    if not api_key:
        log_test("ERROR: No API key provided")
        exit()
    
    # Update the test functions to use the provided API key
    def test_heygen_voices_with_key():
        return test_heygen_voices_internal(api_key)
    
    def test_heygen_avatars_with_key():
        return test_heygen_avatars_internal(api_key)
    
    # Get avatar info from user
    print("\nWhat would you like to test?")
    print("1. Search for a specific avatar's voice")
    print("2. List all voices")
    print("3. List all avatars")
    print("4. Full test (all of the above)")
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == "1":
        avatar_name = input("Enter avatar name to search for: ").strip()
        log_test(f"Searching for avatar: {avatar_name}")
        voice_id = test_find_specific_voice(api_key, avatar_name)
        if voice_id:
            log_test(f"\n=== SUCCESS! ===")
            log_test(f"Found voice_id for {avatar_name}: {voice_id}")
        else:
            log_test(f"\n=== NO VOICE FOUND ===")
            log_test(f"No voice found matching '{avatar_name}'")
            
    elif choice == "2":
        test_heygen_voices_internal(api_key)
        
    elif choice == "3":
        test_heygen_avatars_internal(api_key)
        
    elif choice == "4":
        voice_id = test_heygen_voices_internal(api_key)
        test_heygen_avatars_internal(api_key)
        
        if voice_id:
            log_test(f"\n=== SUCCESS! ===")
            log_test(f"Found voice_id: {voice_id}")
        else:
            log_test(f"\n=== NEXT STEPS ===")
            log_test(f"Check the voices and avatars listed above")
    else:
        log_test("Invalid choice")
    
    log_test("\nTest completed!")