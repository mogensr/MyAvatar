"""
🍹 Video Background Replacer - IFRAME OPTIMIZED VERSION + SAVE TO MYAVATAR
Combining Windsurf's UI improvements with Claude's audio/video processing + Direct Save
"""

import streamlit as st
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import time
import requests
import base64
from datetime import datetime

# ============================================================================
# IFRAME OPTIMIZATION - From Windsurf + Claude's recommendations
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

def save_to_myavatar(video_data, filename):
    """Save processed video directly to MyAvatar backend"""
    try:
        # MyAvatar API endpoint - MUST use HTTPS for HF Space compatibility
        api_url = "https://myavatar-production.up.railway.app/api/backgroundfx/save-video"
        
        # Encode video data as base64 for API transmission
        video_b64 = base64.b64encode(video_data).decode('utf-8')
        
        # Create enhanced payload with proper metadata
        payload = {
            "video_data": video_b64,
            "filename": filename,
            "source": "hf_space_streamlit",
            "content_type": "video/mp4",
            "file_size": len(video_data),
            "processed_at": datetime.now().isoformat(),
            "processing_type": "background_replacement",
            "metadata": {
                "tool": "MatAnyone",
                "interface": "Streamlit",
                "version": "2.0",
                "hf_space": True
            }
        }
        
        # Enhanced headers with proper authentication
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "HF-Space-BackgroundFX/2.0",
            "Accept": "application/json",
            "X-Requested-With": "StreamlitApp"
        }
        
        # Make the API call with enhanced error handling
        response = requests.post(api_url, json=payload, headers=headers, timeout=120)
        
        # Debug logging
        st.write(f"🔍 Debug - API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                video_id = result.get('video_id', 'unknown')
                return True, f"✅ Video saved to My Videos! (ID: {video_id})"
            else:
                error_detail = result.get('detail', result.get('error', 'Unknown error'))
                return False, f"❌ Save failed: {error_detail}"
        elif response.status_code == 401:
            return False, "❌ Authentication required - please log in to MyAvatar"
        elif response.status_code == 413:
            return False, "❌ Video file too large for upload"
        elif response.status_code == 429:
            return False, "❌ Too many requests - please wait and try again"
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('detail', response.text)
            except:
                error_msg = response.text
            return False, f"❌ API Error ({response.status_code}): {error_msg}"
            
    except requests.exceptions.Timeout:
        return False, "❌ Save timeout - video may be too large (try smaller file)"
    except requests.exceptions.ConnectionError:
        return False, "❌ Connection error - MyAvatar server may be down"
    except requests.exceptions.SSLError:
        return False, "❌ SSL/HTTPS connection error - security issue"
    except Exception as e:
        st.write(f"🔍 Debug - Exception details: {str(e)}")
        return False, f"❌ Save error: {str(e)}"

def main():
    # Compact header for iframe
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
        
        # Clear any previous results and status
        if 'video_result' in st.session_state:
            del st.session_state['video_result']
        if 'video_filename' in st.session_state:
            del st.session_state['video_filename']
        if 'save_success' in st.session_state:
            del st.session_state['save_success']
        if 'save_message' in st.session_state:
            del st.session_state['save_message']
        if 'download_clicked' in st.session_state:
            del st.session_state['download_clicked']
        
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
            # Step B: Load MatAnyone
            status_text.text("Step B: Loading MatAnyone...")
            from matanyone import InferenceCore
            processor = InferenceCore("PeiqingYang/MatAnyone")
            progress_bar.progress(40)
            
            # Step C: Create initial mask
            status_text.text("Step C: Creating segmentation mask...")
            import mediapipe as mp
            
            mp_selfie = mp.solutions.selfie_segmentation
            selfie_segmentation = mp_selfie.SelfieSegmentation(model_selection=1)
            
            # Get first frame for mask
            cap = cv2.VideoCapture(video_path)
            ret, first_frame = cap.read()
            cap.release()
            
            if ret:
                rgb_frame = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB)
                results = selfie_segmentation.process(rgb_frame)
                mask = (results.segmentation_mask > 0.5).astype(np.uint8) * 255
                
                mask_path = f"temp_mask_{int(time.time())}.png"
                cv2.imwrite(mask_path, mask)
            else:
                st.error("Could not read video file")
                st.stop()
                
            progress_bar.progress(60)
            
            # Step D: Run MatAnyone (creates green screen video)
            status_text.text("Step D: Running MatAnyone - extracting person...")
            
            foreground_path, alpha_path = processor.process_video(
                input_path=video_path,
                mask_path=mask_path,
                output_path="output"
            )
            
            progress_bar.progress(80)
            
            # Step E: Replace green screen with new background
            status_text.text("Step E: Adding new background...")
            
            # Read background image
            bg_image = cv2.imread(image_path)
            
            # Open the videos
            cap_fg = cv2.VideoCapture(foreground_path)
            cap_alpha = cv2.VideoCapture(alpha_path)
            
            # Get video properties from ORIGINAL video
            cap_orig = cv2.VideoCapture(video_path)
            fps = int(cap_orig.get(cv2.CAP_PROP_FPS))
            width = int(cap_orig.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap_orig.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap_orig.release()
            
            # Resize background to match ORIGINAL video
            bg_resized = cv2.resize(bg_image, (width, height))
            
            # Step F: Create output video with smart codec selection
            status_text.text("Step F: Creating optimized video...")
            
            try:
                # Try to create MP4 directly with H.264
                fourcc_h264 = cv2.VideoWriter_fourcc(*'H264')
                output_path = f"final_video_{int(time.time())}.mp4"
                out = cv2.VideoWriter(output_path, fourcc_h264, fps, (width, height))
                
                if not out.isOpened():
                    # Fallback to XVID
                    temp_output_path = f"temp_output_{int(time.time())}.avi"
                    fourcc_xvid = cv2.VideoWriter_fourcc(*'XVID')
                    out = cv2.VideoWriter(temp_output_path, fourcc_xvid, fps, (width, height))
                    if not out.isOpened():
                        st.error("❌ Could not create video writer!")
                        st.stop()
                    use_temp_file = True
                else:
                    use_temp_file = False
                    st.info("✅ Using H.264 codec directly")
                    
            except Exception as e:
                st.error(f"❌ Setup error: {e}")
                st.stop()
            
            # Process each frame
            frame_count = 0
            while True:
                ret_fg, frame_fg = cap_fg.read()
                ret_alpha, frame_alpha = cap_alpha.read()
                
                if not ret_fg or not ret_alpha:
                    break
                
                # Convert alpha to single channel if needed
                if len(frame_alpha.shape) == 3:
                    alpha = cv2.cvtColor(frame_alpha, cv2.COLOR_BGR2GRAY)
                else:
                    alpha = frame_alpha
                
                # Normalize alpha
                alpha_norm = alpha.astype(float) / 255.0
                
                # Blend: person * alpha + background * (1-alpha)
                result = np.zeros_like(frame_fg, dtype=float)
                for c in range(3):
                    result[:,:,c] = (frame_fg[:,:,c] * alpha_norm + 
                                   bg_resized[:,:,c] * (1 - alpha_norm))
                
                out.write(result.astype(np.uint8))
                frame_count += 1
            
            cap_fg.release()
            cap_alpha.release()
            out.release()
            
            st.write(f"✅ Processed {frame_count} frames")
            
            progress_bar.progress(90)
            
            # Step G: Audio preservation and web optimization
            if use_temp_file:
                status_text.text("Step G: Adding audio and optimizing...")
                
                try:
                    # Try FFmpeg for audio preservation
                    import subprocess
                    
                    final_output_path = f"final_video_{int(time.time())}.mp4"
                    
                    # Extract audio from original video
                    audio_path = f"temp_audio_{int(time.time())}.wav"
                    extract_audio_cmd = [
                        'ffmpeg', '-y',
                        '-i', video_path,
                        '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2',
                        audio_path
                    ]
                    
                    audio_result = subprocess.run(extract_audio_cmd, capture_output=True, text=True)
                    has_audio = audio_result.returncode == 0 and os.path.exists(audio_path)
                    
                    if has_audio:
                        st.info("✅ Audio extracted, combining with video...")
                        # Combine processed video with original audio
                        ffmpeg_cmd = [
                            'ffmpeg', '-y',
                            '-i', temp_output_path,  # Processed video (no audio)
                            '-i', audio_path,        # Original audio
                            '-c:v', 'libx264',
                            '-preset', 'fast',
                            '-crf', '23',
                            '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac',           # Audio codec
                            '-movflags', '+faststart',  # Web optimization
                            final_output_path
                        ]
                    else:
                        st.info("ℹ️ No audio track found")
                        # No audio - just convert video
                        ffmpeg_cmd = [
                            'ffmpeg', '-y',
                            '-i', temp_output_path,
                            '-c:v', 'libx264',
                            '-preset', 'fast',
                            '-crf', '23',
                            '-pix_fmt', 'yuv420p',
                            '-movflags', '+faststart',
                            final_output_path
                        ]
                    
                    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        st.success("✅ Video with audio optimized!")
                        output_path = final_output_path
                        # Clean up temp files
                        if os.path.exists(temp_output_path):
                            os.remove(temp_output_path)
                        if has_audio and os.path.exists(audio_path):
                            os.remove(audio_path)
                    else:
                        st.warning("⚠️ FFmpeg failed, trying moviepy...")
                        raise Exception("FFmpeg failed")
                        
                except:
                    # Try moviepy for audio
                    try:
                        import moviepy.editor as mp
                        
                        st.info("🎵 Using moviepy for audio...")
                        original_clip = mp.VideoFileClip(video_path)
                        
                        if original_clip.audio is not None:
                            processed_clip = mp.VideoFileClip(temp_output_path)
                            final_clip = processed_clip.set_audio(original_clip.audio)
                            
                            final_output_path = f"final_video_{int(time.time())}.mp4"
                            final_clip.write_videofile(final_output_path, codec='libx264', audio_codec='aac')
                            
                            original_clip.close()
                            processed_clip.close()
                            final_clip.close()
                            
                            st.success("✅ Video with audio created!")
                            output_path = final_output_path
                            
                            if os.path.exists(temp_output_path):
                                os.remove(temp_output_path)
                        else:
                            st.info("ℹ️ No audio in original")
                            output_path = temp_output_path
                            
                    except Exception as e:
                        st.warning(f"⚠️ Audio processing failed: {e}")
                        output_path = temp_output_path
            else:
                # H.264 MP4 created directly - just optimize
                try:
                    from qtfaststart import processor as qtfast_processor
                    temp_fixed_path = f"fixed_{output_path}"
                    qtfast_processor.process(output_path, temp_fixed_path)
                    os.replace(temp_fixed_path, output_path)
                    st.info("✅ Video optimized for web streaming")
                except:
                    st.info("✅ Video created (basic optimization)")
            
            progress_bar.progress(100)
            status_text.text("✅ Complete!")
            
            # Step H: Display results
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                st.write(f"✅ Video saved: {file_size:,} bytes")
                
                # Read and store video
                with open(output_path, 'rb') as f:
                    st.session_state['video_result'] = f.read()
                    st.session_state['video_filename'] = f"background_replaced_{int(time.time())}.mp4"
                
                # Clear processing UI
                progress_bar.empty()
                status_text.empty()
                
                # Show success
                st.markdown('<div class="success-box">🎉 Video Successfully Processed! 🎉</div>', unsafe_allow_html=True)
                
                # Display video
                st.markdown("### 🎬 Your Processed Video:")
                st.video(st.session_state['video_result'])
                
                # Persistent action buttons - both always available
                st.markdown("### 📥 Download & Save Options")
                st.markdown("*Both options remain available until you process a new video*")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Download button - always available
                    st.download_button(
                        label="⬇️ Download to Device",
                        data=st.session_state['video_result'],
                        file_name=st.session_state['video_filename'],
                        mime="video/mp4",
                        use_container_width=True,
                        help="Download video to your device"
                    )
                    
                    # Show download status
                    if 'download_clicked' not in st.session_state:
                        st.session_state.download_clicked = False
                
                with col2:
                    # Save to MyAvatar button - always available
                    if st.button("💾 Save to My Videos", key="save_to_myavatar", use_container_width=True, type="secondary", help="Save directly to your MyAvatar library"):
                        with st.spinner("💾 Saving to MyAvatar library..."):
                            success, message = save_to_myavatar(
                                st.session_state['video_result'],
                                st.session_state['video_filename']
                            )
                        
                        if success:
                            st.session_state.save_success = True
                            st.session_state.save_message = message
                            st.success(message)
                            st.balloons()
                        else:
                            st.session_state.save_success = False
                            st.session_state.save_message = message
                            st.error(message)
                
                # Show persistent status messages
                if hasattr(st.session_state, 'save_success') and st.session_state.save_success:
                    st.success(f"✅ {st.session_state.save_message}")
                elif hasattr(st.session_state, 'save_success') and not st.session_state.save_success:
                    st.error(f"❌ {st.session_state.save_message}")
                
                # Save to MyAvatar info box
                st.markdown("""
                <div class="save-to-myavatar-box">
                    <h3 style="margin: 0 0 10px 0; color: white;">💾 Save to My Videos Library</h3>
                    <p style="margin: 0; color: white;">Click "Save to My Videos" to add this video directly to your MyAvatar library!</p>
                </div>
                """, unsafe_allow_html=True)
                
            else:
                st.error("❌ Failed to create video")
            
            # Cleanup
            try:
                for temp_file in [video_path, image_path, mask_path, foreground_path, alpha_path, output_path]:
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
    
    # Compact footer for iframe
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 10px;">
        <p><small>🍹 Powered by MatAnyone + Audio Preservation | Connected to MyAvatar</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
