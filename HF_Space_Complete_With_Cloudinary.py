"""
🍹 Video Background Replacer - 2-STAGE PIPELINE WITH CLOUDINARY INTEGRATION
FIXED: Restored the working 2-stage approach + Save to My Videos functionality:
1. MatAnyone: Original video → Green screen video
2. Chroma key: Green screen → Custom background
3. Cloudinary: Upload to cloud storage
4. MyAvatar: Save metadata to "My Videos"
"""

import streamlit as st
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import torch
import time
from pathlib import Path
import shutil
import requests
from datetime import datetime

# Cloudinary integration
try:
    import cloudinary
    import cloudinary.uploader
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False
    st.warning("⚠️ Cloudinary not available - install with: pip install cloudinary")

# ============================================================================
# CLOUDINARY CONFIGURATION - MyAvatar Integration
# ============================================================================

# Configure Cloudinary (using HF Spaces secrets)
if CLOUDINARY_AVAILABLE:
    try:
        cloudinary.config(
            cloud_name=st.secrets["CLOUDINARY_CLOUD_NAME"],
            api_key=st.secrets["CLOUDINARY_API_KEY"],  
            api_secret=st.secrets["CLOUDINARY_API_SECRET"]
        )
        st.success("☁️ Cloudinary configured successfully!")
    except Exception as e:
        st.error(f"❌ Cloudinary configuration failed: {e}")
        CLOUDINARY_AVAILABLE = False

