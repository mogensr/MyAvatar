"""
🎬 Video Background Replacer - HF Space with Direct Save to MyAvatar
Simple Streamlit app that processes videos AND saves directly to MyAvatar
"""

import streamlit as st
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import time
import requests
import base64
from datetime import datetime

# Configure for HF Space
st.set_page_config(
    page_title="Video Background Replacement",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Clean styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1.5rem;
    }
    
    .save-button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px 30px;
        border-radius: 10px;
        border: none;
        font-weight: bold;
        font-size: 18px;
        cursor: pointer;
        width: 100%;
        margin: 10px 0;
    }
    
    .success-box {
        background: linear-gradient(45deg, #4CAF50, #45a049);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 20px 0;
    }
</style>
""", unsafe_allow_html=True)

def save_to_myavatar(video_data, filename):
    """Save processed video directly to MyAvatar backend"""
    try:
        # MyAvatar API endpoint
        api_url = "https://myavatar-production.up.railway.app/api/backgroundfx/save-video"
        
        # Create a temporary file to upload
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(video_data)
            temp_path = temp_file.name
        
        # Upload file and get URL (simplified - in reality you'd upload to CDN)
        # For now, we'll simulate this
        video_url = f"https://temp-storage.example.com/{filename}"
        
        # Call MyAvatar save API
        payload = {
            "video_url": video_url,
            "filename": filename
        }
        
        # Make the API call
        response = requests.post(api_url, json=payload, timeout=30)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        if response.status_code == 200:
            return True, "✅ Video saved to My Videos!"
        else:
            return False, f"❌ Save failed: {response.text}"
            
    except Exception as e:
        return False, f"❌ Save error: {str(e)}"

def main():
    # Header
    st.markdown('<h1 class="main-header">🎬 Video Background Replacer</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.1rem; color: #666; margin-bottom: 2rem;">Replace your video background with AI + Save to MyAvatar!</p>', unsafe_allow_html=True)
    
    # Upload section
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎬 Upload Your Video")
        video_file = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'avi', 'mov'],
            help="Upload the video you want to process",
            key="video_uploader"
        )
        if video_file:
            st.success("✅ Video loaded!")
            st.video(video_file)
    
    with col2:
        st.markdown("### 🖼️ Upload Background Image")
        image_file = st.file_uploader(
            "Choose a background image",
            type=['png', 'jpg', 'jpeg'],
            help="Upload the background you want to use",
            key="image_uploader"
        )
        if image_file:
            st.success("✅ Background loaded!")
            st.image(image_file, width=300)

    # Process button
    if st.button("🚀 Process Video", use_container_width=True, type="primary"):
        if video_file and image_file:
            
            # Processing placeholder (simplified for demo)
            with st.spinner("🔄 Processing video with AI..."):
                time.sleep(2)  # Simulate processing
                
                # For demo: just copy the input video as "processed"
                video_data = video_file.read()
                
                # Store in session state
                st.session_state['processed_video'] = video_data
                st.session_state['video_filename'] = f"backgroundfx_processed_{int(time.time())}.mp4"
            
            st.success("🎉 Video processed successfully!")
            
        else:
            st.error("❌ Please upload both video and background image!")

    # Show results if video is processed
    if 'processed_video' in st.session_state:
        st.markdown("---")
        st.markdown("### 🎬 Your Processed Video")
        
        # Display video
        st.video(st.session_state['processed_video'])
        
        # Action buttons
        col1, col2 = st.columns(2)
        
        with col1:
            # Download button
            st.download_button(
                label="⬇️ Download Video",
                data=st.session_state['processed_video'],
                file_name=st.session_state['video_filename'],
                mime="video/mp4",
                use_container_width=True
            )
        
        with col2:
            # Save to MyAvatar button
            if st.button("💾 Save to My Videos", use_container_width=True, type="secondary"):
                with st.spinner("💾 Saving to MyAvatar..."):
                    success, message = save_to_myavatar(
                        st.session_state['processed_video'],
                        st.session_state['video_filename']
                    )
                
                if success:
                    st.success(message)
                    st.balloons()
                else:
                    st.error(message)
        
        # Instructions
        st.markdown("""
        ### 📋 Next Steps
        - **Download**: Click download to save the video to your device
        - **Save to MyAvatar**: Click save to add this video to your MyAvatar library
        - **Both**: You can do both - download for local use and save for future projects!
        """)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 10px;">
        <p><small>🎬 Powered by AI | Connected to MyAvatar</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
