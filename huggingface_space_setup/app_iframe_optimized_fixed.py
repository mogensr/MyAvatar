"""
🍹 Video Background Replacer - IFRAME OPTIMIZED VERSION
Optimized for embedding in MyAvatar Railway app with Claude's recommendations
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
        min-height: 300px; /* Prevents height jumping */
        display: flex;
        flex-direction: column;
        justify-content: center;
        transition: all 0.3s ease; /* Smooth transitions */
    }
    
    .upload-ready {
        background: rgba(76, 175, 80, 0.1);
        border-color: #4CAF50;
        color: #2E7D32;
        font-weight: bold;
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
    
    /* Iframe-specific optimizations */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* Mobile responsiveness for iframe */
    @media (max-width: 768px) {
        .main-header {
            font-size: 1.8rem;
        }
        .upload-slot {
            min-height: 250px;
        }
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
            # Initialize MatAnyone with model name (HuggingFace style)
            self.matanyone_processor = InferenceCore("PeiqingYang/MatAnyone")
            self.use_matanyone = True
            print("✅ MatAnyone AI loaded successfully!")
            
        except ImportError as e:
            print(f"⚠️ MatAnyone not found ({str(e)}), trying MediaPipe...")
            # Fallback to MediaPipe
            try:
                import mediapipe as mp
                self.mp_selfie_segmentation = mp.solutions.selfie_segmentation
                self.selfie_segmentation = self.mp_selfie_segmentation.SelfieSegmentation(model_selection=1)
                self.use_mediapipe = True
                print("✅ MediaPipe AI loaded successfully!")
            except ImportError:
                print("📱 Using basic background replacement (install MatAnyone or MediaPipe for better results)")
        
        except Exception as e:
            print(f"⚠️ MatAnyone failed to load ({str(e)}), trying MediaPipe...")
            # Fallback to MediaPipe
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
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Define range for background colors (you can adjust these)
        # This is a simple approach - in practice, you'd want more sophisticated detection
        lower_bg = np.array([0, 0, 0])
        upper_bg = np.array([180, 255, 100])
        
        # Create mask
        mask = cv2.inRange(hsv, lower_bg, upper_bg)
        
        # Invert mask (we want person, not background)
        mask = cv2.bitwise_not(mask)
        
        # Apply some morphological operations to clean up the mask
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Convert to 3-channel for blending
        mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        
        return mask

    def process_frame(self, frame, background_image):
        """Process a single frame with background replacement"""
        if self.use_matanyone:
            try:
                # Convert frame to PIL Image for MatAnyone
                frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                
                # Use MatAnyone for segmentation
                result = self.matanyone_processor.infer(frame_pil)
                
                # Extract the mask from MatAnyone result
                if hasattr(result, 'alpha') and result.alpha is not None:
                    # MatAnyone returns alpha matte
                    mask = np.array(result.alpha)
                    if len(mask.shape) == 2:
                        mask = np.stack([mask] * 3, axis=-1)
                    mask = mask.astype(np.float32) / 255.0
                else:
                    # Fallback if alpha not available
                    mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
                
            except Exception as e:
                print(f"MatAnyone processing failed: {e}, using fallback")
                mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
                
        elif self.use_mediapipe:
            try:
                # Convert BGR to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Process with MediaPipe
                results = self.selfie_segmentation.process(rgb_frame)
                
                if results.segmentation_mask is not None:
                    # Convert segmentation mask to 3-channel
                    mask = results.segmentation_mask
                    mask = np.stack([mask] * 3, axis=-1).astype(np.float32)
                else:
                    mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
                    
            except Exception as e:
                print(f"MediaPipe processing failed: {e}, using fallback")
                mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
        else:
            # Simple fallback method
            mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
        
        # Resize background to match frame
        bg_resized = cv2.resize(background_image, (frame.shape[1], frame.shape[0]))
        
        # Apply background replacement
        # mask values close to 1 = keep original (person)
        # mask values close to 0 = use background
        result = frame * mask + bg_resized * (1 - mask)
        
        return result.astype(np.uint8)

    def process_video(self, video_path, background_image, progress_callback=None):
        """Process entire video with background replacement"""
        # Convert PIL background to OpenCV format
        if isinstance(background_image, Image.Image):
            background_image = cv2.cvtColor(np.array(background_image), cv2.COLOR_RGB2BGR)
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Create output video writer
        output_path = tempfile.mktemp(suffix='.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        frame_count = 0
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Process frame
                processed_frame = self.process_frame(frame, background_image)
                out.write(processed_frame)
                
                frame_count += 1
                
                # Update progress
                if progress_callback:
                    progress = frame_count / total_frames
                    progress_callback(progress, frame_count, total_frames)
        
        finally:
            cap.release()
            out.release()
        
        return output_path

def main():
    # Compact header for iframe
    st.markdown('<h1 class="main-header">🍹 Video Background Replacer</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.1rem; color: #666; margin-bottom: 2rem;">Replace your video background with AI!</p>', unsafe_allow_html=True)
    
    # Initialize the background replacer with loading feedback
    if 'replacer' not in st.session_state:
        with st.spinner('🔄 Loading AI Processing Interface...'):
            st.session_state.replacer = BackgroundReplacer()
    
    # Show initialization status
    if hasattr(st.session_state.replacer, 'use_matanyone') and st.session_state.replacer.use_matanyone:
        st.success('🚀 MatAnyone AI Ready - Ultimate Quality!')
    elif hasattr(st.session_state.replacer, 'use_mediapipe') and st.session_state.replacer.use_mediapipe:
        st.success('🎯 MediaPipe AI Ready - Good Quality!')
    else:
        st.info('📱 Basic Processing Ready')
    
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
        st.markdown("### 🚀 Ready to Process!")
        
        # Process button (clean and stable)
        if st.button("🍹 PROCESS VIDEO", key="process_button", use_container_width=True):
            # Clear any previous results first
            if 'video_result' in st.session_state:
                del st.session_state['video_result']
            
            # Save uploaded files
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_video:
                tmp_video.write(uploaded_video.read())
                video_path = tmp_video.name
            
            background_image = Image.open(uploaded_background)
            
            # Processing container - clean and professional
            processing_container = st.empty()
            
            with processing_container.container():
                st.markdown('<div class="processing-box">', unsafe_allow_html=True)
                st.markdown("### 🔄 Processing Your Video...")
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def update_progress(progress, frame_count, total_frames):
                    progress_bar.progress(progress)
                    status_text.text(f"Processing frame {frame_count}/{total_frames} ({progress*100:.1f}%)")
                
                try:
                    # Process the video
                    st.info("🚀 Starting video processing...")
                    output_path = st.session_state.replacer.process_video(
                        video_path, background_image, update_progress
                    )
                    
                    # Clear processing animation
                    processing_container.empty()
                    
                    # Success message
                    st.markdown('<div class="success-box">🎉 Video Successfully Processed! 🎉</div>', unsafe_allow_html=True)
                    
                    # Store result in session state
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        with open(output_path, 'rb') as video_file:
                            st.session_state['video_result'] = video_file.read()
                        
                        # Cleanup temp files
                        try:
                            os.unlink(video_path)
                            os.unlink(output_path)
                        except:
                            pass
                            
                    else:
                        st.error("❌ Output video file is empty or corrupted")
                        
                except Exception as e:
                    processing_container.empty()
                    st.error(f"❌ Processing failed: {str(e)}")
                    st.info("💡 Try with a shorter video or different background image")
        
        # Display results if they exist (separate from processing)
        if 'video_result' in st.session_state:
            st.markdown("### 🎬 Your Processed Video:")
            
            # Show the video
            st.video(st.session_state['video_result'])
            
            # Download button
            st.download_button(
                label="⬇️ Download Processed Video",
                data=st.session_state['video_result'],
                file_name=f"background_replaced_{int(time.time())}.mp4",
                mime="video/mp4",
                use_container_width=True,
                key="download_button"
            )
            
            st.success("✅ Video ready for download!")
    
    else:
        st.info("👆 Upload both a video and background image to start processing!")
    
    # Compact footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 10px;">
        <p><small>🍹 Powered by MatAnyone and MediaPipe | Optimized for MyAvatar</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
