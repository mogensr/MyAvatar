"""
🍹 Video Background Replacer - CLOUDINARY INTEGRATION VERSION
Using MatAnyone from Hugging Face + MediaPipe + Audio Preservation + Cloudinary Storage
"""

import streamlit as st
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import time
import subprocess
import requests
import base64
from datetime import datetime

# Cloudinary imports
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

# ============================================================================
# STREAMLIT CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Video Background Replacement",
    page_icon="🍹",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Configure Cloudinary
try:
    cloudinary.config(
        cloud_name=st.secrets["CLOUDINARY_CLOUD_NAME"],
        api_key=st.secrets["CLOUDINARY_API_KEY"],
        api_secret=st.secrets["CLOUDINARY_API_SECRET"]
    )
    CLOUDINARY_ENABLED = True
except Exception as e:
    CLOUDINARY_ENABLED = False
    st.warning(f"⚠️ Cloudinary not configured: {e}")

# Custom CSS for clean iframe embedding
st.markdown("""
<style>
    /* Hide Streamlit elements for clean iframe */
    .main > div { padding-top: 1rem; }
    .stDeployButton { display: none; }
    header[data-testid="stHeader"] { display: none; }
    .stMainBlockContainer { padding-top: 1rem; }
    
    /* Main header styling */
    .main-header {
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1.5rem;
    }
    
    /* Box styling */
    .processing-box {
        border: 2px solid #4ECDC4;
        border-radius: 15px;
        padding: 20px;
        margin: 20px 0;
        background: rgba(78, 205, 196, 0.1);
    }
    
    .success-box {
        background: linear-gradient(45deg, #4CAF50, #45a049);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 20px 0;
    }
    
    .save-to-myavatar-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 15px;
        margin: 20px 0;
        text-align: center;
    }
    
    /* Mobile responsive */
    @media (max-width: 768px) {
        .main-header { font-size: 1.8rem; }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def upload_to_cloudinary(video_path, title="BackgroundFX Video"):
    """Upload video to Cloudinary and return URL"""
    try:
        if not CLOUDINARY_ENABLED:
            return None, "Cloudinary not configured"
        
        # Upload video to Cloudinary
        upload_result = cloudinary.uploader.upload(
            video_path,
            resource_type="video",
            folder="myavatar/backgroundfx",
            public_id=f"bg_{int(datetime.now().timestamp())}",
            overwrite=True,
            quality="auto",
            format="mp4"
        )
        
        video_url = upload_result['secure_url']
        thumbnail_url = video_url.replace('.mp4', '.jpg')
        duration = upload_result.get('duration', 8)
        
        return {
            'video_url': video_url,
            'thumbnail_url': thumbnail_url,
            'duration': duration,
            'public_id': upload_result['public_id']
        }, None
        
    except Exception as e:
        return None, f"Cloudinary upload failed: {str(e)}"

def save_to_myavatar_metadata(cloudinary_data, title="BackgroundFX Video", user_token=None):
    """Save video metadata to MyAvatar after Cloudinary upload"""
    try:
        # MyAvatar metadata API endpoint
        api_url = "https://myavatar-production.up.railway.app/api/save-video-metadata"
        
        # Create metadata payload
        metadata = {
            "title": title,
            "video_url": cloudinary_data['video_url'],
            "thumbnail_url": cloudinary_data['thumbnail_url'],
            "duration": cloudinary_data['duration'],
            "format": "16:9",
            "source": "BackgroundFX",
            "cloudinary_id": cloudinary_data['public_id'],
            "created_at": datetime.now().isoformat()
        }
        
        # Headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "HF-Space-BackgroundFX/2.0"
        }
        
        # Add auth if available
        if user_token:
            headers["Authorization"] = f"Bearer {user_token}"
        
        # Make API call
        response = requests.post(
            api_url, 
            json=metadata, 
            headers=headers, 
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            if result.get('success'):
                return True, "✅ Video saved to My Videos!"
            else:
                return False, f"❌ Save failed: {result.get('message', 'Unknown error')}"
        else:
            return False, f"❌ API Error: {response.status_code} - {response.text}"
            
    except requests.exceptions.Timeout:
        return False, "❌ Save timeout - please try again"
    except requests.exceptions.ConnectionError:
        return False, "❌ Connection error - MyAvatar may be down"
    except Exception as e:
        return False, f"❌ Save error: {str(e)}"

def process_video_with_matanyone(video_path, image_path, progress_callback=None):
    """Main video processing pipeline using MatAnyone"""
    
    try:
        # Import required libraries - ONLY when needed
        if progress_callback:
            progress_callback(0.05, "Loading dependencies...")
        
        try:
            from matanyone import InferenceCore
        except ImportError as e:
            raise Exception(f"MatAnyone import failed: {str(e)}. Check if MatAnyone is properly installed.")
        
        try:
            import mediapipe as mp
        except ImportError as e:
            raise Exception(f"MediaPipe import failed: {str(e)}. Check if MediaPipe is properly installed.")
        
        # Initialize processors
        if progress_callback:
            progress_callback(0.1, "Loading MatAnyone model...")
        
        try:
            processor = InferenceCore("PeiqingYang/MatAnyone")
        except Exception as e:
            raise Exception(f"Failed to load MatAnyone model: {str(e)}")
        
        try:
            mp_selfie = mp.solutions.selfie_segmentation
            selfie_segmentation = mp_selfie.SelfieSegmentation(model_selection=1)
        except Exception as e:
            raise Exception(f"Failed to initialize MediaPipe: {str(e)}")
        
        # Create mask from first frame
        if progress_callback:
            progress_callback(0.2, "Creating segmentation mask...")
        
        cap = cv2.VideoCapture(video_path)
        ret, first_frame = cap.read()
        cap.release()
        
        if not ret:
            raise Exception("Could not read video file")
        
        # Generate mask with MediaPipe
        rgb_frame = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB)
        results = selfie_segmentation.process(rgb_frame)
        mask = (results.segmentation_mask > 0.5).astype(np.uint8) * 255
        
        # Save mask
        mask_path = f"temp_mask_{int(time.time())}.png"
        cv2.imwrite(mask_path, mask)
        
        # Process with MatAnyone
        if progress_callback:
            progress_callback(0.4, "Running MatAnyone extraction...")
        
        try:
            foreground_path, alpha_path = processor.process_video(
                input_path=video_path,
                mask_path=mask_path,
                output_path="output"
            )
        except Exception as e:
            raise Exception(f"MatAnyone processing failed: {str(e)}")
        
        # Apply new background
        if progress_callback:
            progress_callback(0.6, "Applying new background...")
        
        # Read background image
        bg_image = cv2.imread(image_path)
        if bg_image is None:
            raise Exception("Could not read background image")
        
        # Open videos
        cap_fg = cv2.VideoCapture(foreground_path)
        cap_alpha = cv2.VideoCapture(alpha_path)
        cap_orig = cv2.VideoCapture(video_path)
        
        # Get video properties
        fps = int(cap_orig.get(cv2.CAP_PROP_FPS))
        width = int(cap_orig.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap_orig.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap_orig.get(cv2.CAP_PROP_FRAME_COUNT))
        cap_orig.release()
        
        # Resize background
        bg_resized = cv2.resize(bg_image, (width, height))
        
        # Create output video
        temp_output = f"temp_output_{int(time.time())}.avi"
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))
        
        # Process frames
        frame_count = 0
        while True:
            ret_fg, frame_fg = cap_fg.read()
            ret_alpha, frame_alpha = cap_alpha.read()
            
            if not ret_fg or not ret_alpha:
                break
            
            # Convert alpha to single channel
            if len(frame_alpha.shape) == 3:
                alpha = cv2.cvtColor(frame_alpha, cv2.COLOR_BGR2GRAY)
            else:
                alpha = frame_alpha
            
            # Normalize and blend
            alpha_norm = alpha.astype(float) / 255.0
            result = np.zeros_like(frame_fg, dtype=float)
            
            for c in range(3):
                result[:,:,c] = (frame_fg[:,:,c] * alpha_norm + 
                               bg_resized[:,:,c] * (1 - alpha_norm))
            
            out.write(result.astype(np.uint8))
            frame_count += 1
            
            if progress_callback and frame_count % 30 == 0:
                progress = 0.6 + (0.2 * frame_count / total_frames)
                progress_callback(progress, f"Processing frame {frame_count}/{total_frames}")
        
        # Release resources
        cap_fg.release()
        cap_alpha.release()
        out.release()
        
        # Add audio and optimize
        if progress_callback:
            progress_callback(0.8, "Adding audio and optimizing...")
        
        final_output = f"final_output_{int(time.time())}.mp4"
        audio_path = f"temp_audio_{int(time.time())}.wav"
        
        # Try to preserve audio with ffmpeg
        try:
            # Extract audio
            extract_cmd = [
                'ffmpeg', '-y', '-i', video_path,
                '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2',
                audio_path
            ]
            
            audio_result = subprocess.run(extract_cmd, capture_output=True, text=True)
            has_audio = audio_result.returncode == 0 and os.path.exists(audio_path)
            
            # Combine video with audio (or just optimize)
            if has_audio:
                combine_cmd = [
                    'ffmpeg', '-y',
                    '-i', temp_output,
                    '-i', audio_path,
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '192k',
                    '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart',
                    final_output
                ]
            else:
                combine_cmd = [
                    'ffmpeg', '-y',
                    '-i', temp_output,
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart',
                    final_output
                ]
            
            result = subprocess.run(combine_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                output_path = final_output
            else:
                # Fallback to moviepy
                raise Exception(f"FFmpeg failed: {result.stderr}")
                
        except Exception as ffmpeg_error:
            # Try moviepy as fallback
            if progress_callback:
                progress_callback(0.85, "FFmpeg failed, trying MoviePy...")
            
            try:
                import moviepy.editor as mpy
                
                original_clip = mpy.VideoFileClip(video_path)
                processed_clip = mpy.VideoFileClip(temp_output)
                
                if original_clip.audio is not None:
                    final_clip = processed_clip.set_audio(original_clip.audio)
                else:
                    final_clip = processed_clip
                
                final_clip.write_videofile(final_output, codec='libx264', audio_codec='aac')
                
                original_clip.close()
                processed_clip.close()
                if original_clip.audio is not None:
                    final_clip.close()
                
                output_path = final_output
                
            except Exception as moviepy_error:
                # Last resort - use video without audio
                if progress_callback:
                    progress_callback(0.9, "Audio processing failed, using video only...")
                output_path = temp_output
        
        # Cleanup temporary files
        for temp_file in [mask_path, foreground_path, alpha_path]:
            if os.path.exists(temp_file) and temp_file != output_path:
                try:
                    os.remove(temp_file)
                except:
                    pass
        
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except:
                pass
        
        if progress_callback:
            progress_callback(1.0, "Complete!")
        
        return output_path
        
    except Exception as e:
        # Better error reporting
        import traceback
        error_msg = f"Processing failed: {str(e)}"
        if progress_callback:
            progress_callback(0, f"Error: {error_msg}")
        raise Exception(f"{error_msg}\n\nFull traceback:\n{traceback.format_exc()}")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    # Header
    st.markdown('<h1 class="main-header">🍹 Video Background Replacer</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.1rem; color: #666; margin-bottom: 2rem;">AI-Powered Background Replacement with Audio Preservation + Cloud Storage</p>', unsafe_allow_html=True)
    
    # Show Cloudinary status
    if CLOUDINARY_ENABLED:
        st.success("☁️ Cloudinary connected - videos can be saved to My Videos!")
    else:
        st.warning("⚠️ Cloudinary not available - download only mode")
    
    # Show system info for debugging
    with st.expander("🔧 System Info (for debugging)"):
        st.code(f"""
Python version: {os.sys.version}
OpenCV available: {cv2.__version__}
Cloudinary enabled: {CLOUDINARY_ENABLED}
Current directory: {os.getcwd()}
Available files: {os.listdir('.')}
        """)
    
    # File upload section
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎬 Upload Your Video")
        video_file = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'avi', 'mov'],
            key="video_upload"
        )
        if video_file:
            st.success("✅ Video loaded!")
            st.video(video_file)
    
    with col2:
        st.markdown("### 🖼️ Upload Background Image")
        image_file = st.file_uploader(
            "Choose a background image",
            type=['png', 'jpg', 'jpeg'],
            key="bg_upload"
        )
        if image_file:
            st.success("✅ Background loaded!")
            st.image(image_file, width=300)
    
    # Process button
    if video_file and image_file:
        if st.button("🍹 PROCESS VIDEO", type="primary", use_container_width=True):
            
            # Save uploaded files
            video_path = f"temp_video_{int(time.time())}.mp4"
            image_path = f"temp_image_{int(time.time())}.jpg"
            
            with open(video_path, "wb") as f:
                f.write(video_file.read())
            
            # Save and convert image
            img = Image.open(image_file)
            img = img.convert('RGB')
            img.save(image_path)
            
            # Process video
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(progress, message):
                progress_bar.progress(progress)
                status_text.text(message)
            
            try:
                output_path = process_video_with_matanyone(
                    video_path, 
                    image_path,
                    update_progress
                )
                
                # Read result
                with open(output_path, 'rb') as f:
                    video_data = f.read()
                
                # Store in session state
                st.session_state['video_result'] = video_data
                st.session_state['video_path'] = output_path
                st.session_state['video_filename'] = f"background_replaced_{int(time.time())}.mp4"
                
                # Clear progress
                progress_bar.empty()
                status_text.empty()
                
                # Show success
                st.markdown('<div class="success-box">🎉 Video Successfully Processed!</div>', unsafe_allow_html=True)
                
                # Display video
                st.markdown("### 🎬 Your Processed Video:")
                st.video(video_data)
                
                # Action buttons
                col1, col2 = st.columns(2)
                
                with col1:
                    st.download_button(
                        label="⬇️ Download Video",
                        data=video_data,
                        file_name=st.session_state['video_filename'],
                        mime="video/mp4",
                        use_container_width=True
                    )
                
                with col2:
                    if CLOUDINARY_ENABLED:
                        if st.button("💾 Save to My Videos", type="secondary", use_container_width=True):
                            with st.spinner("Uploading to cloud..."):
                                # Step 1: Upload to Cloudinary
                                cloudinary_data, error = upload_to_cloudinary(
                                    st.session_state['video_path'],
                                    "BackgroundFX Video"
                                )
                                
                                if cloudinary_data:
                                    st.success("☁️ Uploaded to Cloudinary!")
                                    
                                    # Step 2: Save metadata to MyAvatar
                                    with st.spinner("Saving to My Videos..."):
                                        success, message = save_to_myavatar_metadata(
                                            cloudinary_data,
                                            "BackgroundFX Video"
                                        )
                                    
                                    if success:
                                        st.success(message)
                                        st.balloons()
                                        st.info(f"🌍 Video URL: {cloudinary_data['video_url']}")
                                    else:
                                        st.error(message)
                                        st.info(f"Video is still available on cloud: {cloudinary_data['video_url']}")
                                else:
                                    st.error(f"❌ Cloud upload failed: {error}")
                    else:
                        st.button("💾 Save to My Videos", disabled=True, help="Cloudinary not configured", use_container_width=True)
                
                # Info box
                if CLOUDINARY_ENABLED:
                    st.markdown("""
                    <div class="save-to-myavatar-box">
                        <h3 style="margin: 0 0 10px 0;">💾 Save to MyAvatar</h3>
                        <p style="margin: 0;">Upload to Cloudinary and add to your MyAvatar video library!</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("ℹ️ To enable 'Save to My Videos', configure Cloudinary in your Hugging Face Spaces secrets.")
                
                # Cleanup
                for temp_file in [video_path, image_path]:
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                            
            except Exception as e:
                st.error(f"❌ Processing failed: {str(e)}")
                with st.expander("Show error details"):
                    st.code(str(e))
    
    elif not video_file or not image_file:
        st.info("👆 Upload both a video and background image to start!")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 10px;">
        <p><small>🍹 Powered by MatAnyone AI | Audio Preserved | Cloudinary Storage | Connected to MyAvatar</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
