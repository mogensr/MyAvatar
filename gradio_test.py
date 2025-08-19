import gradio as gr

def show_video_preview(video_file):
    print("VIDEO FILE:", video_file)
    return video_file

with gr.Blocks() as demo:
    video_input = gr.Video(label="Upload video")
    video_preview = gr.Video(label="Preview")

    video_input.upload(
        fn=show_video_preview,
        inputs=video_input,
        outputs=video_preview
    )

demo.launch()
