#!/usr/bin/env python3
"""
BackgroundFX - Fast Video Background Replacement
Optimized with Rembg for immediate deployment on HF Space with T4 GPU
Ready to run in 30 minutes!
"""

import streamlit as st
import cv2
import numpy as np
import tempfile
import os
from PIL import Image
import requests
from io import BytesIO
import logging
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check GPU
CUDA_AVAILABLE = torch.cuda.is_available()
if CUDA_AVAILABLE:
    logger.info(f"✅ GPU: {torch.cuda.get_device_name(0)}")
else:
    logger.warning("⚠️ Running on CPU")

# Import rembg - the main workhorse
try:
    from rembg import remove, new_session
    REMBG_AVAILABLE = True
    logger.info("✅ Rembg loaded")
except ImportError:
    REMBG_AVAILABLE = False
    st.error("❌ Please install rembg: pip install rembg")

# Global session cache
@st.cache_resource
def load_rembg_model():
    """Load and cache the Rembg model"""
    if REMBG_AVAILABLE:
        # u2net_human_seg is specifically for people
        session = new_session('u2net_human_seg')
        logger.info("✅ U2NET Human Segmentation model loaded")
        return session
    return None

def get_video_info(video_path):
    """Get video information"""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None, None
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        ret, first_frame = cap.read()
        cap.release()
        
        if ret:
            first_frame_rgb = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB)
            return {
                'fps': fps,
                'width': width,
                'height': height,
                'total_frames': total_frames,
                'duration': duration
            }, first_frame_rgb
        
        return None, None
    except Exception as e:
        logger.error(f"Error: {e}")
        return None, None

def create_gradient_background(width=1280, height=720, color1=(70, 130, 180), color2=(255, 140, 90)):
    """Create a nice gradient background"""
    background = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        blend = y / height
        color = [
            int(color1[0] * (1 - blend) + color2[0] * blend),
            int(color1[1] * (1 - blend) + color2[1] * blend),
            int(color1[2] * (1 - blend) + color2[2] * blend)
        ]
        background[y, :] = color
    return background

def process_frame_rembg(frame, session, background, use_green_screen=False):
    """Process a single frame with Rembg"""
    try:
        # Get RGBA output from rembg
        frame_pil = Image.fromarray(frame)
        output = remove(frame_pil, session=session, alpha_matting=True)  # Enable alpha matting for better edges
        output_np = np.array(output)
        
        # Extract alpha channel
        if output_np.shape[2] == 4:
            alpha = output_np[:, :, 3].astype(float) / 255.0
            person_rgb = output_np[:, :, :3]
        else:
            alpha = np.ones(frame.shape[:2])
            person_rgb = output_np
        
        # Resize background
        h, w = frame.shape[:2]
        bg_resized = cv2.resize(background, (w, h))
        
        if use_green_screen:
            # Green screen workflow
            green = np.zeros_like(frame)
            green[:, :] = [0, 255, 0]
            
            # Composite person on green
            green_composite = np.zeros_like(frame)
            for c in range(3):
                green_composite[:, :, c] = alpha * person_rgb[:, :, c] + (1 - alpha) * green[:, :, c]
            
            # Replace green with background
            lower_green = np.array([0, 200, 0])
            upper_green = np.array([100, 255, 100])
            green_mask = cv2.inRange(green_composite, lower_green, upper_green)
            green_mask_inv = cv2.bitwise_not(green_mask)
            
            result = cv2.bitwise_and(green_composite, green_composite, mask=green_mask_inv)
            bg_part = cv2.bitwise_and(bg_resized, bg_resized, mask=green_mask)
            result = cv2.add(result, bg_part)
        else:
            # Direct composite (faster and usually better)
            result = np.zeros_like(frame)
            for c in range(3):
                result[:, :, c] = alpha * person_rgb[:, :, c] + (1 - alpha) * bg_resized[:, :, c]
        
        return result.astype(np.uint8)
        
    except Exception as e:
        logger.error(f"Frame processing error: {e}")
        return frame

