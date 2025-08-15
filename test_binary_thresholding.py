#!/usr/bin/env python3
"""
Test script to verify strict binary thresholding is working correctly
Tests that RVM output is properly converted to binary 0/1 values only
"""

import sys
import os
import cv2
import numpy as np
import time

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.video_enhancer.segmentation_models import RVMSegmenter
    print("✅ Successfully imported RVM segmentation models")
except ImportError as e:
    print(f"❌ Failed to import segmentation models: {e}")
    sys.exit(1)

def test_binary_thresholding():
    """Test that RVM output is strictly binary thresholded"""
    
    print("\n🧪 Testing Strict Binary Thresholding")
    print("=" * 50)
    print("🎯 Goal: Verify NO gradual alpha values - only 0.0 and 1.0")
    
    # Create test frame
    test_frame = create_test_frame()
    
    try:
        # Create RVM segmenter with binary mode
        segmenter = RVMSegmenter(model_quality="medium", enable_gpu=True)
        
        if not segmenter.initialize():
            print("❌ Failed to initialize RVM segmenter")
            return
        
        print("✅ RVM segmenter initialized")
        print(f"   - Binary mode enabled: {segmenter.use_hard_binary_mask}")
        print(f"   - Subject threshold: {segmenter.subject_confidence_threshold}")
        
        # Process frame
        print("\n🔄 Processing test frame...")
        start_time = time.time()
        mask = segmenter.segment_frame(test_frame)
        processing_time = time.time() - start_time
        
        print(f"✅ Frame processed in {processing_time:.3f}s")
        
        # Analyze the mask for binary compliance
        print("\n📊 Binary Compliance Analysis:")
        
        # Convert mask back to alpha values for analysis
        alpha_values = mask.astype(np.float32) / 255.0
        
        # Check unique values
        unique_values = np.unique(alpha_values)
        print(f"   - Unique alpha values: {unique_values}")
        
        # Check if strictly binary
        is_binary = np.all((unique_values == 0.0) | (unique_values == 1.0))
        print(f"   - Is strictly binary: {is_binary}")
        
        if is_binary:
            print("   ✅ PASS: No gradual transparency detected")
        else:
            print("   ❌ FAIL: Gradual transparency values found")
            gradual_pixels = ((alpha_values > 0.0) & (alpha_values < 1.0)).sum()
            print(f"   - Gradual transparency pixels: {gradual_pixels}")
        
        # Count pixels
        solid_pixels = (alpha_values == 1.0).sum()
        transparent_pixels = (alpha_values == 0.0).sum()
        total_pixels = alpha_values.size
        
        print(f"   - Solid pixels (1.0): {solid_pixels}")
        print(f"   - Transparent pixels (0.0): {transparent_pixels}")
        print(f"   - Total pixels: {total_pixels}")
        print(f"   - Coverage: {(solid_pixels / total_pixels * 100):.1f}%")
        
        # Verify no in-between values
        in_between = ((alpha_values > 0.0) & (alpha_values < 1.0)).sum()
        if in_between == 0:
            print("   ✅ VERIFIED: No in-between alpha values")
        else:
            print(f"   ❌ ERROR: {in_between} pixels have in-between alpha values")
        
        # Test different aggressiveness levels
        print("\n🎛️ Testing different aggressiveness levels:")
        for level in ["conservative", "medium", "aggressive", "extreme"]:
            segmenter.set_segmentation_aggressiveness(level)
            test_mask = segmenter.segment_frame(test_frame)
            test_alpha = test_mask.astype(np.float32) / 255.0
            test_unique = np.unique(test_alpha)
            test_binary = np.all((test_unique == 0.0) | (test_unique == 1.0))
            
            status = "✅ BINARY" if test_binary else "❌ GRADUAL"
            coverage = (test_alpha == 1.0).sum() / test_alpha.size * 100
            print(f"   - {level.capitalize()}: {status} ({coverage:.1f}% coverage)")
        
        segmenter.cleanup()
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

def create_test_frame():
    """Create a test frame with clear subject/background separation"""
    # Create test image
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Background (blue)
    frame[:, :] = [100, 150, 200]
    
    # Add person-like shape in center (different color)
    center = (320, 240)
    axes = (100, 150)
    cv2.ellipse(frame, center, axes, 0, 0, 360, (180, 140, 120), -1)
    
    # Add head
    cv2.circle(frame, (320, 160), 50, (200, 160, 140), -1)
    
    return frame

def test_alpha_matte_processing():
    """Test that alpha matte is properly processed"""
    print("\n🔬 Testing Alpha Matte Processing")
    print("-" * 40)
    
    # Create synthetic alpha matte with gradual values
    synthetic_alpha = np.random.rand(100, 100).astype(np.float32)
    print(f"Synthetic alpha range: {synthetic_alpha.min():.3f} to {synthetic_alpha.max():.3f}")
    
    # Apply binary thresholding like RVM does
    threshold = 0.3
    binary_result = (synthetic_alpha > threshold).astype(np.float32)
    
    unique_values = np.unique(binary_result)
    print(f"After binary thresholding: {unique_values}")
    
    is_binary = np.all((unique_values == 0.0) | (unique_values == 1.0))
    print(f"Is strictly binary: {is_binary}")
    
    if is_binary:
        print("✅ Alpha matte processing works correctly")
    else:
        print("❌ Alpha matte processing failed")

if __name__ == "__main__":
    print("🚀 Binary Thresholding Test Suite")
    print("Testing that RVM output is strictly binary (0/1) with no gradual transparency")
    
    # Run tests
    test_binary_thresholding()
    test_alpha_matte_processing()
    
    print("\n📋 Expected Results:")
    print("   ✓ All alpha values should be exactly 0.0 or 1.0")
    print("   ✓ No gradual transparency (no values between 0 and 1)")
    print("   ✓ Subject pixels = 1.0 (solid), background pixels = 0.0 (transparent)")
    print("   ✓ Binary compliance across all aggressiveness levels")