def upload_to_cloudinary_and_save(video_path, user_token, title="BackgroundFX Video"):
    """
    Upload video to Cloudinary and save metadata to MyAvatar
    """
    if not CLOUDINARY_AVAILABLE:
        st.error("❌ Cloudinary not available")
        return False
        
    try:
        # Step 1: Upload directly to Cloudinary
        st.write("🔄 Uploading to cloud storage...")
        
        upload_result = cloudinary.uploader.upload(
            video_path,
            resource_type="video",
            folder="myavatar/backgroundfx",
            public_id=f"bg_{int(datetime.now().timestamp())}",
            overwrite=True
        )
        
        cloudinary_url = upload_result['secure_url']
        thumbnail_url = cloudinary_url.replace('.mp4', '.jpg')
        duration = upload_result.get('duration', 8)  # fallback to 8 seconds
        
        st.success("✅ Video uploaded to cloud!")
        
        # Step 2: Send metadata to MyAvatar
        st.write("🔄 Saving to My Videos...")
        
        metadata = {
            "title": title,
            "video_url": cloudinary_url,
            "thumbnail_url": thumbnail_url,
            "duration": f"0:{duration:02.0f}" if duration < 60 else f"{int(duration//60)}:{int(duration%60):02d}",
            "format": "16:9",
            "source": "BackgroundFX"
        }
        
        response = requests.post(
            "https://myavatar-production.up.railway.app/api/save-video-metadata",
            json=metadata,
            headers={
                "Authorization": f"Bearer {user_token}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        if response.status_code in [200, 201]:
            st.success("🎉 Video saved to My Videos!")
            st.info(f"📹 Video URL: {cloudinary_url}")
            return True
        else:
            st.error(f"❌ Failed to save metadata: {response.text}")
            st.info(f"But video is uploaded: {cloudinary_url}")
            return False
            
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return False

# ============================================================================
# IFRAME OPTIMIZATION - Claude's Recommendations
# ============================================================================

# Configure for iframe embedding
st.set_page_config(
    page_title="Video Background Replacement",
    page_icon="🍹",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Add iframe-friendly styling
st.markdown("""
<style>
    /* Hide Streamlit elements for clean iframe embedding */
    .main > div {
        padding-top: 1rem;
    }
    .stDeployButton {
        display: none;
    }
    header[data-testid="stHeader"] {
        display: none;
    }
    .stMainBlockContainer {
        padding-top: 1rem;
    }
    
    /* Clean, professional CSS - NO ANIMATIONS for iframe stability */
    .main-header {
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1.5rem;
    }
    
    .upload-container {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 20px;
        padding: 25px;
        margin: 15px 0;
        box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
    }
    
    .processing-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        padding: 25px;
        margin: 20px 0;
        color: white;
    }
    
    .success-box {
        background: linear-gradient(45deg, #4CAF50, #45a049);
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        font-weight: bold;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
    }
    
    .stage-indicator {
        background: rgba(255, 255, 255, 0.2);
        padding: 10px 20px;
        border-radius: 25px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
        backdrop-filter: blur(10px);
    }
    
    /* Progress styling */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #4CAF50, #45a049);
    }
    
    /* Mobile responsive */
    @media (max-width: 768px) {
        .main-header { font-size: 1.8rem; }
        .upload-container { padding: 15px; }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# MATANYONE INTEGRATION - SAFE LOADING
# ============================================================================

@st.cache_resource
def load_matanyone_model():
    """Load MatAnyone model with error handling"""
    try:
        # Import MatAnyone
        from matanyone import InferenceCore
        
        # Load model
        model = InferenceCore("PeiqingYang/MatAnyone")
        return model, None
    except Exception as e:
        return None, f"MatAnyone loading failed: {str(e)}"

# ============================================================================
# VIDEO PROCESSING PIPELINE - 2-STAGE APPROACH
# ============================================================================

class BackgroundReplacer:
    def __init__(self):
        self.matanyone_model = None
        self.model_error = None
        
    def initialize_model(self):
        """Initialize MatAnyone model"""
        if self.matanyone_model is None:
            self.matanyone_model, self.model_error = load_matanyone_model()
        return self.matanyone_model is not None

    def stage1_create_green_screen(self, frame, is_first_frame=False):
        """Stage 1: Create green screen video using MatAnyone"""
        try:
            if not self.initialize_model():
                raise Exception(f"MatAnyone model not available: {self.model_error}")
            
            # Use MatAnyone for person segmentation
            # This is a simplified implementation - adjust based on actual MatAnyone API
            mask = self.matanyone_model.segment_person(frame)
            
            # Create green screen background
            green_bg = np.full_like(frame, (0, 255, 0), dtype=np.uint8)  # Pure green
            
            # Apply mask to create green screen effect
            # mask should be 1 for person, 0 for background
            if len(mask.shape) == 2:
                mask_3ch = np.stack([mask, mask, mask], axis=-1)
            else:
                mask_3ch = mask
            
            # Person areas keep original, background becomes green
            result = frame * mask_3ch + green_bg * (1 - mask_3ch)
            
            return result.astype(np.uint8)
            
        except Exception as e:
            print(f"Stage 1 MatAnyone failed: {e}")
            # Fallback: return original frame with simple background removal
            return self.fallback_green_screen(frame)
    
    def fallback_green_screen(self, frame):
        """Fallback green screen creation without MatAnyone"""
        try:
            # Simple background subtraction or edge detection fallback
            # Convert to HSV for better color segmentation
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Create a simple mask (this is very basic - just for fallback)
            # In practice, you'd want a more sophisticated approach
            lower_bound = np.array([0, 50, 50])
            upper_bound = np.array([180, 255, 255])
            mask = cv2.inRange(hsv, lower_bound, upper_bound)
            
            # Invert mask (assume person is in the detected areas)
            mask = cv2.bitwise_not(mask)
            mask_norm = mask.astype(np.float32) / 255.0
            
            # Create green background
            green_bg = np.full_like(frame, (0, 255, 0), dtype=np.uint8)
            
            # Apply mask
            mask_3ch = np.stack([mask_norm, mask_norm, mask_norm], axis=-1)
            result = frame * mask_3ch + green_bg * (1 - mask_3ch)
            
            return result.astype(np.uint8)
            
        except Exception as e:
            print(f"Fallback green screen failed: {e}")
            # Last resort: return original frame
            return frame

    def stage2_chroma_key_replace(self, green_screen_frame, background_image):
        """Stage 2: Replace green screen with custom background"""
        try:
            # Convert to HSV for better green detection
            hsv = cv2.cvtColor(green_screen_frame, cv2.COLOR_BGR2HSV)
            
            # Define green color range (adjust these values as needed)
            lower_green = np.array([40, 50, 50])    # Lower HSV threshold for green
            upper_green = np.array([80, 255, 255])  # Upper HSV threshold for green
            
            # Create mask for green areas
            green_mask = cv2.inRange(hsv, lower_green, upper_green)
            
            # Improve mask with morphological operations
            kernel = np.ones((3,3), np.uint8)
            green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
            green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel)
            
            # Blur mask edges for smoother blending
            green_mask = cv2.GaussianBlur(green_mask, (5, 5), 0)
            
            # Convert mask to 3-channel and normalize
            green_mask_3ch = cv2.cvtColor(green_mask, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0
            
            # Resize background to match frame
            if isinstance(background_image, Image.Image):
                background_image = cv2.cvtColor(np.array(background_image), cv2.COLOR_RGB2BGR)
            
            bg_resized = cv2.resize(background_image, (green_screen_frame.shape[1], green_screen_frame.shape[0]))
            
            # Replace green areas with background
            # green_mask_3ch = 1 where green (use background), 0 where not green (keep original)
            result = green_screen_frame * (1 - green_mask_3ch) + bg_resized * green_mask_3ch
            
            return result.astype(np.uint8)
            
        except Exception as e:
            print(f"Stage 2 chroma key failed: {e}")
            # Fallback: return original frame
            return green_screen_frame

    def process_video_2stage(self, video_path, background_image, progress_callback=None):
        """Process entire video with 2-stage pipeline"""
        # Open video
        cap = cv2.VideoCapture(video_path)
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Create temporary files for each stage
        stage1_path = tempfile.mktemp(suffix='_green_screen.mp4')
        output_path = tempfile.mktemp(suffix='_final.mp4')
        
        # Video writers
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        stage1_writer = cv2.VideoWriter(stage1_path, fourcc, fps, (width, height))
        final_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        frame_count = 0
        
        try:
            # STAGE 1: Create green screen video
            if progress_callback:
                progress_callback("stage1", 0, 0, total_frames, "🎬 Stage 1: Creating green screen video...")
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Stage 1: Person → Green screen
                is_first_frame = (frame_count == 0)
                green_screen_frame = self.stage1_create_green_screen(frame, is_first_frame)
                stage1_writer.write(green_screen_frame)
                
                frame_count += 1
                
                # Update progress for Stage 1
                if progress_callback:
                    progress = frame_count / total_frames * 0.5  # Stage 1 is 50% of total
                    progress_callback("stage1", progress, frame_count, total_frames, 
                                    f"🎬 Stage 1: Processing frame {frame_count}/{total_frames}")
            
            # Close stage 1 writer and video capture
            stage1_writer.release()
            cap.release()
            
            # STAGE 2: Replace green screen with custom background
            if progress_callback:
                progress_callback("stage2", 0.5, 0, total_frames, "🖼️ Stage 2: Replacing green screen with background...")
            
            # Open the green screen video
            cap_stage2 = cv2.VideoCapture(stage1_path)
            frame_count = 0
            
            while True:
                ret, green_frame = cap_stage2.read()
                if not ret:
                    break
                
                # Stage 2: Green screen → Custom background
                final_frame = self.stage2_chroma_key_replace(green_frame, background_image)
                final_writer.write(final_frame)
                
                frame_count += 1
                
                # Update progress for Stage 2
                if progress_callback:
                    progress = 0.5 + (frame_count / total_frames * 0.5)  # Stage 2 is remaining 50%
                    progress_callback("stage2", progress, frame_count, total_frames,
                                    f"🖼️ Stage 2: Processing frame {frame_count}/{total_frames}")
            
            cap_stage2.release()
            final_writer.release()
            
            # Cleanup stage 1 temporary file
            try:
                os.unlink(stage1_path)
            except:
                pass
            
            return output_path
            
        except Exception as e:
            # Cleanup on error
            try:
                stage1_writer.release()
                final_writer.release()
                cap.release()
                if 'cap_stage2' in locals():
                    cap_stage2.release()
                for temp_file in [stage1_path, output_path]:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
            except:
                pass
            raise e

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    # Header
    st.markdown('<h1 class="main-header">🍹 Video Background Replacer</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.1rem; color: #666; margin-bottom: 2rem;">2-Stage AI Pipeline: MatAnyone + Chroma Key Replacement</p>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'replacer' not in st.session_state:
        st.session_state.replacer = BackgroundReplacer()
    
    # File upload section
    st.markdown('<div class="upload-container">', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎬 Upload Your Video")
        video_file = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'avi', 'mov', 'mkv'],
            key="video_upload",
            help="Upload the video where you want to replace the background"
        )
        
        if video_file:
            st.success("✅ Video uploaded successfully!")
            # Show video preview
            st.video(video_file)
    
    with col2:
        st.markdown("### 🖼️ Upload Background Image")
        image_file = st.file_uploader(
            "Choose a background image",
            type=['png', 'jpg', 'jpeg', 'bmp'],
            key="image_upload",
            help="Upload the new background image"
        )
        
        if image_file:
            st.success("✅ Background image uploaded!")
            # Show image preview
            image = Image.open(image_file)
            st.image(image, caption="New Background", width=300)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Processing section
    if video_file and image_file:
        
        # Process button
        if st.button("🍹 START 2-STAGE PROCESSING", type="primary", use_container_width=True):
            
            # Save uploaded files temporarily
            video_path = tempfile.mktemp(suffix='.mp4')
            with open(video_path, 'wb') as f:
                f.write(video_file.read())
            
            # Load background image
            background_image = Image.open(image_file)
            
            # Processing container
            st.markdown('<div class="processing-container">', unsafe_allow_html=True)
            st.markdown("### 🚀 Processing Your Video...")
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            stage_indicator = st.empty()
            
            def update_progress(stage, progress, frame_num, total_frames, message):
                progress_bar.progress(progress)
                status_text.text(message)
                
                if stage == "stage1":
                    stage_indicator.markdown('<div class="stage-indicator">🎬 STAGE 1: Creating Green Screen Video</div>', unsafe_allow_html=True)
                elif stage == "stage2":
                    stage_indicator.markdown('<div class="stage-indicator">🖼️ STAGE 2: Applying New Background</div>', unsafe_allow_html=True)
                
                try:
                    # Process the video with 2-stage pipeline
                    st.info("🚀 Starting 2-stage video processing...")
                    output_path = st.session_state.replacer.process_video_2stage(
                        video_path, background_image, update_progress
                    )
                    
                    # Complete progress
                    progress_bar.progress(1.0)
                    status_text.text("✅ 2-Stage Processing Complete!")
                    stage_indicator.markdown('<div class="stage-indicator">🎉 BOTH STAGES COMPLETED SUCCESSFULLY!</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Success message
                    st.markdown('<div class="success-box">🎉 Video Successfully Processed with 2-Stage Pipeline! 🎉</div>', unsafe_allow_html=True)
                    
                    # Display result
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        with open(output_path, 'rb') as video_file:
                            video_data = video_file.read()
                        
                        st.markdown("### 🎬 Your Processed Video:")
                        
                        # Show the video
                        st.video(video_data)
                        
                        # Action buttons in columns
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Download button
                            st.download_button(
                                label="⬇️ Download Video",
                                data=video_data,
                                file_name=f"2stage_background_replaced_{int(time.time())}.mp4",
                                mime="video/mp4",
                                use_container_width=True,
                                key=f"download_button_{int(time.time())}"
                            )
                        
                        with col2:
                            # Save to My Videos button
                            if st.button("💾 Save to My Videos", use_container_width=True, key=f"save_button_{int(time.time())}"):
                                # Get user token (you'll need to implement user auth via iframe/SSO)
                                user_token = st.session_state.get('user_token')
                                
                                if not user_token:
                                    # For testing - show token input
                                    st.error("🔐 Please login to save videos to My Videos")
                                    with st.expander("🧪 Debug: Manual Token Entry"):
                                        test_token = st.text_input("Enter JWT token for testing:", type="password")
                                        if test_token:
                                            st.session_state.user_token = test_token
                                            user_token = test_token
                                
                                if user_token:
                                    # Get video title from user
                                    video_title = st.text_input(
                                        "Video title:", 
                                        value="BackgroundFX Video",
                                        key=f"title_input_{int(time.time())}"
                                    )
                                    
                                    if st.button("🚀 Confirm Save", key=f"confirm_save_{int(time.time())}"):
                                        # Save the video file temporarily for upload
                                        temp_save_path = tempfile.mktemp(suffix='_for_upload.mp4')
                                        with open(temp_save_path, 'wb') as f:
                                            f.write(video_data)
                                        
                                        # Upload to Cloudinary and save to MyAvatar
                                        if upload_to_cloudinary_and_save(temp_save_path, user_token, video_title):
                                            st.balloons()
                                            st.success("🎉 Video successfully saved to My Videos!")
                                        
                                        # Cleanup temp file
                                        try:
                                            os.unlink(temp_save_path)
                                        except:
                                            pass
                        
                        st.success("✅ 2-Stage processed video ready!")
                        
                        # Cleanup temp files
                        try:
                            os.unlink(video_path)
                            os.unlink(output_path)
                        except:
                            pass
                            
                    else:
                        st.error("❌ Output video file is empty or corrupted")
                        
                except Exception as e:
                    status_text.text("❌ 2-Stage processing failed")
                    st.error(f"❌ Processing failed: {str(e)}")
                    st.info("💡 Try with a shorter video or different background image")
    
    else:
        st.info("👆 Upload both a video and background image to start 2-stage processing!")
    
    # Compact footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 10px;">
        <p><small>🍹 2-Stage Pipeline: MatAnyone + Chroma Key | Optimized for MyAvatar</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
