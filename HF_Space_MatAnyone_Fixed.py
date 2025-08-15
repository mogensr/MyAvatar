"""
🍹 Video Background Replacer - MATANYONE API FIXED
Corrected MatAnyone API usage: processor.step() instead of processor.infer()
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

# Configure Streamlit
st.set_page_config(
    page_title="Video Background Replacement",
    page_icon="🍹",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS styling
st.markdown("""
<style>
    .main > div { padding-top: 1rem; }
    .stDeployButton { display: none; }
    header[data-testid="stHeader"] { display: none; }
    .main-header {
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1.5rem;
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
        """Initialize with CORRECTED MatAnyone API"""
        self.use_matanyone = False
        self.use_mediapipe = False
        
        print("🔄 Starting AI model initialization...")
        
        # Try MatAnyone with CORRECT API
        try:
            print("🚀 Attempting to load MatAnyone...")
            from matanyone.inference.inference_core import InferenceCore
            from matanyone.utils.get_default_model import get_matanyone_model
            from matanyone.utils.device import get_default_device
            
            print("📦 MatAnyone imported successfully, initializing processor...")
            
            # Get device and model
            self.device = get_default_device()
            
            # Load MatAnyone model (this will auto-download if needed)
            self.matanyone_model = get_matanyone_model(None, self.device)  # None = auto-download
            
            # Initialize processor with CORRECT API
            self.matanyone_processor = InferenceCore(self.matanyone_model, cfg=self.matanyone_model.cfg)
            
            self.use_matanyone = True
            print("✅ MatAnyone AI loaded successfully!")
            
        except ImportError as e:
            print(f"⚠️ MatAnyone not found ({str(e)}), trying MediaPipe...")
            self._init_mediapipe()
        except Exception as e:
            print(f"⚠️ MatAnyone failed to load ({str(e)}), trying MediaPipe...")
            self._init_mediapipe()
    
    def _init_mediapipe(self):
        """Initialize MediaPipe as fallback"""
        try:
            import mediapipe as mp
            self.mp_selfie_segmentation = mp.solutions.selfie_segmentation
            self.selfie_segmentation = self.mp_selfie_segmentation.SelfieSegmentation(model_selection=1)
            self.use_mediapipe = True
            print("✅ MediaPipe AI loaded successfully!")
        except ImportError:
            print("📱 Using basic background replacement")

    def process_frame_matanyone(self, frame, background_image, is_first_frame=False, mask=None):
        """Process frame using CORRECTED MatAnyone API"""
        try:
            # Convert frame to tensor format expected by MatAnyone
            frame_tensor = torch.from_numpy(frame).permute(2, 0, 1).float() / 255.0
            frame_tensor = frame_tensor.to(self.device)
            
            if is_first_frame and mask is not None:
                # First frame: provide mask
                mask_tensor = torch.from_numpy(mask).float().to(self.device)
                objects = [1]  # Object ID
                
                # CORRECTED API: Use .step() not .infer()
                output_prob = self.matanyone_processor.step(frame_tensor, mask_tensor, objects=objects)
                output_prob = self.matanyone_processor.step(frame_tensor, first_frame_pred=True)
            else:
                # Subsequent frames: no mask needed
                output_prob = self.matanyone_processor.step(frame_tensor)
            
            # Convert output to mask
            alpha_mask = self.matanyone_processor.output_prob_to_mask(output_prob)
            alpha_mask = alpha_mask.cpu().numpy()
            
            # Ensure mask is 3-channel
            if len(alpha_mask.shape) == 2:
                alpha_mask = np.stack([alpha_mask] * 3, axis=-1)
            
            return alpha_mask.astype(np.float32)
            
        except Exception as e:
            print(f"MatAnyone processing error: {e}")
            return self.create_simple_mask(frame).astype(np.float32) / 255.0

    def create_simple_mask(self, frame):
        """Fallback mask creation"""
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

    def process_frame(self, frame, background_image, is_first_frame=False, mask=None):
        """Process a single frame with background replacement"""
        if self.use_matanyone:
            alpha_mask = self.process_frame_matanyone(frame, background_image, is_first_frame, mask)
        elif self.use_mediapipe:
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.selfie_segmentation.process(rgb_frame)
                
                if results.segmentation_mask is not None:
                    alpha_mask = results.segmentation_mask
                    alpha_mask = np.stack([alpha_mask] * 3, axis=-1).astype(np.float32)
                else:
                    alpha_mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
            except Exception as e:
                print(f"MediaPipe error: {e}")
                alpha_mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
        else:
            alpha_mask = self.create_simple_mask(frame).astype(np.float32) / 255.0
        
        # Resize background to match frame
        bg_resized = cv2.resize(background_image, (frame.shape[1], frame.shape[0]))
        
        # Apply background replacement
        result = frame * alpha_mask + bg_resized * (1 - alpha_mask)
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
                
                # For MatAnyone, first frame needs special handling
                is_first_frame = (frame_count == 0)
                mask = None  # Could add mask detection here if needed
                
                processed_frame = self.process_frame(frame, background_image, is_first_frame, mask)
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
    st.markdown('<h1 class="main-header">🍹 Video Background Replacer</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.1rem; color: #666; margin-bottom: 2rem;">Replace your video background with AI!</p>', unsafe_allow_html=True)
    
    # Initialize replacer
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
        uploaded_video = st.file_uploader("Choose a video file", type=['mp4', 'avi', 'mov', 'mkv'])
        if uploaded_video:
            st.video(uploaded_video)
    
    with col2:
        st.markdown("### 🖼️ Upload Background Image")
        uploaded_background = st.file_uploader("Choose background image", type=['jpg', 'jpeg', 'png', 'bmp'])
        if uploaded_background:
            st.image(uploaded_background, caption="Background Preview")
    
    # Processing section
    if uploaded_video and uploaded_background:
        st.markdown("---")
        st.markdown("### 🚀 Ready to Process!")
        
        if st.button("🍹 PROCESS VIDEO", use_container_width=True):
            # Save uploaded files
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_video:
                tmp_video.write(uploaded_video.read())
                video_path = tmp_video.name
            
            background_image = Image.open(uploaded_background)
            
            # Processing
            st.markdown("### 🔄 Processing Your Video...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(progress, frame_count, total_frames):
                progress_bar.progress(progress)
                status_text.text(f"Processing frame {frame_count}/{total_frames} ({progress*100:.1f}%)")
            
            try:
                output_path = st.session_state.replacer.process_video(
                    video_path, background_image, update_progress
                )
                
                progress_bar.progress(1.0)
                status_text.text("✅ Processing complete!")
                
                st.markdown('<div class="success-box">🎉 Video Successfully Processed! 🎉</div>', unsafe_allow_html=True)
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    st.markdown("### 🎬 Your Processed Video:")
                    
                    with open(output_path, 'rb') as video_file:
                        video_data = video_file.read()
                    
                    st.video(video_data)
                    
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
        <p><small>🍹 Powered by MatAnyone and MediaPipe | Fixed API Integration</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
