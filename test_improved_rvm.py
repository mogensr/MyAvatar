#!/usr/bin/env python3
"""
Test script for improved RVM background segmentation
Tests the new aggressive parameters and morphological cleanup
"""

import sys
import os
import cv2
import numpy as np
import time

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.video_enhancer.segmentation_models import RVMSegmenter, create_segmentation_model
    print("✅ Successfully imported RVM segmentation models")
except ImportError as e:
    print(f"❌ Failed to import segmentation models: {e}")
    sys.exit(1)

def test_rvm_improvements():
    """Test the improved RVM segmentation with subject preservation"""
    
    print("\n🧪 Testing RVM Subject Preservation & Background Removal")
    print("=" * 60)
    print("🎯 Goal: Subject 100% opaque, background completely removed")
    
    # Create a test frame (you can replace this with actual video frame)
    test_frame = create_test_frame()
    
    # Test different quality settings
    quality_levels = ["low", "medium", "high"]
    aggressiveness_levels = ["conservative", "medium", "aggressive", "extreme"]
    
    for quality in quality_levels:
        print(f"\n📊 Testing Quality Level: {quality.upper()}")
        print("-" * 40)
        
        try:
            # Create RVM segmenter
            segmenter = RVMSegmenter(model_quality=quality, enable_gpu=True)
            
            if not segmenter.initialize():
                print(f"❌ Failed to initialize RVM segmenter for {quality} quality")
                continue
            
            print(f"✅ RVM segmenter initialized successfully")
            print(f"   - Subject preservation: {segmenter.enable_subject_preservation}")
            print(f"   - Subject confidence threshold: {segmenter.subject_confidence_threshold}")
            print(f"   - Background confidence threshold: {segmenter.background_confidence_threshold}")
            print(f"   - Alpha matting threshold: {segmenter.alpha_matting_threshold}")
            print(f"   - Multi-pass enabled: {segmenter.enable_multi_pass}")
            print(f"   - Morphological cleanup: {segmenter.enable_morphological_cleanup}")
            
            # Test segmentation
            start_time = time.time()
            mask = segmenter.segment_frame(test_frame)
            processing_time = time.time() - start_time
            
            # Analyze results for subject preservation
            mask_coverage = (mask > 0).sum() / mask.size * 100
            subject_opacity = analyze_subject_opacity(mask, test_frame)
            background_removal = analyze_background_removal(mask, test_frame)
            
            print(f"   - Processing time: {processing_time:.3f}s")
            print(f"   - Total mask coverage: {mask_coverage:.1f}%")
            print(f"   - Subject opacity score: {subject_opacity:.2f}/10 (10=fully opaque)")
            print(f"   - Background removal score: {background_removal:.2f}/10 (10=completely removed)")
            
            # Test different aggressiveness levels
            print(f"\n   Testing aggressiveness adjustments:")
            for aggressiveness in aggressiveness_levels:
                segmenter.set_segmentation_aggressiveness(aggressiveness)
                test_mask = segmenter.segment_frame(test_frame)
                test_coverage = (test_mask > 0).sum() / test_mask.size * 100
                print(f"     - {aggressiveness}: {test_coverage:.1f}% coverage")
            
            # Cleanup
            segmenter.cleanup()
            print(f"✅ {quality} quality test completed successfully")
            
        except Exception as e:
            print(f"❌ Error testing {quality} quality: {e}")
            continue

def create_test_frame():
    """Create a synthetic test frame for testing"""
    # Create a simple test image with a person-like shape in the center
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Background (blue sky)
    frame[:, :] = [135, 206, 235]  # Sky blue
    
    # Add some background texture
    noise = np.random.randint(0, 30, (480, 640, 3), dtype=np.uint8)
    frame = cv2.add(frame, noise)
    
    # Add a person-like shape (ellipse) in the center
    center = (320, 240)
    axes = (80, 120)
    cv2.ellipse(frame, center, axes, 0, 0, 360, (180, 140, 120), -1)  # Skin tone
    
    # Add head
    cv2.circle(frame, (320, 180), 40, (200, 160, 140), -1)
    
    return frame

