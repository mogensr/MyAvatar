# Claude Prompt: Fix HuggingFace Space Restart Loop Issue

## Problem Analysis
My HuggingFace Space for BackgroundFX video processing is stuck in an infinite restart loop, causing Streamlit context errors and making the service inaccessible. The root cause is in the current `app.py` file which contains this problematic code:

```python
# PROBLEMATIC CODE CAUSING RESTART LOOP:
if clean_install_onnx_gpu():
    print("🔄 Restarting to pick up new installation...")
    os.execv(sys.executable, [sys.executable] + sys.argv)  # ← THIS CAUSES INFINITE LOOP
```

**What's happening:**
1. App starts
2. ONNX installation checker runs
3. `os.execv()` restarts the entire Python process
4. App starts again → INFINITE LOOP
5. Streamlit never gets a chance to initialize properly
6. Results in "missing ScriptRunContext" errors

## Current Symptoms
- HF Space shows as "running" but is inaccessible
- Logs show: `Session state does not function when running a script without streamlit run`
- Massive spam of: `Thread 'MainThread': missing ScriptRunContext!`
- GPU detection works but falls back to CPU
- Connection errors when trying to access the Space

## Proposed Solution
Replace the problematic restart-heavy approach with a clean, stable implementation that:

1. **Removes all `os.execv()` restart loops**
2. **Implements proper GPU detection without restarts**
3. **Uses clean ONNX Runtime initialization**
4. **Maintains professional UI and functionality**
5. **Leverages the 32GB RAM and NVIDIA L4 GPU properly**

## Requirements for the Fix
- **CRITICAL:** No `os.execv()` or process restarts
- **CRITICAL:** Must work in HuggingFace Space environment
- **CRITICAL:** Proper Streamlit initialization without context errors
- GPU acceleration with NVIDIA L4 when available
- Professional UI with system stats
- Batch processing capabilities
- Multiple AI model support (u2net, u2net_human_seg, etc.)
- Efficient RAM usage (up to 32GB available)
- Clean error handling without crashes

## Technical Specifications
- **Environment:** HuggingFace Space with Streamlit SDK
- **Hardware:** NVIDIA L4 GPU, 32GB RAM
- **Framework:** Streamlit for UI
- **AI Models:** Rembg with ONNX Runtime
- **Output:** Professional background removal service

## Success Criteria
1. ✅ HF Space loads without restart loops
2. ✅ Streamlit UI initializes properly
3. ✅ GPU detection and utilization works
4. ✅ Background removal processes videos/images
5. ✅ Professional UI with system monitoring
6. ✅ Stable operation without context errors

## Code Template to Build Upon
I have a clean implementation template that removes all restart logic and implements proper GPU detection, model loading, and Streamlit UI. The template includes:

- Clean GPU setup without restarts
- Proper ONNX Runtime provider configuration
- Multiple model loading and caching
- Professional UI with system stats
- Batch processing capabilities
- Error handling without crashes

**Please create a complete, production-ready `app.py` file that fixes the restart loop issue and implements a stable, professional background removal service for HuggingFace Spaces.**

The service was working perfectly yesterday, so this is a regression caused by the restart loop logic. The fix should restore full functionality while maintaining the professional quality and GPU acceleration.
