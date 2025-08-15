#!/usr/bin/env python3
"""
BackgroundFX - Video Background Replacement with Green Screen Workflow
Fixed for Hugging Face Space - Handles video preview issues
FIXED: Video display issue by properly handling file stream
Updated: 2025-08-13 - Force rebuild to fix Streamlit context issues
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

# Try to import SAM2 and MatAnyone
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

def load_background_image(background_url):
    """Load background image from URL"""
    try:
        response = requests.get(background_url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        return np.array(image.convert('RGB'))
    except Exception as e:
        logger.error(f"Failed to load background image: {e}")
        # Return default brick wall background
        return create_default_background()

def create_default_background():
    """Create a default brick wall background"""
    # Create a simple brick pattern
    height, width = 720, 1280
    background = np.ones((height, width, 3), dtype=np.uint8) * 150
    
    # Add brick pattern
    brick_height, brick_width = 40, 80
    for y in range(0, height, brick_height):
        for x in range(0, width, brick_width):
            # Alternate brick offset
            offset = brick_width // 2 if (y // brick_height) % 2 else 0
            x_pos = (x + offset) % width
            
            # Draw brick
            cv2.rectangle(background, 
                         (x_pos, y), 
                         (min(x_pos + brick_width - 2, width), min(y + brick_height - 2, height)), 
                         (180, 120, 80), -1)
            cv2.rectangle(background, 
                         (x_pos, y), 
                         (min(x_pos + brick_width - 2, width), min(y + brick_height - 2, height)), 
                         (120, 80, 40), 2)
    
    return background

def get_basic_backgrounds():
    """Get basic background options for free users"""
    return {
        "Brick Wall": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=1280&h=720&fit=crop",
        "Simple Office": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1280&h=720&fit=crop"
    }

def get_professional_backgrounds():
    """Get professional background options for premium users"""
    return {
        "Brick Wall": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=1280&h=720&fit=crop",
        "Simple Office": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1280&h=720&fit=crop",
        "Executive Office": "https://images.unsplash.com/photo-1586953208448-b95a79798f07?w=1280&h=720&fit=crop",
        "Modern Conference Room": "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=1280&h=720&fit=crop",
        "Library Study": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=1280&h=720&fit=crop",
        "Nature Forest": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1280&h=720&fit=crop",
        "Mountain View": "https://images.unsplash.com/photo-1464822759844-d150baec3e5d?w=1280&h=720&fit=crop",
        "Beach Paradise": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1280&h=720&fit=crop",
        "City Skyline": "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1280&h=720&fit=crop",
        "Studio Professional": "https://images.unsplash.com/photo-1598300042247-d088f8ab3a91?w=1280&h=720&fit=crop"
    }

def check_premium_access():
    """Check if user has premium access - placeholder for now"""
    # In a real implementation, this would check user authentication/subscription
    # For now, return True to enable all backgrounds in HF Space
    return True

def segment_person_sam2(frame):
    """Segment person using SAM2"""
    try:
        # Initialize SAM2 predictor
        predictor = SAM2ImagePredictor.from_pretrained("facebook/sam2-hiera-large")
        
        # Set image
        predictor.set_image(frame)
        
        # Use center point as prompt (assuming person is in center)
        h, w = frame.shape[:2]
        center_point = np.array([[w//2, h//2]])
        center_label = np.array([1])
        
        # Predict mask
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
        # Convert to HSV for better skin detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        
        # Define skin color range
        lower_skin = np.array([0, 20, 70])
        upper_skin = np.array([20, 255, 255])
        
        # Create mask for skin tones
        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
        
        # Morphological operations to clean up mask
        kernel = np.ones((5, 5), np.uint8)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)
        
        # Find largest contour (assumed to be person)
        contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # Get largest contour
            largest_contour = max(contours, key=cv2.contourArea)
            
            # Create mask from contour
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [largest_contour], 255)
            
            # Expand mask to include more of the person
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
        # Create green background
        green_background = np.zeros_like(frame)
        green_background[:, :] = [0, 255, 0]  # Pure green (RGB)
        
        # Combine person with green background
        # Where mask is True (person), keep original frame
        # Where mask is False (background), use green
        result = np.where(person_mask[..., None], frame, green_background)
        
        return result
        
    except Exception as e:
        logger.error(f"Green screen insertion failed: {e}")
        return frame

def chroma_key_replacement(green_screen_frame, new_background):
    """Replace green screen with new background using chroma key"""
    try:
        # Resize background to match frame
        h, w = green_screen_frame.shape[:2]
        background_resized = cv2.resize(new_background, (w, h))
        
        # Convert to HSV for better green detection
        hsv = cv2.cvtColor(green_screen_frame, cv2.COLOR_RGB2HSV)
        
        # Define green color range for chroma key
        lower_green = np.array([40, 50, 50])
        upper_green = np.array([80, 255, 255])
        
        # Create mask for green pixels
        green_mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Smooth the mask
        kernel = np.ones((3, 3), np.uint8)
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
        green_mask = cv2.GaussianBlur(green_mask, (5, 5), 0)
        
        # Normalize mask to 0-1 range
        mask_normalized = green_mask.astype(float) / 255
        
        # Apply chroma key replacement
        result = green_screen_frame.copy()
        for c in range(3):
            result[:, :, c] = (green_screen_frame[:, :, c] * (1 - mask_normalized) + 
                              background_resized[:, :, c] * mask_normalized)
        
        return result.astype(np.uint8)
        
    except Exception as e:
        logger.error(f"Chroma key replacement failed: {e}")
        return green_screen_frame

def process_video_with_green_screen(video_path, background_url, progress_callback=None):
    """Process video with proper green screen workflow"""
    try:
        # Load background image
        background_image = load_background_image(background_url)
        
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
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Step 1: Segment person
            if SAM2_AVAILABLE:
                person_mask = segment_person_sam2(frame_rgb)
                method_used = "SAM2"
            else:
                person_mask = segment_person_fallback(frame_rgb)
                method_used = "Fallback"
            
            if person_mask is not None:
                # Step 2: Insert green screen
                green_screen_frame = insert_green_screen(frame_rgb, person_mask)
                
                # Step 3: Chroma key replacement
                final_frame = chroma_key_replacement(green_screen_frame, background_image)
            else:
                # If segmentation fails, use original frame
                final_frame = frame_rgb
                method_used = "No segmentation"
            
            # Convert back to BGR for video writer
            final_frame_bgr = cv2.cvtColor(final_frame, cv2.COLOR_RGB2BGR)
            out.write(final_frame_bgr)
            
            frame_count += 1
            
            # Update progress
            if progress_callback:
                progress = frame_count / total_frames
                progress_callback(progress, f"Processing frame {frame_count}/{total_frames} ({method_used})")
        
        # Release resources
        cap.release()
        out.release()
        
        return output_path
        
    except Exception as e:
        logger.error(f"Video processing failed: {e}")
        return None

def process_video_with_green_screen_custom(video_path, background_image, progress_callback=None):
    """Process video with custom background image"""
    try:
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
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Step 1: Segment person
            if SAM2_AVAILABLE:
                person_mask = segment_person_sam2(frame_rgb)
                method_used = "SAM2"
            else:
                person_mask = segment_person_fallback(frame_rgb)
                method_used = "Fallback"
            
            if person_mask is not None:
                # Step 2: Insert green screen
                green_screen_frame = insert_green_screen(frame_rgb, person_mask)
                
                # Step 3: Chroma key replacement with custom background
                final_frame = chroma_key_replacement(green_screen_frame, background_image)
            else:
                # If segmentation fails, use original frame
                final_frame = frame_rgb
                method_used = "No segmentation"
            
            # Convert back to BGR for video writer
            final_frame_bgr = cv2.cvtColor(final_frame, cv2.COLOR_RGB2BGR)
            out.write(final_frame_bgr)
            
            frame_count += 1
            
            # Update progress
            if progress_callback:
                progress = frame_count / total_frames
                progress_callback(progress, f"Processing frame {frame_count}/{total_frames} ({method_used})")
        
        # Release resources
        cap.release()
        out.release()
        
        return output_path
        
    except Exception as e:
        logger.error(f"Video processing with custom background failed: {e}")
        return None

def main():
    """Streamlit main function"""
    st.set_page_config(
        page_title="BackgroundFX - Video Background Replacement",
        page_icon="🎬",
        layout="wide"
    )
    
    st.title("🎬 BackgroundFX - Video Background Replacement")
    st.markdown("**Professional video background replacement with green screen workflow**")
    
    # Show available methods
    methods = []
    if SAM2_AVAILABLE:
        methods.append("✅ SAM2 (AI Segmentation)")
    if MATANYONE_AVAILABLE:
        methods.append("✅ MatAnyone (Advanced Processing)")
    methods.append("✅ Fallback Method (Color-based)")
    
    st.sidebar.markdown("### Available Methods")
    for method in methods:
        st.sidebar.markdown(method)
    
    # File upload
    col1, col2 = st.columns(2)
    
    # Initialize session state for video persistence
    if 'video_path' not in st.session_state:
        st.session_state.video_path = None
    if 'video_bytes' not in st.session_state:
        st.session_state.video_bytes = None
    if 'video_name' not in st.session_state:
        st.session_state.video_name = None
    
    with col1:
        st.markdown("### 📹 Upload Video")
        uploaded_video = st.file_uploader(
            "Choose a video file", 
            type=['mp4', 'avi', 'mov', 'mkv'],
            help="Upload the video you want to process"
        )
        
        if uploaded_video:
            # Check if this is a new video upload
            if st.session_state.video_name != uploaded_video.name:
                # Display video info
                st.success(f"✅ Video uploaded: {uploaded_video.name}")
                
                # Read video data once and store it
                video_bytes = uploaded_video.read()
                
                # Save uploaded video to persistent temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                    tmp_file.write(video_bytes)
                    video_path = tmp_file.name
                
                # Store in session state for persistence
                st.session_state.video_path = video_path
                st.session_state.video_bytes = video_bytes
                st.session_state.video_name = uploaded_video.name
            
            # Show video preview using stored bytes
            if st.session_state.video_bytes is not None:
                st.video(st.session_state.video_bytes)
        
        elif st.session_state.video_path:
            # Show previously uploaded video info
            st.success(f"✅ Video ready: {st.session_state.video_name}")
            st.video(st.session_state.video_bytes)
    
    with col2:
        st.markdown("### 🖼️ Background Image")
        
        # Background selection method
        background_method = st.radio(
            "Choose background method:",
            ["📋 Preset Backgrounds", "📁 Upload Custom Image"],
            index=0
        )
        
        background_url = None
        custom_background = None
        
        if background_method == "📋 Preset Backgrounds":
            # Check premium access and get appropriate backgrounds
            is_premium = check_premium_access()
            
            if is_premium:
                background_options = get_professional_backgrounds()
                st.info("🎨 **Professional Backgrounds** - Premium collection available!")
            else:
                background_options = get_basic_backgrounds()
                st.info("🆓 **Basic Backgrounds** - Upgrade for professional collection!")
            
            selected_background = st.selectbox(
                "Choose background",
                options=list(background_options.keys()),
                index=0
            )
            
            background_url = background_options[selected_background]
            
            # Show background preview
            try:
                background_image = load_background_image(background_url)
                st.image(background_image, caption=f"Background: {selected_background}", use_column_width=True)
            except:
                st.error("Failed to load background image")
        
        else:  # Upload Custom Image
            uploaded_background = st.file_uploader(
                "Upload your background image",
                type=['jpg', 'jpeg', 'png', 'bmp'],
                help="Upload a custom background image (JPG, PNG, BMP)"
            )
            
            if uploaded_background:
                # Load and display custom background
                try:
                    custom_background = np.array(Image.open(uploaded_background).convert('RGB'))
                    st.image(custom_background, caption="Custom Background", use_column_width=True)
                    st.success(f"✅ Custom background uploaded: {uploaded_background.name}")
                except Exception as e:
                    st.error(f"Failed to load custom background: {e}")
                    custom_background = None
            else:
                st.info("Please upload a background image")
    
    # Process button
    if (uploaded_video or st.session_state.video_path) and st.button("🎬 Process Video", type="primary"):
        
        # Check if background is selected
        if background_method == "📋 Preset Backgrounds" and not background_url:
            st.error("Please select a preset background")
            return
        elif background_method == "📁 Upload Custom Image" and custom_background is None:
            st.error("Please upload a custom background image")
            return
        
        with st.spinner("Processing video with green screen workflow..."):
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(progress, message):
                progress_bar.progress(progress)
                status_text.text(message)
            
            # Process video with appropriate background using session state
            if background_method == "📋 Preset Backgrounds":
                output_path = process_video_with_green_screen(
                    st.session_state.video_path, 
                    background_url, 
                    progress_callback=update_progress
                )
            else:  # Custom background
                output_path = process_video_with_green_screen_custom(
                    st.session_state.video_path, 
                    custom_background, 
                    progress_callback=update_progress
                )
            
            if output_path and os.path.exists(output_path):
                st.success("✅ Video processing completed!")
                
                # Display processed video
                st.markdown("### 🎉 Processed Video")
                
                with open(output_path, 'rb') as video_file:
                    video_bytes = video_file.read()
                    st.video(video_bytes)
                
                # Download button
                st.download_button(
                    label="📥 Download Processed Video",
                    data=video_bytes,
                    file_name=f"backgroundfx_{st.session_state.video_name}",
                    mime="video/mp4"
                )
                
                # Cleanup processed video only (keep original for re-processing)
                try:
                    os.unlink(output_path)
                except:
                    pass
                
                # Add button to clear session and cleanup
                if st.button("🗑️ Clear Video & Start Over"):
                    try:
                        if st.session_state.video_path and os.path.exists(st.session_state.video_path):
                            os.unlink(st.session_state.video_path)
                    except:
                        pass
                    st.session_state.video_path = None
                    st.session_state.video_bytes = None
                    st.session_state.video_name = None
                    st.experimental_rerun()
            else:
                st.error("❌ Video processing failed. Please try again.")
    
    # Footer
    st.markdown("---")
    st.markdown("### 🔧 Technical Details")
    st.markdown("""
    **Green Screen Workflow:**
    1. **Person Segmentation** - AI identifies the person in each frame
    2. **Green Screen Insert** - Replaces background with pure green
    3. **Chroma Key Replacement** - Replaces green with new background
    
    This ensures clean edges and professional results.
    """)

if __name__ == "__main__":
    main()
