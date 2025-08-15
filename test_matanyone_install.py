#!/usr/bin/env python3
"""
MatAnyone Installation Test Script
Quick test to verify MatAnyone works with Python 3.13.3
"""
import sys
import traceback

def test_matanyone_installation():
    """Test MatAnyone installation and basic functionality"""
    print("🚀 Testing MatAnyone Installation")
    print(f"Python version: {sys.version}")
    print("-" * 50)
    
    try:
        # Test 1: Import MatAnyone
        print("📦 Testing import...")
        from matanyone import InferenceCore
        print("✅ MatAnyone imported successfully")
        
        # Test 2: Initialize processor
        print("🧠 Testing processor initialization...")
        processor = InferenceCore("PeiqingYang/MatAnyone")
        print("✅ Processor initialized successfully")
        
        # Test 3: Check available methods
        print("🔍 Available methods:")
        methods = [method for method in dir(processor) if not method.startswith('_')]
        for method in methods:
            print(f"   - {method}")
        
        print("\n🎉 MatAnyone installation test PASSED!")
        print("Ready to process videos with superior segmentation!")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("💡 Try: pip install git+https://github.com/pq-yang/MatAnyone")
        return False
        
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        print(f"Error details: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = test_matanyone_installation()
    sys.exit(0 if success else 1)
