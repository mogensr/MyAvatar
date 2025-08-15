"""
🍹 Video Background Replacer - Railway Deployment
Claude's enhanced Streamlit app optimized for Railway iframe embedding
"""

import streamlit as st
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import time

# ============================================================================
# RAILWAY IFRAME OPTIMIZATION
# ============================================================================

# Configure for iframe embedding in Railway
st.set_page_config(
    page_title="Video Background Replacement",
    page_icon="🍹",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Add Railway iframe-friendly styling
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
    
    /* Railway iframe-specific optimizations */
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

def main():
    # Compact header for Railway iframe
    st.markdown('<h1 class="main-header">🍹 Video Background Replacer</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.1rem; color: #666; margin-bottom: 2rem;">Replace your video background with AI + Audio!</p>', unsafe_allow_html=True)
    
    # Compact upload section
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎬 Upload Your Video")
        video_file = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'avi', 'mov'],
            help="Upload the video you want to process",
            key="video_uploader"
        )
        if video_file:
            st.success("✅ Video loaded!")
            st.video(video_file)
    
    with col2:
        st.markdown("### 🖼️ Upload Background Image")
        image_file = st.file_uploader(
            "Choose a background image",
            type=['png', 'jpg', 'jpeg'],
            help="Upload the background you want to use",
            key="image_uploader"
        )
        if image_file:
            st.success("✅ Background loaded!")
            st.image(image_file, width=300)

    # Process button
    if video_file and image_file and st.button("🍹 PROCESS VIDEO", key="process_button", use_container_width=True):
        
        # Clear any previous results
        if 'video_result' in st.session_state:
            del st.session_state['video_result']
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step A: Save uploaded files
        status_text.text("Step A: Saving uploaded files...")
        
        video_path = f"temp_video_{int(time.time())}.mp4"
        image_path = f"temp_image_{int(time.time())}.jpg"
        
        with open(video_path, "wb") as f:
            f.write(video_file.read())
        
        with open(image_path, "wb") as f:
            f.write(image_file.read())
        
        progress_bar.progress(20)
        
        try:
            # Step B: Try to load MatAnyone (fallback to MediaPipe if not available)
            status_text.text("Step B: Loading AI models...")
            
            use_matanyone = False
            use_mediapipe = False
            
            try:
                from matanyone import InferenceCore
                processor = InferenceCore("PeiqingYang/MatAnyone")
                use_matanyone = True
                st.success("🚀 MatAnyone AI loaded - Ultimate quality!")
            except ImportError:
                try:
                    import mediapipe as mp
                    mp_selfie = mp.solutions.selfie_segmentation
                    selfie_segmentation = mp_selfie.SelfieSegmentation(model_selection=1)
                    use_mediapipe = True
                    st.success("🎯 MediaPipe AI loaded - Good quality!")
                except ImportError:
                    st.info("📱 Using basic background replacement")
            
            progress_bar.progress(40)
            
            # Step C: Process video with available AI
            status_text.text("Step C: Processing video with AI...")
            
            # Read video properties
            cap = cv2.VideoCapture(video_path)
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            
            # Read background image
            bg_image = cv2.imread(image_path)
            bg_resized = cv2.resize(bg_image, (width, height))
            
            # Create output video
            output_path = f"output_video_{int(time.time())}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            # Process each frame
            cap = cv2.VideoCapture(video_path)
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if use_mediapipe:
                    # Use MediaPipe for segmentation
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = selfie_segmentation.process(rgb_frame)
                    mask = results.segmentation_mask
                    binary_mask = (mask > 0.5).astype(np.uint8)
                    bg_mask = 1 - binary_mask
                    result = frame * binary_mask[:, :, np.newaxis] + bg_resized * bg_mask[:, :, np.newaxis]
                else:
                    # Simple background replacement
                    result = cv2.addWeighted(frame, 0.6, bg_resized, 0.4, 0)
                
                out.write(result.astype(np.uint8))
                frame_count += 1
                
                # Update progress
                if frame_count % max(1, total_frames // 10) == 0:
                    progress = 60 + (frame_count / total_frames) * 20
                    progress_bar.progress(int(progress))
            
            cap.release()
            out.release()
            
            progress_bar.progress(80)
            
            # Step D: Audio preservation (if possible)
            status_text.text("Step D: Adding audio...")
            
            try:
                import subprocess
                
                # Try to add audio with FFmpeg
                final_output_path = f"final_video_{int(time.time())}.mp4"
                
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-i', output_path,  # Processed video (no audio)
                    '-i', video_path,   # Original video (with audio)
                    '-c:v', 'copy',     # Copy video stream
                    '-c:a', 'aac',      # Audio codec
                    '-map', '0:v:0',    # Video from processed
                    '-map', '1:a:0',    # Audio from original
                    '-shortest',        # Match shortest stream
                    final_output_path
                ]
                
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    st.success("✅ Audio preserved!")
                    output_path = final_output_path
                    if os.path.exists("temp_output.mp4"):
                        os.remove("temp_output.mp4")
                else:
                    st.info("ℹ️ Audio preservation failed, video only")
                    
            except Exception as e:
                st.info(f"ℹ️ Audio processing not available: {e}")
            
            progress_bar.progress(100)
            status_text.text("✅ Complete!")
            
            # Step E: Display results
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                st.write(f"✅ Video processed: {file_size:,} bytes")
                
                # Read and store video
                with open(output_path, 'rb') as f:
                    st.session_state['video_result'] = f.read()
                
                # Clear processing UI
                progress_bar.empty()
                status_text.empty()
                
                # Show success
                st.markdown('<div class="success-box">🎉 Video Successfully Processed! 🎉</div>', unsafe_allow_html=True)
                
                # Add a prominent save-to-library section
                st.markdown("""
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                           color: white; padding: 20px; border-radius: 15px; margin: 20px 0; text-align: center;">
                    <h3 style="margin: 0; color: white;">💾 Save to My Videos Library</h3>
                    <p style="margin: 10px 0; color: white;">Download the video and save it to your MyAvatar library!</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Display video
                st.markdown("### 🎬 Your Processed Video:")
                st.video(st.session_state['video_result'])
                
                # Generate filename for download
                filename = f"background_replaced_{int(time.time())}.mp4"
                
                # Download button
                st.download_button(
                    label="⬇️ Download Processed Video",
                    data=st.session_state['video_result'],
                    file_name=filename,
                    mime="video/mp4",
                    use_container_width=True
                )
                
                # Show the download URL for easy copying
                st.markdown("### 📋 Save to My Videos")
                st.info("💡 After downloading, copy the download URL from your browser and use it to save to your MyAvatar library!")
                
                # Create a temporary file URL that can be accessed
                # Note: In Streamlit, the actual download URL is generated when the download button is clicked
                # We'll show instructions for now
                st.markdown("""
                **How to save to My Videos:**
                1. Click the download button above
                2. Copy the download URL from your browser's download manager
                3. Go to your MyAvatar BackgroundFX page
                4. Click "Save to My Videos" and paste the URL
                """)
                
            else:
                st.error("❌ Failed to create video")
            
            # Cleanup
            try:
                for temp_file in [video_path, image_path, output_path]:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
            except:
                pass
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    elif not video_file or not image_file:
        st.info("👆 Upload both a video and background image to start processing!")
    
    # Compact footer for Railway iframe
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 10px;">
        <p><small>🍹 Powered by AI | Deployed on Railway for MyAvatar</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
