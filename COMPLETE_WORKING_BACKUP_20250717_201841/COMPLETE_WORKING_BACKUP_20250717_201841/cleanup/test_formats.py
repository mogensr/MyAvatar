import os
from heygen_api import create_video_from_audio_file

def test_video_formats():
    # Set these variables to appropriate test values
    api_key = os.environ.get('HEYGEN_API_KEY', 'your-api-key')
    avatar_id = 'test-avatar-id'  # Use a valid avatar_id for testing
    audio_file = 'test-audio.mp3'  # Use a valid audio file for testing
    
    # Test 16:9 format
    print("\n=== Testing 16:9 format ===")
    result_16_9 = create_video_from_audio_file(
        api_key=api_key,
        avatar_id=avatar_id,
        audio_file_path=audio_file,
        video_format="16:9"
    )
    print(f"16:9 Result: {result_16_9}")
    
    # Test 9:16 format
    print("\n=== Testing 9:16 format ===")
    result_9_16 = create_video_from_audio_file(
        api_key=api_key,
        avatar_id=avatar_id,
        audio_file_path=audio_file,
        video_format="9:16"
    )
    print(f"9:16 Result: {result_9_16}")
    
    # Test 1:1 format
    print("\n=== Testing 1:1 format ===")
    result_1_1 = create_video_from_audio_file(
        api_key=api_key,
        avatar_id=avatar_id,
        audio_file_path=audio_file,
        video_format="1:1"
    )
    print(f"1:1 Result: {result_1_1}")

if __name__ == "__main__":
    test_video_formats()
