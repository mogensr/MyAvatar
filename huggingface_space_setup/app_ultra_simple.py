import gradio as gr

def test_click():
    """Ultra simple test - no parameters"""
    print("🚀 BUTTON CLICKED!")
    return "✅ Button works!"

with gr.Blocks() as demo:
    gr.Markdown("# Ultra Simple Button Test")
    
    test_btn = gr.Button("Click Me!")
    output = gr.Textbox(label="Result")
    
    test_btn.click(fn=test_click, outputs=output)

demo.launch()
