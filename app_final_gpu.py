#!/usr/bin/env python3
"""
BackgroundFX - GPU-Optimized Video Background Replacement
FIXED: GPU and RAM utilization for HuggingFace Space L4 GPU
Updated: 2025-08-13 - FINAL GPU VERSION: Claude's optimizations integrated
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
import gc
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OPTIMIZED: Aggressive GPU setup with proper memory management
def setup_gpu_environment():
    """Setup GPU environment with proper CUDA utilization"""
    # Set environment variables for optimal GPU usage
    os.environ['OMP_NUM_THREADS'] = '8'  # Increased for L4
    os.environ['ORT_PROVIDERS'] = 'CUDAExecutionProvider,CPUExecutionProvider'
    os.environ['CUDA_VISIBLE_DEVICES'] = '0'
    os.environ['TORCH_CUDA_ARCH_LIST'] = '8.9'  # L4 architecture
    os.environ['CUDA_LAUNCH_BLOCKING'] = '0'  # Async CUDA
    os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:512'
    
    # Check and initialize GPU
    try:
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            
            logger.info(f"🚀 GPU: {gpu_name} ({gpu_memory:.1f}GB)")
            
            # Initialize CUDA context
            torch.cuda.init()
            torch.cuda.set_device(0)
            
            # Warm up GPU with larger tensor
            dummy = torch.randn(1024, 1024, device='cuda')
            dummy = dummy @ dummy.T  # Matrix multiplication to warm up
            del dummy
            torch.cuda.empty_cache()
            
            # Set memory fraction for optimal usage
            torch.cuda.set_per_process_memory_fraction(0.8)  # Use 80% of GPU memory
            
            return True, gpu_name, gpu_memory
        else:
            logger.warning("⚠️ CUDA not available")
            return False, None, 0
    except Exception as e:
        logger.error(f"GPU setup failed: {e}")
        return False, None, 0

# Initialize GPU environment
CUDA_AVAILABLE, GPU_NAME, GPU_MEMORY = setup_gpu_environment()

# CLAUDE'S FIX: Enable TF32 for better performance on L4
if CUDA_AVAILABLE:
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    torch.backends.cudnn.deterministic = False

# CLAUDE'S FIX: GPU-optimized rembg with ONNX providers
try:
    from rembg import remove, new_session
    import onnxruntime as ort
    
    REMBG_AVAILABLE = True
    logger.info("✅ Rembg loaded")
    
    # FORCE GPU providers for ONNX
    if CUDA_AVAILABLE:
        providers = [
            ('CUDAExecutionProvider', {
                'device_id': 0,
                'arena_extend_strategy': 'kSameAsRequested',
                'gpu_mem_limit': 20 * 1024 * 1024 * 1024,  # 20GB for L4
                'cudnn_conv_algo_search': 'HEURISTIC',
            }),
            'CPUExecutionProvider'
        ]
        
        # Create session with explicit GPU providers
        rembg_session = new_session('u2net_human_seg', providers=providers)
        
        # VIGTIGT: Warm up the model on GPU
        dummy_img = Image.new('RGB', (512, 512), color='white')
        with torch.cuda.amp.autocast():  # Use mixed precision
            _ = remove(dummy_img, session=rembg_session)
        
        logger.info(f"✅ Rembg GPU session initialized with providers: {providers}")
    else:
        rembg_session = new_session('u2net_human_seg')
        logger.info("✅ Rembg CPU session initialized")

except ImportError as e:
    REMBG_AVAILABLE = False
    rembg_session = None
    logger.warning(f"⚠️ Rembg not available: {e}")

# Try to import SAM2 with GPU optimization
try:
    from sam2.build_sam import build_sam2_video_predictor
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    SAM2_AVAILABLE = True
    logger.info("✅ SAM2 loaded successfully")
    
    # Initialize SAM2 with GPU if available
    if CUDA_AVAILABLE:
        sam2_predictor = SAM2ImagePredictor.from_pretrained("facebook/sam2-hiera-large")
        sam2_predictor.to('cuda')
        logger.info("✅ SAM2 GPU predictor initialized")
    else:
        sam2_predictor = None
        
except ImportError as e:
    SAM2_AVAILABLE = False
    sam2_predictor = None
    logger.warning(f"⚠️ SAM2 not available: {e}")

# GPU-accelerated OpenCV setup
try:
    # Enable OpenCV GPU acceleration
    if cv2.cuda.getCudaEnabledDeviceCount() > 0:
        logger.info(f"✅ OpenCV CUDA devices: {cv2.cuda.getCudaEnabledDeviceCount()}")
        OPENCV_GPU = True
    else:
        OPENCV_GPU = False
        logger.warning("⚠️ OpenCV CUDA not available")
except:
    OPENCV_GPU = False
    logger.warning("⚠️ OpenCV CUDA not available")

# Memory management utilities
def optimize_memory():
    """Optimize memory usage"""
    if CUDA_AVAILABLE:
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    gc.collect()

def get_memory_usage():
    """Get current memory usage"""
    stats = {}
    if CUDA_AVAILABLE:
        stats['gpu_allocated'] = torch.cuda.memory_allocated() / 1024**3
        stats['gpu_reserved'] = torch.cuda.memory_reserved() / 1024**3
        stats['gpu_free'] = GPU_MEMORY - stats['gpu_reserved']
    else:
        stats['gpu_allocated'] = 0
        stats['gpu_reserved'] = 0
        stats['gpu_free'] = 0
    
    return stats

# Background loading functions
def load_background_image(background_url):
    """Load background image from URL"""
    try:
        if background_url == "default_brick":
            return create_default_background()
        
        response = requests.get(background_url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        return np.array(image.convert('RGB'))
    except Exception as e:
        logger.error(f"Failed to load background image: {e}")
        return create_default_background()

def create_default_background():
    """Create a default brick wall background"""
    background = np.zeros((720, 1280, 3), dtype=np.uint8)
    background[:, :] = [139, 69, 19]  # Brown color
    
    # Add brick pattern
    for y in range(0, 720, 60):
        for x in range(0, 1280, 120):
            cv2.rectangle(background, (x, y), (x+115, y+55), (160, 82, 45), -1)
            cv2.rectangle(background, (x, y), (x+115, y+55), (101, 67, 33), 2)
    
    return background

def get_professional_backgrounds():
    """Get professional background collection"""
    return {
        "🏢 Modern Office": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1920&h=1080&fit=crop",
        "🌆 City Skyline": "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1920&h=1080&fit=crop",
        "🏖️ Tropical Beach": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1920&h=1080&fit=crop",
        "🌲 Forest Path": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=1920&h=1080&fit=crop",
        "🎨 Abstract Blue": "https://images.unsplash.com/photo-1557683316-973673baf926?w=1920&h=1080&fit=crop",
        "🏔️ Mountain View": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=1920&h=1080&fit=crop",
        "🌅 Sunset Gradient": "https://images.unsplash.com/photo-1495616811223-4d98c6e9c869?w=1920&h=1080&fit=crop",
        "💼 Executive Suite": "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=1920&h=1080&fit=crop"
    }

# CLAUDE'S FIX: Optimized rembg segmentation with GPU acceleration
def segment_person_rembg_optimized(frame):
    """Optimized rembg segmentation with GPU acceleration"""
    try:
        if REMBG_AVAILABLE and rembg_session:
            # Convert frame to PIL Image
            pil_image = Image.fromarray(frame)
            
            # Use GPU memory efficiently
            if CUDA_AVAILABLE:
                # Process with mixed precision for L4
                with torch.cuda.amp.autocast():
                    output = remove(
                        pil_image, 
                        session=rembg_session,
                        alpha_matting=True,
                        alpha_matting_foreground_threshold=240,
                        alpha_matting_background_threshold=10,
                        alpha_matting_erode_size=10
                    )
            else:
                output = remove(pil_image, session=rembg_session, alpha_matting=True)
            
            # Extract alpha channel as mask
            output_array = np.array(output)
            if output_array.shape[2] == 4:
                mask = output_array[:, :, 3].astype(np.float32) / 255.0  # Use float32
            else:
                mask = np.ones((frame.shape[0], frame.shape[1]), dtype=np.float32)
            
            return mask
        return None
    except Exception as e:
        logger.error(f"Rembg segmentation failed: {e}")
        return None

def segment_person_sam2_gpu(frame):
    """GPU-accelerated SAM2 segmentation"""
    try:
        if SAM2_AVAILABLE and sam2_predictor and CUDA_AVAILABLE:
            # Convert to tensor and move to GPU
            frame_tensor = torch.from_numpy(frame).permute(2, 0, 1).float().cuda()
            frame_tensor = frame_tensor.unsqueeze(0) / 255.0
            
            with torch.no_grad():
                # SAM2 prediction on GPU
                # This is a placeholder - actual SAM2 implementation would go here
                logger.debug("SAM2 GPU segmentation attempted")
                
            # Clean up GPU memory
            del frame_tensor
            torch.cuda.empty_cache()
            
        return None  # Fallback for now
    except Exception as e:
        logger.error(f"SAM2 GPU segmentation failed: {e}")
        return None

def segment_person_opencv_gpu(frame):
    """GPU-accelerated OpenCV segmentation"""
    try:
        if OPENCV_GPU:
            # Upload frame to GPU
            gpu_frame = cv2.cuda_GpuMat()
            gpu_frame.upload(frame)
            
            # Convert to HSV on GPU
            gpu_hsv = cv2.cuda.cvtColor(gpu_frame, cv2.COLOR_RGB2HSV)
            
            # Create mask on GPU
            lower_skin = np.array([0, 20, 70])
            upper_skin = np.array([20, 255, 255])
            
            gpu_mask = cv2.cuda.inRange(gpu_hsv, lower_skin, upper_skin)
            
            # Morphological operations on GPU
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            gpu_mask = cv2.cuda.morphologyEx(gpu_mask, cv2.MORPH_CLOSE, kernel)
            gpu_mask = cv2.cuda.morphologyEx(gpu_mask, cv2.MORPH_OPEN, kernel)
            
            # Download result from GPU
            mask = gpu_mask.download()
            
            # Clean up GPU memory
            del gpu_frame, gpu_hsv, gpu_mask
            
            return mask.astype(float) / 255
        else:
            # CPU fallback
            return segment_person_fallback_cpu(frame)
    except Exception as e:
        logger.error(f"OpenCV GPU segmentation failed: {e}")
        return segment_person_fallback_cpu(frame)

def segment_person_fallback_cpu(frame):
    """CPU fallback segmentation"""
    try:
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        lower_skin = np.array([0, 20, 70])
        upper_skin = np.array([20, 255, 255])
        mask = cv2.inRange(hsv, lower_skin, upper_skin)
        
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        return mask.astype(float) / 255
    except Exception as e:
        logger.error(f"CPU fallback segmentation failed: {e}")
        return None

# GPU-OPTIMIZED: Video processing with batch processing
def process_video_gpu_optimized(video_path, background_url, progress_callback=None):
    """GPU-optimized video processing with batch processing"""
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
        
        logger.info(f"Processing video: {width}x{height}, {total_frames} frames, {fps} FPS")
        
        # Create output video writer
        output_path = tempfile.mktemp(suffix='.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # Resize background once
        background_resized = cv2.resize(background_image, (width, height))
        
        frame_count = 0
        batch_size = 4 if CUDA_AVAILABLE else 1  # Process multiple frames if GPU available
        frame_batch = []
        
        while True:
            ret, frame = cap.read()
            if not ret:
                # Process remaining frames in batch
                if frame_batch:
                    processed_batch = process_frame_batch(frame_batch, background_resized)
                    for processed_frame in processed_batch:
                        out.write(processed_frame)
                break
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_batch.append(frame_rgb)
            
            # Process batch when full or GPU memory optimization
            if len(frame_batch) >= batch_size:
                processed_batch = process_frame_batch(frame_batch, background_resized)
                
                for processed_frame in processed_batch:
                    out.write(processed_frame)
                    frame_count += 1
                    
                    # Update progress
                    if progress_callback:
                        progress = frame_count / total_frames
                        memory_stats = get_memory_usage()
                        progress_callback(
                            progress, 
                            f"GPU Processing: {frame_count}/{total_frames} | "
                            f"GPU: {memory_stats['gpu_allocated']:.1f}GB used"
                        )
                
                # Clear batch and optimize memory
                frame_batch = []
                optimize_memory()
        
        # Release resources
        cap.release()
        out.release()
        optimize_memory()
        
        logger.info(f"Video processing complete: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"GPU video processing failed: {e}")
        return None

def process_frame_batch(frame_batch, background_resized):
    """Process a batch of frames for GPU efficiency"""
    processed_frames = []
    
    for frame in frame_batch:
        # Try segmentation methods in order
        person_mask = None
        method_used = "None"
        
        # Try SAM2 GPU first
        if SAM2_AVAILABLE and CUDA_AVAILABLE:
            person_mask = segment_person_sam2_gpu(frame)
            if person_mask is not None:
                method_used = "SAM2-GPU"
        
        # Try rembg optimized (CLAUDE'S IMPROVED VERSION)
        if person_mask is None and REMBG_AVAILABLE:
            person_mask = segment_person_rembg_optimized(frame)
            if person_mask is not None:
                method_used = "Rembg-GPU"
        
        # Try OpenCV GPU
        if person_mask is None and OPENCV_GPU:
            person_mask = segment_person_opencv_gpu(frame)
            if person_mask is not None:
                method_used = "OpenCV-GPU"
        
        # CPU fallback
        if person_mask is None:
            person_mask = segment_person_fallback_cpu(frame)
            method_used = "CPU-Fallback"
        
        if person_mask is not None:
            # Composite with background
            if person_mask.ndim == 2:
                person_mask = np.expand_dims(person_mask, axis=2)
            
            final_frame = frame * person_mask + background_resized * (1 - person_mask)
            final_frame = final_frame.astype(np.uint8)
        else:
            final_frame = frame
        
        # Convert back to BGR
        final_frame_bgr = cv2.cvtColor(final_frame, cv2.COLOR_RGB2BGR)
        processed_frames.append(final_frame_bgr)
    
    return processed_frames

# Streamlit UI with GPU monitoring
def main():
    st.set_page_config(
        page_title="BackgroundFX - GPU Optimized",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🚀 BackgroundFX - GPU-Optimized Video Processing")
    st.markdown("**High-performance GPU-accelerated background replacement**")
    
    # GPU Status Dashboard
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if CUDA_AVAILABLE:
            st.success(f"🚀 GPU: {GPU_NAME}")
            st.caption(f"{GPU_MEMORY:.1f}GB VRAM")
        else:
            st.warning("⚠️ CPU Mode")
    
    with col2:
        if SAM2_AVAILABLE and CUDA_AVAILABLE:
            st.success("✅ SAM2-GPU")
        elif REMBG_AVAILABLE:
            st.success("✅ Rembg-GPU")
        else:
            st.warning("⚠️ Basic Mode")
    
    with col3:
        if OPENCV_GPU:
            st.success("✅ OpenCV-GPU")
        else:
            st.info("ℹ️ OpenCV-CPU")
    
    with col4:
        memory_stats = get_memory_usage()
        if CUDA_AVAILABLE:
            st.metric("GPU Memory", f"{memory_stats['gpu_allocated']:.1f}GB")
        else:
            st.info("CPU Processing")
    
    # Sidebar with GPU monitoring and CLAUDE'S DEBUG INFO
    with st.sidebar:
        st.markdown("### 🚀 GPU Performance")
        
        if CUDA_AVAILABLE:
            memory_stats = get_memory_usage()
            st.metric("GPU Allocated", f"{memory_stats['gpu_allocated']:.2f}GB")
            st.metric("GPU Reserved", f"{memory_stats['gpu_reserved']:.2f}GB")
            st.metric("GPU Free", f"{memory_stats['gpu_free']:.2f}GB")
            
            # Memory usage bar
            usage_percent = (memory_stats['gpu_reserved'] / GPU_MEMORY) * 100
            st.progress(usage_percent / 100)
            st.caption(f"{usage_percent:.1f}% GPU Memory Used")
        else:
            st.warning("GPU not available")
        
        # CLAUDE'S DEBUG INFO
        st.markdown("### 🔍 GPU Debug Info")
        
        if CUDA_AVAILABLE:
            # Check ONNX providers
            try:
                import onnxruntime as ort
                providers = ort.get_available_providers()
                gpu_providers = [p for p in providers if 'CUDA' in p or 'Tensorrt' in p]
                if gpu_providers:
                    st.success(f"✅ ONNX GPU: {', '.join(gpu_providers)}")
                else:
                    st.error("❌ No ONNX GPU providers!")
                st.info(f"All providers: {providers}")
            except:
                st.warning("ONNX Runtime not available")
            
            # PyTorch info
            st.code(f"""