def process_video_fast(video_path, output_path, background, progress_callback=None, 
                       skip_frames=1, use_green_screen=False):
    """Fast video processing with Rembg"""
    try:
        # Load model once
        session = load_rembg_model()
        if session is None:
            st.error("Failed to load Rembg model")
            return False
        
        cap = cv2.VideoCapture(video_path)
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Adjust FPS if skipping frames
        output_fps = max(fps // skip_frames, 15)  # Minimum 15 fps
        
        # Use MP4V codec for compatibility
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, output_fps, (width, height))
        
        frame_count = 0
        processed_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Skip frames for speed
            if skip_frames > 1 and (frame_count - 1) % skip_frames != 0:
                continue
            
            # Process frame
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            processed_frame = process_frame_rembg(frame_rgb, session, background, use_green_screen)
            
            # Write frame
            frame_bgr = cv2.cvtColor(processed_frame, cv2.COLOR_RGB2BGR)
            out.write(frame_bgr)
            
            processed_count += 1
            
            if progress_callback and frame_count % 5 == 0:  # Update progress every 5 frames
                progress = frame_count / total_frames
                progress_callback(progress)
        
        cap.release()
        out.release()
        
        # Clear GPU memory
        if CUDA_AVAILABLE:
            torch.cuda.empty_cache()
        
        return True
        
    except Exception as e:
        logger.error(f"Video processing failed: {e}")
        return False

