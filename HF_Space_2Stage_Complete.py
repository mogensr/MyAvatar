"""
🍹 Video Background Replacer - 2-STAGE PIPELINE VERSION
FIXED: Restored the working 2-stage approach:
1. MatAnyone: Original video → Green screen video
2. Chroma key: Green screen → Custom background
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
    
    .upload-slot {
        background: rgba(255, 255, 255, 0.8);
        border: 2px dashed #ccc;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        margin: 10px 0;
        min-height: 300px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        transition: all 0.3s ease;
    }
    
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
    
    .stage-indicator {
        background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
        color: white;
        padding: 10px;
        border-radius: 8px;
        margin: 10px 0;
        text-align: center;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

class BackgroundReplacer2Stage:
    def __init__(self):
        """Initialize the 2-stage background replacer with MatAnyone"""
        self.use_matanyone = False
        self.use_mediapipe = False
        self.matanyone_processor = None
        self.matanyone_model = None
        self.device = None
        
        print("🔄 Starting 2-Stage AI model initialization...")
        
        # Try MatAnyone first (Stage 1: Person segmentation)
        try:
            print("🚀 Attempting to load MatAnyone for Stage 1...")
            from matanyone.inference.inference_core import InferenceCore
            from matanyone.utils.get_default_model import get_matanyone_model
            from matanyone.utils.device import get_default_device
            
            print("📦 MatAnyone imported successfully, initializing processor...")
            
            # Get device
            self.device = get_default_device()
            
            # Load MatAnyone model (auto-downloads if needed)
            self.matanyone_model = get_matanyone_model(None, self.device)
            
            # Initialize processor with CORRECT API
            self.matanyone_processor = InferenceCore(self.matanyone_model, cfg=self.matanyone_model.cfg)
            
            self.use_matanyone = True
            print("✅ MatAnyone AI loaded successfully for 2-stage processing!")
            
        except ImportError as e:
            print(f"⚠️ MatAnyone not found ({str(e)}), trying MediaPipe...")
            self._init_mediapipe()
        except Exception as e:
            print(f"⚠️ MatAnyone failed to load ({str(e)}), trying MediaPipe...")
            self._init_mediapipe()
    
    def _init_mediapipe(self):
        """Initialize MediaPipe as fallback for Stage 1"""
        try:
            import mediapipe as mp
            self.mp_selfie_segmentation = mp.solutions.selfie_segmentation
            self.selfie_segmentation = self.mp_selfie_segmentation.SelfieSegmentation(model_selection=1)
            self.use_mediapipe = True
            print("✅ MediaPipe AI loaded successfully for 2-stage processing!")
        except ImportError:
            print("📱 Using basic segmentation for 2-stage processing")
    
    def create_simple_mask(self, frame):
        """Create a simple person mask using basic detection"""
        # Convert to HSV for better detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Basic skin tone and clothing detection (simplified)
        lower_person = np.array([0, 20, 70])
        upper_person = np.array([20, 255, 255])
        
        mask = cv2.inRange(hsv, lower_person, upper_person)
        
        # Clean up mask
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Convert to 3-channel
        mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        
        return mask

    def stage1_create_green_screen(self, frame, is_first_frame=False, mask=None):
        """STAGE 1: Create green screen video using MatAnyone/MediaPipe"""
        
        if self.use_matanyone:
            return self._stage1_matanyone(frame, is_first_frame, mask)
        elif self.use_mediapipe:
            return self._stage1_mediapipe(frame)
        else:
            return self._stage1_basic(frame)
    
    def _stage1_matanyone(self, frame, is_first_frame=False, mask=None):
        """Stage 1 with MatAnyone: Person segmentation → Green screen"""
        try:
            # Convert frame to tensor format
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = frame
            
            # Convert to tensor and normalize
            frame_tensor = torch.from_numpy(frame_rgb).permute(2, 0, 1).float() / 255.0
            frame_tensor = frame_tensor.to(self.device)
            
            if is_first_frame and mask is not None:
                # First frame: provide mask
                mask_tensor = torch.from_numpy(mask).float().to(self.device)
                if len(mask_tensor.shape) == 3:
                    mask_tensor = mask_tensor[:, :, 0]
                
                objects = [1]
                output_prob = self.matanyone_processor.step(frame_tensor, mask_tensor, objects=objects)
                output_prob = self.matanyone_processor.step(frame_tensor, first_frame_pred=True)
            else:
                # Subsequent frames
                output_prob = self.matanyone_processor.step(frame_tensor)
            
            # Convert output to mask
            alpha_mask = self.matanyone_processor.output_prob_to_mask(output_prob)
            alpha_mask = alpha_mask.cpu().numpy()
            
            if len(alpha_mask.shape) == 2:
                alpha_mask = np.stack([alpha_mask] * 3, axis=-1)
            
            # Ensure mask is in [0,1] range
            alpha_mask = np.clip(alpha_mask, 0, 1).astype(np.float32)
            
            # Create green screen background
            green_screen = np.full_like(frame, [0, 255, 0], dtype=np.uint8)  # Pure green (BGR)
            
            # Composite person on green screen
            green_screen_frame = frame * alpha_mask + green_screen * (1 - alpha_mask)
            
            return green_screen_frame.astype(np.uint8)
            
        except Exception as e:
            print(f"MatAnyone Stage 1 failed: {e}, using fallback")
            return self._stage1_basic(frame)
    
    def _stage1_mediapipe(self, frame):
        """Stage 1 with MediaPipe: Person segmentation → Green screen"""
        try:
            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process with MediaPipe
            results = self.selfie_segmentation.process(rgb_frame)
            
            if results.segmentation_mask is not None:
                # Convert segmentation mask to 3-channel
                alpha_mask = results.segmentation_mask
                alpha_mask = np.stack([alpha_mask] * 3, axis=-1).astype(np.float32)
            else:
                alpha_mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
            
            # Create green screen background
            green_screen = np.full_like(frame, [0, 255, 0], dtype=np.uint8)  # Pure green (BGR)
            
            # Composite person on green screen
            green_screen_frame = frame * alpha_mask + green_screen * (1 - alpha_mask)
            
            return green_screen_frame.astype(np.uint8)
            
        except Exception as e:
            print(f"MediaPipe Stage 1 failed: {e}, using fallback")
            return self._stage1_basic(frame)
    
    def _stage1_basic(self, frame):
        """Stage 1 basic fallback: Simple segmentation → Green screen"""
        # Use simple mask
        mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
        
        # Create green screen background
        green_screen = np.full_like(frame, [0, 255, 0], dtype=np.uint8)  # Pure green (BGR)
        
        # Composite person on green screen
        green_screen_frame = frame * mask + green_screen * (1 - mask)
        
        return green_screen_frame.astype(np.uint8)

    def stage2_chroma_key_replace(self, green_screen_frame, background_image):
        """STAGE 2: Replace green screen with custom background using chroma key"""
        try:
            # Convert to HSV for better green screen detection
            hsv = cv2.cvtColor(green_screen_frame, cv2.COLOR_BGR2HSV)
            
            # Define green screen range (optimized for pure green)
            lower_green = np.array([35, 40, 40])   # Lower bound for green
            upper_green = np.array([85, 255, 255]) # Upper bound for green
            
            # Create mask for green screen areas
            green_mask = cv2.inRange(hsv, lower_green, upper_green)
            
            # Smooth the mask to avoid harsh edges
            kernel = np.ones((3,3), np.uint8)
            green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
            green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel)
            
            # Apply Gaussian blur for smoother edges
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
                os.unlink(stage1_path)
                os.unlink(output_path)
            except:
                pass
            raise e

def main():
    # Compact header for iframe
    st.markdown('<h1 class="main-header">🍹 Video Background Replacer</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.1rem; color: #666; margin-bottom: 2rem;">2-Stage AI Processing: Person Segmentation → Green Screen → Custom Background</p>', unsafe_allow_html=True)
    
    # Initialize the 2-stage background replacer
    if 'replacer' not in st.session_state:
        with st.spinner('🔄 Loading 2-Stage AI Processing System...'):
            st.session_state.replacer = BackgroundReplacer2Stage()
    
    # Show initialization status
    if hasattr(st.session_state.replacer, 'use_matanyone') and st.session_state.replacer.use_matanyone:
        st.success('🚀 MatAnyone AI Ready - 2-Stage Ultimate Quality!')
    elif hasattr(st.session_state.replacer, 'use_mediapipe') and st.session_state.replacer.use_mediapipe:
        st.success('🎯 MediaPipe AI Ready - 2-Stage Good Quality!')
    else:
        st.info('📱 Basic 2-Stage Processing Ready')
    
    # Show 2-stage process explanation
    st.markdown("""
    <div class="processing-box">
        <h4>🔄 2-Stage Processing Pipeline:</h4>
        <p><strong>Stage 1:</strong> AI extracts person from video → Creates clean green screen video</p>
        <p><strong>Stage 2:</strong> Chroma key replacement → Green screen becomes your custom background</p>
        <p><em>This approach ensures the highest quality and most reliable results!</em></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Compact upload section
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎬 Upload Your Video")
        uploaded_video = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'avi', 'mov', 'mkv'],
            key="video_upload",
            help="Upload the video you want to process"
        )
        
        if uploaded_video:
            st.video(uploaded_video)
    
    with col2:
        st.markdown("### 🖼️ Upload Background Image")
        uploaded_background = st.file_uploader(
            "Choose background image",
            type=['jpg', 'jpeg', 'png', 'bmp'],
            key="bg_upload",
            help="Upload the background you want to use"
        )
        
        if uploaded_background:
            st.image(uploaded_background, caption="Background Preview")
    
    # Processing section
    if uploaded_video and uploaded_background:
        st.markdown("---")
        st.markdown("### 🚀 Ready for 2-Stage Processing!")
        
        # Process button
        if st.button("🍹 START 2-STAGE PROCESSING", key="process_button", use_container_width=True):
            # Save uploaded files
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_video:
                tmp_video.write(uploaded_video.read())
                video_path = tmp_video.name
            
            background_image = Image.open(uploaded_background)
            
            # Create containers for processing stages
            result_container = st.container()
            
            with result_container:
                st.markdown('<div class="processing-box">', unsafe_allow_html=True)
                st.markdown("### 🔄 2-Stage Processing in Progress...")
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                stage_indicator = st.empty()
                
                def update_progress(stage, progress, frame_count, total_frames, message):
                    progress_bar.progress(progress)
                    status_text.text(f"{message}")
                    
                    if stage == "stage1":
                        stage_indicator.markdown('<div class="stage-indicator">🎬 STAGE 1: Creating Green Screen Video</div>', unsafe_allow_html=True)
                    elif stage == "stage2":
                        stage_indicator.markdown('<div class="stage-indicator">🖼️ STAGE 2: Applying Custom Background</div>', unsafe_allow_html=True)
                
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
