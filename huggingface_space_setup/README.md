---
title: Video Background Replacement
emoji: 🍹
colorFrom: blue
colorTo: purple
sdk: streamlit
sdk_version: 1.47.1
app_file: app.py
pinned: false
license: mit
---

# Video Background Replacement

A simple Streamlit app that replaces video backgrounds using MatAnyone AI with direct MyAvatar integration.

## Features
- Upload video files (MP4, AVI, MOV, MKV)
- Upload background images (PNG, JPG, JPEG)
- AI-powered background replacement using MatAnyone
- Preserves original audio from input videos
- Web-optimized MP4 output with instant streaming capability
- Download processed video
- 💾 Save to MyAvatar - Direct integration with MyAvatar library

## Usage
1. Upload your video file
2. Upload your desired background image
3. Click "🍹 PROCESS VIDEO"
4. Choose your action:
   - ⬇️ Download - Save to your device
   - 💾 Save to My Videos - Add directly to your MyAvatar library

## 🎬 Video Output Quality
This app automatically creates professional-quality, web-compatible MP4 videos:

- **H.264 Encoding**: Industry-standard codec for maximum browser compatibility
- **Audio Preservation**: Automatically extracts and maintains original audio tracks
- **Moov Atom Optimization**: Fixes MP4 metadata positioning using qtfaststart for instant web streaming
- **Smart Fallbacks**: Gracefully handles different system configurations (FFmpeg/moviepy available or not)

### Why This Matters
Input videos display perfectly in browsers, but AI-generated videos often have metadata and audio issues. Our solution ensures output videos have the same streaming compatibility and audio quality as professional camera recordings.

## 🔗 MyAvatar Integration
- **One-Click Save**: Processed videos can be saved directly to your MyAvatar library
- **No Manual Steps**: Skip downloading and re-uploading - save happens automatically
- **Seamless Workflow**: Process → Save → Use in other MyAvatar features
- **Library Management**: Videos appear in "My Videos" instantly

## Technology
- **MatAnyone**: Professional video matting AI model
- **Streamlit 1.47.1**: Simple web interface
- **GPU Accelerated**: Runs on NVIDIA hardware
- **qtfaststart**: Pure Python moov atom optimizer for web compatibility
- **moviepy**: Audio preservation and video editing capabilities
- **Multiple Codec Support**: H.264, XVID fallbacks for maximum compatibility
- **MyAvatar API**: Direct integration for seamless library managementation.
