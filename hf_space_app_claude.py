#!/usr/bin/env python3
"""
BackgroundFX - Video Background Replacement with Green Screen Workflow
Fixed for Hugging Face Space - Handles video preview issues
FIXED: Video display issue by properly handling file stream
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
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import background removal libraries
try:
    from rembg import remove, new_session
    REMBG_AVAILABLE = True
    logger.info("✅ rembg loaded successfully")
except ImportError as e:
    REMBG_AVAILABLE = False
    logger.warning(f"⚠️ rembg not available: {e}")

try:
    from sam2.build_sam import build_sam2_video_predictor
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    SAM2_AVAILABLE = True
    logger.info("✅ SAM2 loaded successfully")
except ImportError as e:
    SAM2_AVAILABLE = False
    logger.warning(f"⚠️ SAM2 not available: {e}")

try:
    import matanyone
    MATANYONE_AVAILABLE = True
    logger.info("✅ MatAnyone loaded successfully")
except ImportError as e:
    MATANYONE_AVAILABLE = False
    logger.warning(f"⚠️ MatAnyone not available: {e}")

def get_video_info(video_path):
    """Get video information and first frame"""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None, None
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        # Get first frame for thumbnail
        ret, first_frame = cap.read()
        cap.release()
        
        if ret:
            # Convert BGR to RGB
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
        logger.error(f"Error getting video info: {e}")
        return None, None

def load_background_image(background_url):
    """Load background image from URL"""
    try:
        response = requests.get(background_url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        return np.array(image.convert('RGB'))
    except Exception as e:
        logger.error(f"Failed to load background image: {e}")
        return create_default_background()

def create_default_background():
    """Create a default brick wall background"""
    height, width = 720, 1280
    background = np.ones((height, width, 3), dtype=np.uint8) * 150
    
    # Add brick pattern
    brick_height, brick_width = 40, 80
    for y in range(0, height, brick_height):
        for x in range(0, width, brick_width):
            offset = brick_width // 2 if (y // brick_height) % 2 else 0
            x_pos = (x + offset) % width
            
            cv2.rectangle(background, 
                         (x_pos, y), 
                         (min(x_pos + brick_width - 2, width), min(y + brick_height - 2, height)), 
                         (180, 120, 80), -1)
            cv2.rectangle(background, 
                         (x_pos, y), 
                         (min(x_pos + brick_width - 2, width), min(y + brick_height - 2, height)), 
                         (120, 80, 40), 2)
    
    return background

def segment_person_rembg(frame):
    """Segment person using rembg (faster and more efficient)"""
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"🚀 rembg using device: {device}")
        
        # Convert frame to PIL Image
        from PIL import Image
        frame_pil = Image.fromarray(frame)
        
        # Create rembg session with u2net model (good for people)
        session = new_session('u2net')
        
        # Remove background - returns RGBA image
        result = remove(frame_pil, session=session)
        
        # Convert back to numpy array
        result_np = np.array(result)
        
        # Extract alpha channel as mask
        if result_np.shape[2] == 4:  # RGBA
            mask = result_np[:, :, 3] > 0  # Alpha channel > 0 = foreground
            return mask
        else:
            logger.warning("rembg did not return RGBA image")
            return None
            
    except Exception as e:
        logger.error(f"rembg segmentation failed: {e}")
        return None

def segment_person_sam2(frame):
    """Segment person using SAM2 with GPU optimization"""
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        
        predictor = SAM2ImagePredictor.from_pretrained("facebook/sam2-hiera-large")
        
        # Move model to GPU if available
        if device == "cuda":
            predictor.model = predictor.model.to(device)
            logger.info("✅ SAM2 model moved to GPU")
        
        predictor.set_image(frame)
        
        h, w = frame.shape[:2]
        center_point = np.array([[w//2, h//2]])
        center_label = np.array([1])
        
        masks, scores, _ = predictor.predict(
            point_coords=center_point,
            point_labels=center_label,
            multimask_output=False
        )
        
        return masks[0] if len(masks) > 0 else None
        
    except Exception as e:
        logger.error(f"SAM2 segmentation failed: {e}")
        return None

def segment_person_fallback(frame):
    """Fallback person segmentation using color-based method"""
    try:
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        
        lower_skin = np.array([0, 20, 70])
        upper_skin = np.array([20, 255, 255])
        
        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
        
        kernel = np.ones((5, 5), np.uint8)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [largest_contour], 255)
            kernel = np.ones((20, 20), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=2)
            return mask.astype(bool)
        
        return None
        
    except Exception as e:
        logger.error(f"Fallback segmentation failed: {e}")
        return None

def insert_green_screen(frame, person_mask):
    """Insert green screen background while preserving person"""
    try:
        green_background = np.zeros_like(frame)
        green_background[:, :] = [0, 255, 0]  # Pure green
        
        result = np.where(person_mask[..., None], frame, green_background)
        return result
        
    except Exception as e:
        logger.error(f"Green screen insertion failed: {e}")
        return frame

def replace_background(frame, person_mask, background):
    """Replace background with new image"""
    try:
        # Resize background to match frame dimensions
        h, w = frame.shape[:2]
        background_resized = cv2.resize(background, (w, h))
        
        # Create smooth edges
        mask_float = person_mask.astype(np.float32)
        kernel = np.ones((5, 5), np.float32) / 25
        mask_float = cv2.filter2D(mask_float, -1, kernel)
        
        # Composite the images
        result = np.zeros_like(frame)
        for c in range(3):
            result[:, :, c] = (mask_float * frame[:, :, c] + 
                              (1 - mask_float) * background_resized[:, :, c])
        
        return result.astype(np.uint8)
        
    except Exception as e:
        logger.error(f"Background replacement failed: {e}")
        return frame

def process_video(video_path, output_path, background_image, use_green_screen=True, progress_callback=None):
    """Process video with background replacement and GPU optimization"""
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"🚀 Video processing starting on device: {device}")
        
        # Log GPU memory if available
        if device == "cuda":
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"📊 GPU Memory: {gpu_memory:.1f} GB")
        
        cap = cv2.VideoCapture(video_path)
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Convert BGR to RGB for processing
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Segment person - prioritize rembg for speed
            if REMBG_AVAILABLE:
                person_mask = segment_person_rembg(frame_rgb)
            elif SAM2_AVAILABLE:
                person_mask = segment_person_sam2(frame_rgb)
            else:
                person_mask = segment_person_fallback(frame_rgb)
            
            if person_mask is not None:
                if use_green_screen:
                    # First create green screen
                    frame_rgb = insert_green_screen(frame_rgb, person_mask)
                    # Then replace green with background
                    # Create green mask
                    lower_green = np.array([0, 200, 0])
                    upper_green = np.array([100, 255, 100])
                    green_mask = cv2.inRange(frame_rgb, lower_green, upper_green)
                    green_mask = green_mask.astype(bool)
                    # Replace green areas with background
                    frame_rgb = replace_background(frame_rgb, ~green_mask, background_image)
                else:
                    # Direct background replacement
                    frame_rgb = replace_background(frame_rgb, person_mask, background_image)
            
            # Convert back to BGR for writing
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            out.write(frame_bgr)
            
            frame_count += 1
            if progress_callback:
                progress_callback(frame_count / total_frames)
        
        cap.release()
        out.release()
        
        return True
        
    except Exception as e:
        logger.error(f"Video processing failed: {e}")
        return False

# Streamlit UI
def main():
    st.set_page_config(
        page_title="BackgroundFX",
        page_icon="🎬",
        layout="wide"
    )
    
    st.title("🎬 BackgroundFX - Video Background Replacement")
    st.markdown("Replace video backgrounds with AI-powered segmentation")
    
    # Check dependencies and GPU status
    try:
        import torch
        gpu_available = torch.cuda.is_available()
        if gpu_available:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            st.success(f"🚀 GPU Available: {gpu_name} ({gpu_memory:.1f} GB)")
        else:
            st.warning("⚠️ No GPU available - processing will be slower on CPU")
    except ImportError:
        st.warning("⚠️ PyTorch not available - cannot check GPU status")
    
    # Show segmentation method status
    if REMBG_AVAILABLE:
        st.success("🚀 rembg available - using fast background removal")
    elif SAM2_AVAILABLE:
        st.info("🤖 SAM2 available - using AI segmentation")
    else:
        st.warning("⚠️ Using fallback segmentation method - may be slower")
    
    if not MATANYONE_AVAILABLE:
        st.info("ℹ️ MatAnyone not available - using standard matting")
    
    # Sidebar for settings
    with st.sidebar:
        st.header("⚙️ Settings")
        
        use_green_screen = st.checkbox(
            "Use Green Screen Workflow",
            value=True,
            help="First create green screen, then replace with background"
        )
        
        st.subheader("📸 Background Options")
        bg_option = st.radio(
            "Choose background source:",
            ["Preset Backgrounds", "Upload Image"]
        )
        
        background_image = None
        
        if bg_option == "Preset Backgrounds":
            # Preset background URLs
            preset_backgrounds = {
                "Brick Wall (Default)": "default_brick",
                "Modern Office": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1280&h=720&fit=crop",
                "Executive Office": "https://images.unsplash.com/photo-1586953208448-b95a79798f07?w=1280&h=720&fit=crop",
                "Conference Room": "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=1280&h=720&fit=crop",
                "Library Study": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=1280&h=720&fit=crop",
                "Nature Forest": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1280&h=720&fit=crop",
                "Mountain View": "https://images.unsplash.com/photo-1464822759844-d150baec3e5d?w=1280&h=720&fit=crop",
                "Beach Paradise": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1280&h=720&fit=crop",
                "City Skyline": "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1280&h=720&fit=crop",
                "Studio Professional": "https://images.unsplash.com/photo-1598300042247-d088f8ab3a91?w=1280&h=720&fit=crop",
                "Custom URL...": "custom"
            }
            
            selected_bg = st.selectbox(
                "Choose background:",
                list(preset_backgrounds.keys()),
                help="Select from professional backgrounds or enter custom URL"
            )
            
            if selected_bg == "Custom URL...":
                bg_url = st.text_input(
                    "Enter custom background URL:",
                    value="https://images.unsplash.com/photo-1557683316-973673baf926",
                    help="Enter a direct image URL"
                )
                if bg_url:
                    with st.spinner("Loading custom background..."):
                        background_image = load_background_image(bg_url)
                        if background_image is not None:
                            st.success("✅ Custom background loaded")
                            st.image(background_image, caption="Custom Background Preview", use_container_width=True)
            elif selected_bg == "Brick Wall (Default)":
                background_image = create_default_background()
                st.info("Using default brick wall background")
                st.image(background_image, caption="Default Brick Wall", use_container_width=True)
            else:
                bg_url = preset_backgrounds[selected_bg]
                st.info(f"Selected: {selected_bg}")
                with st.spinner("Loading background..."):
                    background_image = load_background_image(bg_url)
                    if background_image is not None:
                        st.success("✅ Background loaded")
                        st.image(background_image, caption="Background Preview", use_container_width=True)
        
        elif bg_option == "Upload Image":
            uploaded_bg = st.file_uploader(
                "Upload Background Image",
                type=['jpg', 'jpeg', 'png'],
                help="Upload your own background image"
            )
            if uploaded_bg is not None:
                background_image = np.array(Image.open(uploaded_bg).convert('RGB'))
                st.success("✅ Background uploaded")
                st.image(background_image, caption="Background Preview", use_container_width=True)

    
    # Main content area
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("📹 Input Video")
        uploaded_video = st.file_uploader(
            "Upload your video",
            type=['mp4', 'avi', 'mov', 'mkv'],
            help="Upload a video to process"
        )
        
        if uploaded_video is not None:
            # FIXED: Read bytes once and reuse
            video_bytes = uploaded_video.read()
            
            # Save to temporary file for processing
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                tmp_file.write(video_bytes)
                temp_video_path = tmp_file.name
            
            # Display video using the original bytes (not consuming the stream)
            st.video(video_bytes)
            
            # Get video info using the temp file
            video_info, first_frame = get_video_info(temp_video_path)
            
            if video_info and first_frame is not None:
                st.success(f"✅ Video loaded: {video_info['width']}x{video_info['height']}, "
                          f"{video_info['fps']} fps, {video_info['duration']:.1f}s")
                
                # Show first frame as thumbnail (optional - can be removed if not needed)
                # st.image(first_frame, caption="Video Thumbnail", use_container_width=True)
                
                # Store paths in session state
                if 'temp_video_path' not in st.session_state:
                    st.session_state.temp_video_path = temp_video_path
            else:
                st.error("Failed to read video information")
    
    with col2:
        st.header("🎯 Output")
        
        if uploaded_video is not None and background_image is not None:
            if st.button("🚀 Process Video", type="primary"):
                try:
                    # Create output path
                    output_path = tempfile.mktemp(suffix='.mp4')
                    
                    # Process video with progress bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    def update_progress(progress):
                        progress_bar.progress(progress)
                        status_text.text(f"Processing: {int(progress * 100)}%")
                    
                    status_text.text("Starting video processing...")
                    
                    # Use the temp file path we saved
                    success = process_video(
                        st.session_state.temp_video_path,
                        output_path,
                        background_image,
                        use_green_screen,
                        update_progress
                    )
                    
                    if success and os.path.exists(output_path):
                        status_text.text("✅ Processing complete!")
                        
                        # Read the processed video
                        with open(output_path, 'rb') as f:
                            processed_video = f.read()
                        
                        # Display processed video
                        st.video(processed_video)
                        
                        # Download button
                        st.download_button(
                            label="📥 Download Processed Video",
                            data=processed_video,
                            file_name="backgroundfx_output.mp4",
                            mime="video/mp4"
                        )
                        
                        # Cleanup
                        os.unlink(output_path)
                    else:
                        st.error("❌ Video processing failed")
                    
                except Exception as e:
                    st.error(f"Error during processing: {str(e)}")
                    logger.error(f"Processing error: {e}")
        
        elif uploaded_video is None:
            st.info("👈 Please upload a video to begin")
        elif background_image is None:
            st.info("👈 Please select or upload a background image")
    
    # Cleanup temporary files on session end
    if 'temp_video_path' in st.session_state and os.path.exists(st.session_state.temp_video_path):
        try:
            os.unlink(st.session_state.temp_video_path)
            del st.session_state.temp_video_path
        except:
            pass
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center'>
            <p>BackgroundFX v1.0 | AI-Powered Video Background Replacement</p>
            <p>Using SAM2 for person segmentation and green screen technology</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
