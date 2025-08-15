"""
MINIMAL DEBUG VERSION - Test Gradio Button
"""
import gradio as gr
import time
import torch

def simple_test(video_file, bg_image, use_matanyone=True):
    """Minimal test function to debug button"""
    print("🚀 BUTTON CLICKED! Function called successfully")
    
    try:
        # Basic validation
        if video_file is None:
            return None, None, "❌ No video uploaded"
        if bg_image is None:
            return None, None, "❌ No background image uploaded"
        
        # Test file access
        video_path = video_file.name if hasattr(video_file, 'name') else str(video_file)
        bg_path = bg_image.name if hasattr(bg_image, 'name') else str(bg_image)
        
        print(f"📁 Video: {video_path}")
        print(f"📁 Background: {bg_path}")
        print(f"🎯 MatAnyone option: {use_matanyone}")
        print(f"🚀 GPU available: {torch.cuda.is_available()}")
        
        # Simulate processing
        time.sleep(2)
        
        status = f"""✅ DEBUG TEST SUCCESSFUL!
📁 Video path: {video_path}
📁 Background path: {bg_path}
🎯 MatAnyone enabled: {use_matanyone}
🚀 GPU available: {torch.cuda.is_available()}
⏱️ Test completed in 2 seconds"""
        
        return video_path, video_path, status
        
    except Exception as e:
        error_msg = f"❌ DEBUG ERROR: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return None, None, error_msg

# Minimal Gradio interface for debugging
with gr.Blocks(title="DEBUG - Button Test") as demo:
    gr.Markdown("# 🔧 DEBUG: Button Test")
    gr.Markdown("**Testing if Process Video button works at all**")
    
    with gr.Row():
        with gr.Column():
            video_input = gr.Video(label="📹 Test Video")
            bg_input = gr.Image(label="🖼️ Test Background", type="filepath")
            
            with gr.Row():
                use_matanyone = gr.Checkbox(
                    label="🚀 Test MatAnyone Option", 
                    value=True
                )
                process_btn = gr.Button("🔧 TEST BUTTON", variant="primary")
            
        with gr.Column():
            output_video = gr.Video(label="📺 Test Output")
            download_file = gr.File(label="💾 Test Download")
            status_text = gr.Textbox(label="📊 Debug Status", lines=8)
    
    # CRITICAL: Test the button click event
    process_btn.click(
        fn=simple_test,
        inputs=[video_input, bg_input, use_matanyone],
        outputs=[output_video, download_file, status_text]
    )
    
    gr.Markdown("### 🔧 Debug Info")
    gr.Markdown(f"- **GPU Available**: {torch.cuda.is_available()}")
    gr.Markdown("- **Purpose**: Test if button click works")
    gr.Markdown("- **Expected**: Status should update when button clicked")

if __name__ == "__main__":
    demo.launch()