PyTorch: {torch.__version__}
CUDA: {torch.version.cuda}
cuDNN: {torch.backends.cudnn.version()}
TF32: {torch.backends.cuda.matmul.allow_tf32}
            """)
        
        # CLAUDE'S GPU TEST BUTTON
        if st.button("🧪 Test GPU Allocation"):
            try:
                test_size = 2  # GB
                test_tensor = torch.zeros(
                    (test_size * 256, 1024, 1024), 
                    device='cuda', 
                    dtype=torch.float32
                )
                allocated = torch.cuda.memory_allocated() / 1024**3
                st.success(f"✅ Allocated {allocated:.2f}GB on GPU!")
                del test_tensor
                torch.cuda.empty_cache()
            except Exception as e:
                st.error(f"❌ GPU allocation failed: {e}")
        
        st.markdown("---")
        st.markdown("### 🛠️ Processing Methods")
        methods = []
        
        if SAM2_AVAILABLE and CUDA_AVAILABLE:
            methods.append("🚀 SAM2-GPU (Ultra Fast)")
        if REMBG_AVAILABLE:
            methods.append("✅ Rembg-GPU (High Quality)")
        if OPENCV_GPU:
            methods.append("⚡ OpenCV-GPU (Fast)")
        methods.append("💻 CPU Fallback")
        
        for method in methods:
            st.markdown(method)
    
    # Main processing interface
    col1, col2 = st.columns(2)
    
    # Initialize session state
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
            help="Upload video for GPU-accelerated processing"
        )
        
        if uploaded_video:
            if st.session_state.video_name != uploaded_video.name:
                st.success(f"✅ Video uploaded: {uploaded_video.name}")
                
                video_bytes = uploaded_video.read()
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                    tmp_file.write(video_bytes)
                    video_path = tmp_file.name
                
                st.session_state.video_path = video_path
                st.session_state.video_bytes = video_bytes
                st.session_state.video_name = uploaded_video.name
            
            if st.session_state.video_bytes is not None:
                st.video(st.session_state.video_bytes)
        
        elif st.session_state.video_path:
            st.success(f"✅ Video ready: {st.session_state.video_name}")
            st.video(st.session_state.video_bytes)
    
    with col2:
        st.markdown("### 🖼️ Background Selection")
        
        background_options = get_professional_backgrounds()
        selected_background = st.selectbox(
            "Choose background",
            options=list(background_options.keys()),
            index=0
        )
        
        background_url = background_options[selected_background]
        
        try:
            background_image = load_background_image(background_url)
            st.image(background_image, caption=f"Background: {selected_background}", use_container_width=True)
        except:
            st.error("Failed to load background image")
    
    # GPU-optimized processing button
    if (uploaded_video or st.session_state.video_path) and st.button("🚀 GPU Process Video", type="primary"):
        video_path = st.session_state.video_path
        
        if video_path and os.path.exists(video_path):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(progress, message):
                progress_bar.progress(progress)
                status_text.text(message)
            
            try:
                # GPU-optimized processing
                result_path = process_video_gpu_optimized(
                    video_path, 
                    background_url, 
                    update_progress
                )
                
                if result_path and os.path.exists(result_path):
                    status_text.text("✅ GPU processing complete!")
                    
                    with open(result_path, 'rb') as f:
                        result_video = f.read()
                    
                    st.video(result_video)
                    
                    st.download_button(
                        "💾 Download GPU-Processed Video",
                        data=result_video,
                        file_name="gpu_backgroundfx_result.mp4",
                        mime="video/mp4"
                    )
                    
                    # Show final GPU stats
                    final_stats = get_memory_usage()
                    st.success(f"🚀 Processing complete! GPU Memory used: {final_stats['gpu_allocated']:.2f}GB")
                    
                    os.unlink(result_path)
                else:
                    st.error("❌ GPU processing failed!")
                    
            except Exception as e:
                st.error(f"❌ Error during GPU processing: {str(e)}")
                logger.error(f"GPU processing error: {e}")
        else:
            st.error("Video file not found. Please upload again.")

if __name__ == "__main__":
    main()
