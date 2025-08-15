"""
🍹 Video Background Replacer - FIXED VERSION (No JavaScript Errors)
Eliminates Streamlit DOM manipulation issues causing 'setIn' errors
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

# ============================================================================
# IFRAME OPTIMIZATION - Stable Configuration
# ============================================================================

st.set_page_config(
    page_title="Video Background Replacement",
    page_icon="🍹",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Stable CSS - NO complex animations or DOM manipulations
st.markdown("""
<style>
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
    
    .success-box {
        background: linear-gradient(45deg, #4CAF50, #45a049);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 20px 0;
    }
</style>
""", unsafe_allow_html=True)

class BackgroundReplacer:
    def __init__(self):
        """Initialize the background replacer with MatAnyone or MediaPipe"""
        self.use_matanyone = False
        self.use_mediapipe = False
        
        print("🔄 Starting AI model initialization...")
        
        # Try MatAnyone first (best quality)
        try:
            print("🚀 Attempting to load MatAnyone...")
            from matanyone import InferenceCore
            
            print("📦 MatAnyone imported successfully, initializing processor...")
            self.matanyone_processor = InferenceCore("PeiqingYang/MatAnyone")
            self.use_matanyone = True
            print("✅ MatAnyone AI loaded successfully!")
            
        except ImportError as e:
            print(f"⚠️ MatAnyone not found ({str(e)}), trying MediaPipe...")
            try:
                import mediapipe as mp
                self.mp_selfie_segmentation = mp.solutions.selfie_segmentation
                self.selfie_segmentation = self.mp_selfie_segmentation.SelfieSegmentation(model_selection=1)
                self.use_mediapipe = True
                print("✅ MediaPipe AI loaded successfully!")
            except ImportError:
                print("📱 Using basic background replacement")
        
        except Exception as e:
            print(f"⚠️ MatAnyone failed to load ({str(e)}), trying MediaPipe...")
            try:
                import mediapipe as mp
                self.mp_selfie_segmentation = mp.solutions.selfie_segmentation
                self.selfie_segmentation = self.mp_selfie_segmentation.SelfieSegmentation(model_selection=1)
                self.use_mediapipe = True
                print("✅ MediaPipe AI loaded successfully!")
            except ImportError:
                print("📱 Using basic background replacement")
    
    def create_simple_mask(self, frame):
        """Create a simple background mask using color detection"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_bg = np.array([0, 0, 0])
        upper_bg = np.array([180, 255, 100])
        mask = cv2.inRange(hsv, lower_bg, upper_bg)
        mask = cv2.bitwise_not(mask)
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        return mask

    def process_frame(self, frame, background_image):
        """Process a single frame with background replacement"""
        if self.use_matanyone:
            try:
                frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = self.matanyone_processor.infer(frame_pil)
                
                if hasattr(result, 'alpha') and result.alpha is not None:
                    mask = np.array(result.alpha)
                    if len(mask.shape) == 2:
                        mask = np.stack([mask] * 3, axis=-1)
                    mask = mask.astype(np.float32) / 255.0
                else:
                    mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
                
            except Exception as e:
                print(f"MatAnyone processing failed: {e}, using fallback")
                mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
                
        elif self.use_mediapipe:
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.selfie_segmentation.process(rgb_frame)
                
                if results.segmentation_mask is not None:
                    mask = results.segmentation_mask
                    mask = np.stack([mask] * 3, axis=-1).astype(np.float32)
                else:
                    mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
                    
            except Exception as e:
                print(f"MediaPipe processing failed: {e}, using fallback")
                mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
        else:
            mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
        
        bg_resized = cv2.resize(background_image, (frame.shape[1], frame.shape[0]))
        result = frame * mask + bg_resized * (1 - mask)
        return result.astype(np.uint8)

    def process_video(self, video_path, background_image, progress_callback=None):
        """Process entire video with background replacement"""
        if isinstance(background_image, Image.Image):
            background_image = cv2.cvtColor(np.array(background_image), cv2.COLOR_RGB2BGR)
        
        cap = cv2.VideoCapture(video_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        output_path = tempfile.mktemp(suffix='.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        frame_count = 0
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                processed_frame = self.process_frame(frame, background_image)
                out.write(processed_frame)
                
                frame_count += 1
                
                if progress_callback:
                    progress = frame_count / total_frames
                    progress_callback(progress, frame_count, total_frames)
        
        finally:
            cap.release()
            out.release()
        
        return output_path

def main():
    # Simple header
    st.markdown('<h1 class="main-header">🍹 Video Background Replacer</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.1rem; color: #666; margin-bottom: 2rem;">Replace your video background with AI!</p>', unsafe_allow_html=True)
    
    # Initialize replacer once
    if 'replacer' not in st.session_state:
        with st.spinner('🔄 Loading AI Processing Interface...'):
            st.session_state.replacer = BackgroundReplacer()
    
    # Show status
    if hasattr(st.session_state.replacer, 'use_matanyone') and st.session_state.replacer.use_matanyone:
        st.success('🚀 MatAnyone AI Ready - Ultimate Quality!')
    elif hasattr(st.session_state.replacer, 'use_mediapipe') and st.session_state.replacer.use_mediapipe:
        st.success('🎯 MediaPipe AI Ready - Good Quality!')
    else:
        st.info('📱 Basic Processing Ready')
    
    # Upload section
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎬 Upload Your Video")
        uploaded_video = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'avi', 'mov', 'mkv'],
            key="video_upload"
        )
        if uploaded_video:
            st.video(uploaded_video)
    
    with col2:
        st.markdown("### 🖼️ Upload Background Image")
        uploaded_background = st.file_uploader(
            "Choose background image",
            type=['jpg', 'jpeg', 'png', 'bmp'],
            key="bg_upload"
        )
        if uploaded_background:
            st.image(uploaded_background, caption="Background Preview")
    
    # Processing section - SIMPLIFIED to avoid DOM issues
    if uploaded_video and uploaded_background:
        st.markdown("---")
        st.markdown("### 🚀 Ready to Process!")
        
        if st.button("🍹 PROCESS VIDEO", key="process_button", use_container_width=True):
            # Save uploaded files
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_video:
                tmp_video.write(uploaded_video.read())
                video_path = tmp_video.name
            
            background_image = Image.open(uploaded_background)
            
            # Simple processing with stable progress
            st.markdown("### 🔄 Processing Your Video...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(progress, frame_count, total_frames):
                progress_bar.progress(progress)
                status_text.text(f"Processing frame {frame_count}/{total_frames} ({progress*100:.1f}%)")
            
            try:
                # Process the video
                output_path = st.session_state.replacer.process_video(
                    video_path, background_image, update_progress
                )
                
                # Complete progress
                progress_bar.progress(1.0)
                status_text.text("✅ Processing complete!")
                
                # Success message
                st.markdown('<div class="success-box">🎉 Video Successfully Processed! 🎉</div>', unsafe_allow_html=True)
                
                # Display result immediately
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    st.markdown("### 🎬 Your Processed Video:")
                    
                    with open(output_path, 'rb') as video_file:
                        video_data = video_file.read()
                    
                    # Show video
                    st.video(video_data)
                    
                    # Download button
                    st.download_button(
                        label="⬇️ Download Processed Video",
                        data=video_data,
                        file_name=f"background_replaced_{int(time.time())}.mp4",
                        mime="video/mp4",
                        use_container_width=True
                    )
                    
                    st.success("✅ Video ready for download!")
                    
                    # Cleanup
                    try:
                        os.unlink(video_path)
                        os.unlink(output_path)
                    except:
                        pass
                        
                else:
                    st.error("❌ Output video file is empty or corrupted")
                    
            except Exception as e:
                st.error(f"❌ Processing failed: {str(e)}")
                st.info("💡 Try with a shorter video or different background image")
    
    else:
        st.info("👆 Upload both a video and background image to start processing!")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 10px;">
        <p><small>🍹 Powered by MatAnyone and MediaPipe | Optimized for MyAvatar</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
