import gradio as gr

def simple_video_test(video_file):
    """Simple video test to isolate the issue"""
    print(f"🎬 Video function called!")
    print(f"Video type: {type(video_file)}")
    print(f"Video: {video_file}")
    
    if video_file is None:
        return "❌ No video received"
    
    try:
        # Test file access
        video_path = video_file.name if hasattr(video_file, 'name') else str(video_file)
        print(f"Video path: {video_path}")
        
        # Test file existence
        import os
        if os.path.exists(video_path):
            file_size = os.path.getsize(video_path)
            return f"✅ Video received successfully!\nPath: {video_path}\nSize: {file_size} bytes"
        else:
            return f"❌ Video file not found at: {video_path}"
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error accessing video: {str(e)}"

# Simple video interface
demo = gr.Interface(
    fn=simple_video_test,
    inputs=gr.Video(label="Upload Video"),
    outputs=gr.Textbox(label="Result"),
    title="🎬 Simple Video Test",
    description="Testing video file handling in HF Spaces"
)

if __name__ == "__main__":
    print("🚀 Starting video test...")
    demo.launch()
