import os
import requests

def download_heygen_video(video_url: str, save_path: str) -> bool:
    """
    Downloads a HeyGen-generated video from the provided public URL and saves it to the given path.
    Returns True if successful, False otherwise.
    """
    try:
        response = requests.get(video_url, stream=True, timeout=60)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"✅ Video downloaded and saved to {save_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to download video: {e}")
        return False

if __name__ == "__main__":
    # Example usage
    url = os.environ.get("HEYGEN_VIDEO_URL")
    path = "downloaded_heygen_video.mp4"
    if url:
        download_heygen_video(url, path)
    else:
        print("Set HEYGEN_VIDEO_URL env variable to the video URL you want to download.")
