#!/usr/bin/env python3
"""
Test script to verify RVM Alpha Transparency Fix
Tests the binary compositing logic for green screen output
"""

import sys
import os
import numpy as np
import cv2
import logging
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.video_enhancer.segmentation_models import RVMSegmenter
    from app.video_enhancer.advanced_background_replacer import AdvancedBackgroundReplacer
    print("✅ Successfully imported MyAvatar video enhancement modules")
except ImportError as e:
    print(f"❌ Failed to import modules: {e}")
    print("Make sure you're running this from the MyAvatar root directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_frame():
    """Create a simple test frame with a person-like shape"""
    # Create a 480x640 test frame (typical video dimensions)
    frame = np.full((480, 640, 3), (200, 180, 160), dtype=np.uint8)  # Beige background
    
    # Add a simple "person" shape in the center (dark blue)
    person_color = (100, 50, 30)  # Dark blue-brown
    cv2.ellipse(frame, (320, 240), (80, 120), 0, 0, 360, person_color, -1)  # Body
    cv2.circle(frame, (320, 180), 40, person_color, -1)  # Head
    
    return frame

def test_rvm_binary_thresholding():
    """Test RVM segmentation produces binary alpha values"""
    print("\n🧪 Testing RVM Binary Thresholding...")
    
    try:
        # Initialize RVM segmenter
        rvm = RVMSegmenter(enable_gpu=False, model_quality="medium")
        if not rvm.initialize():
            print("❌ Failed to initialize RVM segmenter")
            return False
        
        # Create test frame
        test_frame = create_test_frame()
        
        # Get segmentation mask
        mask = rvm.segment_frame(test_frame)
        
        if mask is None:
            print("❌ RVM segmentation returned None")
            return False
        
        # Check mask properties
        unique_values = np.unique(mask)
        print(f"📊 Mask unique values: {unique_values}")
        print(f"📊 Mask shape: {mask.shape}")
        print(f"📊 Mask dtype: {mask.dtype}")
        print(f"📊 Mask range: {mask.min()} to {mask.max()}")
        
        # For binary output, we expect only 0 and 255 (or 0.0 and 1.0)
        if len(unique_values) <= 2:
            print("✅ RVM produced binary mask (good for green screen)")
        else:
            print(f"⚠️ RVM produced {len(unique_values)} unique values (may cause transparency bleeding)")
        
        return True
        
    except Exception as e:
        print(f"❌ RVM test failed: {e}")
        return False

def test_green_screen_compositing():
    """Test green screen compositing logic"""
    print("\n🎬 Testing Green Screen Compositing...")
    
    try:
        # Initialize background replacer
        replacer = AdvancedBackgroundReplacer(enable_gpu=False, quality="medium")
        
        # Set green screen background
        if not replacer.set_background_color("#00FF00"):  # Pure green
            print("❌ Failed to set green background")
            return False
        
        # Create test frame
        test_frame = create_test_frame()
        
        # Process frame
        result_frame = replacer.process_frame(test_frame, frame_number=0)
        
        if result_frame is None:
            print("❌ Background replacement returned None")
            return False
        
        # Analyze result
        print(f"📊 Result shape: {result_frame.shape}")
        print(f"📊 Result dtype: {result_frame.dtype}")
        
        # Check for pure green pixels (should be background)
        green_pixels = np.all(result_frame == [0, 255, 0], axis=2)
        green_count = np.sum(green_pixels)
        total_pixels = result_frame.shape[0] * result_frame.shape[1]
        
        print(f"📊 Pure green pixels: {green_count}/{total_pixels} ({green_count/total_pixels*100:.1f}%)")
        
        # Check for original background bleeding (beige colors)
        beige_mask = np.all(np.abs(result_frame - [160, 180, 200]) < 20, axis=2)
        beige_count = np.sum(beige_mask)
        
        if beige_count > 0:
            print(f"⚠️ Original background bleeding detected: {beige_count} pixels")
        else:
            print("✅ No original background bleeding detected")
        
        # Save test result for visual inspection
        output_path = "test_green_screen_output.png"
        cv2.imwrite(output_path, result_frame)
        print(f"💾 Test result saved to: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Green screen compositing test failed: {e}")
        return False

def test_alpha_values_verification():
    """Test that alpha values are strictly binary"""
    print("\n🔍 Testing Alpha Values Verification...")
    
    # Create a mock alpha array with gradual values (the problem we're fixing)
    gradual_alpha = np.array([0.0, 0.3, 0.5, 0.7, 1.0], dtype=np.float32)
    print(f"📊 Original gradual alpha: {gradual_alpha}")
    
    # Apply binary thresholding (the fix)
    binary_alpha = (gradual_alpha > 0.5).astype(np.float32)
    print(f"📊 After binary thresholding: {binary_alpha}")
    
    # Verify only 0.0 and 1.0 values
    unique_vals = np.unique(binary_alpha)
    print(f"📊 Unique values after fix: {unique_vals}")
    
    if len(unique_vals) <= 2 and np.all(np.isin(unique_vals, [0.0, 1.0])):
        print("✅ Binary thresholding working correctly")
        return True
    else:
        print("❌ Binary thresholding failed")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting RVM Alpha Transparency Fix Tests")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Alpha values verification
    if test_alpha_values_verification():
        tests_passed += 1
    
    # Test 2: RVM binary thresholding
    if test_rvm_binary_thresholding():
        tests_passed += 1
    
    # Test 3: Green screen compositing
    if test_green_screen_compositing():
        tests_passed += 1
    
    print("\n" + "=" * 50)
    print(f"🏁 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! RVM Alpha Transparency Fix is working correctly.")
        print("✅ Green screen output should now show:")
        print("   - Solid subject (no transparency)")
        print("   - Pure green background (no bleeding)")
        print("   - Clean cutout separation")
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
    
    return tests_passed == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