def analyze_subject_opacity(mask, frame):
    """Analyze how opaque the subject appears (should be 10/10 for fully opaque)"""
    # Define subject region (center area where we placed the test subject)
    h, w = frame.shape[:2]
    center_y, center_x = h // 2, w // 2
    subject_region = mask[center_y-60:center_y+60, center_x-40:center_x+40]
    
    if subject_region.size == 0:
        return 0.0
    
    # Check opacity in subject region - should be 255 (fully opaque)
    subject_pixels = subject_region[subject_region > 0]
    if len(subject_pixels) == 0:
        return 0.0  # No subject detected
    
    # Score based on how close to 255 the subject pixels are
    avg_opacity = subject_pixels.mean()
    opacity_score = (avg_opacity / 255.0) * 10
    
    return opacity_score

def analyze_background_removal(mask, frame):
    """Analyze how well background is removed (should be 10/10 for complete removal)"""
    # Define background regions (corners and edges)
    h, w = frame.shape[:2]
    
    # Sample background regions
    bg_regions = [
        mask[0:50, 0:50],           # Top-left corner
        mask[0:50, w-50:w],         # Top-right corner  
        mask[h-50:h, 0:50],         # Bottom-left corner
        mask[h-50:h, w-50:w],       # Bottom-right corner
        mask[0:30, :],              # Top edge
        mask[h-30:h, :],            # Bottom edge
        mask[:, 0:30],              # Left edge
        mask[:, w-30:w]             # Right edge
    ]
    
    total_bg_pixels = 0
    removed_bg_pixels = 0
    
    for region in bg_regions:
        if region.size > 0:
            total_bg_pixels += region.size
            removed_bg_pixels += (region == 0).sum()
    
    if total_bg_pixels == 0:
        return 0.0
    
    # Score based on percentage of background pixels removed
    removal_ratio = removed_bg_pixels / total_bg_pixels
    removal_score = removal_ratio * 10
    
    return removal_score

def analyze_mask_quality(mask):
    """Analyze the overall quality of the segmentation mask"""
    # Simple quality metrics
    edge_strength = cv2.Laplacian(mask, cv2.CV_64F).var()
    smoothness = 1.0 / (1.0 + edge_strength / 1000.0)
    
    # Coverage analysis
    coverage = (mask > 0).sum() / mask.size
    coverage_score = min(1.0, coverage * 2)  # Prefer some coverage but not too much
    
    # Combine metrics
    quality_score = (smoothness * 0.6 + coverage_score * 0.4) * 10
    return quality_score

def test_morphological_cleanup():
    """Test the morphological cleanup functionality"""
    print("\n🔧 Testing Morphological Cleanup")
    print("-" * 40)
    
    # Create a noisy test mask
    test_mask = np.zeros((100, 100), dtype=np.uint8)
    test_mask[20:80, 20:80] = 255  # Main object
    
    # Add noise
    noise_points = np.random.randint(0, 100, (50, 2))
    for point in noise_points:
        test_mask[point[0], point[1]] = 255
    
    # Create RVM segmenter and test cleanup
    try:
        segmenter = RVMSegmenter()
        cleaned_mask = segmenter._apply_morphological_cleanup(test_mask)
        
        noise_before = np.sum(test_mask > 0)
        noise_after = np.sum(cleaned_mask > 0)
        
        print(f"✅ Morphological cleanup test:")
        print(f"   - Pixels before cleanup: {noise_before}")
        print(f"   - Pixels after cleanup: {noise_after}")
        print(f"   - Noise reduction: {((noise_before - noise_after) / noise_before * 100):.1f}%")
        
    except Exception as e:
        print(f"❌ Morphological cleanup test failed: {e}")

if __name__ == "__main__":
    print("🚀 RVM Segmentation Improvement Test Suite")
    print("Testing enhanced background removal with aggressive parameters")
    
    # Run tests
    test_rvm_improvements()
    test_morphological_cleanup()
    
    print("\n✅ All tests completed!")
    print("\n📋 Summary of Improvements:")
    print("   ✓ Lowered confidence thresholds (0.5 → 0.25/0.2/0.15)")
    print("   ✓ Raised alpha matting thresholds (0.5 → 0.75/0.8/0.9)")
    print("   ✓ Added multi-pass processing for accuracy")
    print("   ✓ Implemented morphological cleanup")
    print("   ✓ Added dynamic aggressiveness control")
    print("   ✓ Enhanced edge refinement")
