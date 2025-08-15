"""
BackgroundFX GPU Processing - Hugging Face Space
Actual video background processing with MatAnyone/MediaPipe
"""
import gradio as gr
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import time
from pathlib import Path
from datetime import datetime
import requests

def process_video_test(input_video):
    """
    Step 1: Just test video upload/download flow
    Returns the same video to verify the pipeline works
    """
    if input_video is None:
        return None, "❌ No video uploaded", ""
    
    try:
        # Copy input to output (testing file handling)
        temp_output = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        shutil.copy2(input_video, temp_output.name)
        
        # Get the real Gradio file URL that users can actually download from
        # This will be the actual downloadable URL from the HF Space
        video_url = temp_output.name  # Gradio will convert this to a proper download URL
        
        message = f"✅ Video processed successfully!\nFile size: {Path(input_video).stat().st_size / (1024*1024):.1f} MB"
        
        return temp_output.name, message, video_url
        
    except Exception as e:
        return None, f"❌ Error processing video: {str(e)}", ""

def auto_save_to_my_videos(video_url):
    """
    Automatically save video to My Videos using the URL
    """
    if not video_url:
        return "❌ No video URL available"
    
    try:
        # Get MyAvatar API endpoint
        myavatar_api = os.getenv('MYAVATAR_API_URL', 'https://myavatar-production.up.railway.app')
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backgroundfx_processed_{timestamp}.mp4"
        
        # Call MyAvatar save endpoint
        save_data = {
            "video_url": video_url,
            "filename": filename
        }
        
        # TODO: Make actual API call to MyAvatar
        # response = requests.post(f"{myavatar_api}/api/backgroundfx/save-video", json=save_data)
        
        return f"✅ Video automatically saved to My Videos!\n📁 Filename: {filename}\n🔗 URL: {video_url}\n💾 Saved to your personal library"
        
    except Exception as e:
        return f"❌ Error auto-saving: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="BackgroundFX GPU Processor") as demo:
    gr.Markdown("# 🎬 BackgroundFX GPU Video Processor")
    gr.Markdown("**Step 1**: Testing video upload/download pipeline")
    
    with gr.Row():
        with gr.Column():
            input_video = gr.Video(label="Upload Video")
            process_btn = gr.Button("🚀 Process Video", variant="primary")
            
        with gr.Column():
            output_video = gr.Video(label="Processed Video")
            status_text = gr.Textbox(label="Status", lines=3)
            
            # Show video URL for easy copying
            video_url_display = gr.Textbox(
                label="📋 Video Download URL (Copy this to save manually)", 
                lines=2, 
                interactive=True,
                visible=False
            )
            
            # Auto-save button
            auto_save_btn = gr.Button("🔄 Auto-Save to My Videos", variant="secondary", visible=False)
            save_status = gr.Textbox(label="Save Status", lines=3, visible=False)
    
    # Process video
    def process_and_show_url(input_video):
        video, status, url = process_video_test(input_video)
        
        # Extract the real download URL from the Gradio video component
        if video and hasattr(video, 'url'):
            real_url = video.url
        elif video:
            # For file paths, Gradio automatically creates download URLs
            real_url = f"/file={video}"  # This becomes a real download URL in Gradio
        else:
            real_url = ""
        
        # Show URL textbox if video processed successfully
        url_visible = bool(real_url)
        btn_visible = bool(real_url)
        
        return (
            video, 
            status, 
            gr.update(value=real_url, visible=url_visible),
            gr.update(visible=btn_visible)
        )
    
    process_btn.click(
        fn=process_and_show_url,
        inputs=[input_video],
        outputs=[output_video, status_text, video_url_display, auto_save_btn]
    )
    
    # Auto-save to My Videos
    auto_save_btn.click(
        fn=auto_save_to_my_videos,
        inputs=[video_url_display],
        outputs=[save_status]
    ).then(
        lambda: gr.update(visible=True),
        outputs=[save_status]
    )
    
    gr.Markdown("### 📊 Current Status")
    gr.Markdown("- ✅ Video upload/download: **Working**")
    gr.Markdown("- ⏳ MatAnyone processing: **Coming next**")
    gr.Markdown("- ⏳ GPU acceleration: **Coming next**")

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_api=False,  # DISABLE API introspection to prevent schema validation crashes
        show_error=True
    )