# Streamlit UI
def main():
    st.set_page_config(
        page_title="BackgroundFX - Fast",
        page_icon="🚀",
        layout="wide"
    )
    
    st.title("🚀 BackgroundFX - Fast Background Replacement")
    st.markdown("**Optimized for speed** - Using Rembg U2NET for human segmentation")
    
    # Quick status check
    cols = st.columns(3)
    with cols[0]:
        if CUDA_AVAILABLE:
            st.success(f"✅ GPU Active")
        else:
            st.warning("⚠️ CPU Mode")
    with cols[1]:
        if REMBG_AVAILABLE:
            st.success("✅ Rembg Ready")
        else:
            st.error("❌ Install rembg")
    with cols[2]:
        st.info("⚡ Fast Processing")
    
    # Two columns layout
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("📹 Upload Video")
        
        # Speed preset at the top for visibility
        speed_mode = st.select_slider(
            "⚡ Speed Mode",
            options=["Quality", "Balanced", "Fast", "Ultra Fast"],
            value="Fast"
        )
        
        # Set parameters based on mode
        if speed_mode == "Ultra Fast":
            skip_frames = 3
            use_green = False
            st.caption("⚡ Processes every 3rd frame, direct compositing")
        elif speed_mode == "Fast":
            skip_frames = 2
            use_green = False
            st.caption("⚡ Processes every 2nd frame, direct compositing")
        elif speed_mode == "Balanced":
            skip_frames = 1
            use_green = False
            st.caption("⚡ All frames, direct compositing")
        else:  # Quality
            skip_frames = 1
            use_green = True
            st.caption("⚡ All frames, green screen workflow")
        
        uploaded_video = st.file_uploader(
            "Choose video file",
            type=['mp4', 'avi', 'mov', 'mkv'],
            help="For best results, use videos under 30 seconds"
        )
        
        if uploaded_video is not None:
            # Save video
            video_bytes = uploaded_video.read()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                tmp_file.write(video_bytes)
                temp_path = tmp_file.name
            
            st.video(video_bytes)
            
            # Get info
            info, first_frame = get_video_info(temp_path)
            if info:
                st.success(f"✅ Ready: {info['duration']:.1f}s @ {info['fps']}fps")
                
                # Time estimate
                process_time = (info['duration'] / skip_frames) * 0.5  # Rough estimate
                st.info(f"⏱️ Estimated time: {process_time:.0f} seconds")
                
                st.session_state.video_path = temp_path
                st.session_state.video_info = info
        
        # Background selection
        st.subheader("🎨 Background")
        bg_type = st.radio("Choose:", ["Gradient", "Color", "Image URL", "Upload"])
        
        background = None
        
        if bg_type == "Gradient":
            col_a, col_b = st.columns(2)
            with col_a:
                color1 = st.color_picker("Top", "#4682B4")
            with col_b:
                color2 = st.color_picker("Bottom", "#FF8C5A")
            
            # Convert hex to RGB
            c1 = tuple(int(color1[i:i+2], 16) for i in (1, 3, 5))
            c2 = tuple(int(color2[i:i+2], 16) for i in (1, 3, 5))
            
            if 'video_info' in st.session_state:
                w = st.session_state.video_info['width']
                h = st.session_state.video_info['height']
                background = create_gradient_background(w, h, c1, c2)
            else:
                background = create_gradient_background(1280, 720, c1, c2)
        
        elif bg_type == "Color":
            color = st.color_picker("Pick color", "#00FF00")
            rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
            background = np.full((720, 1280, 3), rgb, dtype=np.uint8)
        
        elif bg_type == "Image URL":
            url = st.text_input("Image URL", "https://images.unsplash.com/photo-1557683316-973673baf926")
            if url:
                try:
                    response = requests.get(url)
                    img = Image.open(BytesIO(response.content))
                    background = np.array(img.convert('RGB'))
                    st.image(background, caption="Background", use_column_width=True)
                except:
                    st.error("Failed to load image")
        
        else:  # Upload
            uploaded_bg = st.file_uploader("Upload image", type=['jpg', 'jpeg', 'png'])
            if uploaded_bg:
                img = Image.open(uploaded_bg)
                background = np.array(img.convert('RGB'))
                st.image(background, caption="Background", use_column_width=True)
    
    with col2:
        st.header("🎬 Result")
        
        if uploaded_video and background is not None:
            if st.button("🚀 Process Video", type="primary", use_container_width=True):
                
                # Check if rembg is available
                if not REMBG_AVAILABLE:
                    st.error("Please install rembg first!")
                    st.code("pip install rembg", language="bash")
                    return
                
                try:
                    output_path = tempfile.mktemp(suffix='.mp4')
                    
                    progress = st.progress(0)
                    status = st.empty()
                    
                    def update_progress(value):
                        progress.progress(value)
                        status.text(f"Processing: {int(value * 100)}%")
                    
                    status.text("🔄 Starting processing...")
                    
                    success = process_video_fast(
                        st.session_state.video_path,
                        output_path,
                        background,
                        update_progress,
                        skip_frames,
                        use_green_screen=use_green
                    )
                    
                    if success and os.path.exists(output_path):
                        status.text("✅ Done!")
                        
                        with open(output_path, 'rb') as f:
                            result_video = f.read()
                        
                        st.video(result_video)
                        
                        st.download_button(
                            "💾 Download Result",
                            data=result_video,
                            file_name=f"backgroundfx_{speed_mode.lower()}.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )
                        
                        # Show stats
                        size_mb = len(result_video) / (1024 * 1024)
                        st.success(f"✅ Output size: {size_mb:.1f} MB")
                        
                        os.unlink(output_path)
                    else:
                        st.error("Processing failed!")
                
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    logger.error(f"Processing error: {e}")
        else:
            if not uploaded_video:
                st.info("👈 Upload a video to start")
            else:
                st.info("👈 Select a background")
    
    # Footer with tips
    st.markdown("---")
    with st.expander("💡 Quick Tips"):
        st.markdown("""
        - **Ultra Fast**: Best for quick previews (3x faster)
        - **Fast**: Good balance of speed and quality (2x faster)
        - **Balanced**: Full quality, still fast
        - **Quality**: Best edges with green screen workflow
        - Videos under 30 seconds process fastest
        - Gradient backgrounds render instantly
        """)

if __name__ == "__main__":
    main()
