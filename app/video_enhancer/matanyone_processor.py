"""
Professional MatAnyone Processor for MyAvatar
Enterprise-grade wrapper for video matting to replace RVM
"""
import os
import cv2
import logging
import time
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MatAnyoneProcessor:
    """
    Professional wrapper for MatAnyone with full error handling,
    logging, and enterprise features for MyAvatar integration
    """
    
    def __init__(self, model_name: str = "PeiqingYang/MatAnyone"):
        """Initialize with configuration"""
        self.model_name = model_name
        self.processor = None
        self._initialize_processor()
        
    def _initialize_processor(self):
        """Initialize the MatAnyone processor with error handling"""
        try:
            logger.info("🚀 Initializing MatAnyone processor...")
            # Import here to handle missing dependency gracefully
            from matanyone import InferenceCore
            self.processor = InferenceCore(self.model_name)
            logger.info("✅ MatAnyone processor initialized successfully")
        except ImportError as e:
            logger.error(f"❌ MatAnyone not installed: {e}")
            logger.error("Run: pip install git+https://github.com/pq-yang/MatAnyone")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to initialize processor: {e}")
            raise
    
    def create_simple_first_frame_mask(self, video_path: str, output_path: str = None) -> str:
        """
        Create a simple first frame mask for testing
        In production, use SAM2 or manual annotation for better results
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            raise ValueError(f"Cannot read first frame from: {video_path}")
        
        # Create a simple center rectangle mask for testing
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        
        # Create mask covering center 70% of frame (adjust as needed)
        margin_x, margin_y = int(w * 0.15), int(h * 0.1)
        mask[margin_y:h-margin_y, margin_x:w-margin_x] = 255
        
        if output_path is None:
            output_path = str(Path(video_path).parent / "first_frame_mask.png")
        
        cv2.imwrite(output_path, mask)
        logger.info(f"✅ Simple mask created: {output_path}")
        logger.warning("⚠️ This is a basic mask. Use SAM2 or manual annotation for better results!")
        
        return output_path
    
    def segment_frame(self, frame: np.ndarray, mask_path: str = None) -> np.ndarray:
        """
        Segment a single frame using MatAnyone
        This replaces the RVM segment_frame method
        """
        try:
            # For single frame processing, we need to create a temporary video
            # MatAnyone is designed for video sequences, not single frames
            
            # Create temporary directory
            temp_dir = Path("temp_matanyone")
            temp_dir.mkdir(exist_ok=True)
            
            # Save frame as temporary video (single frame)
            temp_video = temp_dir / "temp_frame.mp4"
            h, w = frame.shape[:2]
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(temp_video), fourcc, 1.0, (w, h))
            out.write(frame)
            out.release()
            
            # Create simple mask if not provided
            if mask_path is None:
                mask_path = self.create_simple_first_frame_mask(str(temp_video))
            
            # Process with MatAnyone
            logger.info("🎬 Processing frame with MatAnyone...")
            foreground_path, alpha_path = self.processor.process_video(
                input_path=str(temp_video),
                mask_path=mask_path,
                output_path=str(temp_dir),
                max_size=1080,
                save_frames=False
            )
            
            # Read the alpha matte result
            alpha_video = cv2.VideoCapture(alpha_path)
            ret, alpha_frame = alpha_video.read()
            alpha_video.release()
            
            if not ret:
                raise ValueError("Failed to read MatAnyone alpha result")
            
            # Convert to grayscale alpha matte
            if len(alpha_frame.shape) == 3:
                alpha_matte = cv2.cvtColor(alpha_frame, cv2.COLOR_BGR2GRAY)
            else:
                alpha_matte = alpha_frame
            
            # Normalize to 0-1 range
            alpha_matte = alpha_matte.astype(np.float32) / 255.0
            
            # Clean up temporary files
            try:
                temp_video.unlink()
                Path(foreground_path).unlink()
                Path(alpha_path).unlink()
                if mask_path.startswith(str(temp_dir)):
                    Path(mask_path).unlink()
                temp_dir.rmdir()
            except:
                pass  # Ignore cleanup errors
            
            logger.info(f"✅ MatAnyone segmentation complete. Alpha range: {alpha_matte.min():.3f} to {alpha_matte.max():.3f}")
            
            return alpha_matte
            
        except Exception as e:
            logger.error(f"❌ MatAnyone frame segmentation failed: {e}")
            # Fallback: return a simple center mask
            h, w = frame.shape[:2]
            fallback_mask = np.zeros((h, w), dtype=np.float32)
            margin_x, margin_y = int(w * 0.2), int(h * 0.15)
            fallback_mask[margin_y:h-margin_y, margin_x:w-margin_x] = 1.0
            logger.warning("⚠️ Using fallback mask due to MatAnyone error")
            return fallback_mask
    
    def process_video_complete(self, 
                             video_path: str, 
                             mask_path: str = None,
                             output_dir: str = None,
                             max_size: int = 1080) -> Dict:
        """
        Complete video processing with MatAnyone
        """
        start_time = time.time()
        
        try:
            # Set defaults
            if output_dir is None:
                output_dir = str(Path(video_path).parent / "matanyone_output")
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Create mask if not provided
            if mask_path is None:
                logger.info("No mask provided, creating simple first-frame mask...")
                mask_path = self.create_simple_first_frame_mask(video_path)
            
            logger.info(f"🚀 Starting MatAnyone video processing...")
            logger.info(f"📹 Input: {video_path}")
            logger.info(f"🎭 Mask: {mask_path}")
            logger.info(f"📁 Output: {output_dir}")
            
            # Process the video with MatAnyone
            foreground_path, alpha_path = self.processor.process_video(
                input_path=video_path,
                mask_path=mask_path,
                output_path=output_dir,
                max_size=max_size,
                save_frames=False
            )
            
            processing_time = time.time() - start_time
            
            logger.info(f"✅ Processing completed in {processing_time:.2f}s")
            logger.info(f"📁 Foreground: {foreground_path}")
            logger.info(f"📁 Alpha: {alpha_path}")
            
            return {
                'success': True,
                'foreground_path': foreground_path,
                'alpha_path': alpha_path,
                'processing_time': processing_time,
                'output_dir': output_dir
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Processing failed after {processing_time:.2f}s: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'processing_time': processing_time
            }

# Test the processor
if __name__ == "__main__":
    processor = MatAnyoneProcessor()
    print("✅ MatAnyone processor ready for MyAvatar integration!")
