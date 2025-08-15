import gradio as gr
import os
import cv2
import numpy as np
import requests
from PIL import Image
from io import BytesIO
import tempfile
import shutil
import logging

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if running in Colab to set the correct path
GDRIVE_OUTPUT_DIR = '/content/drive/MyDrive/BackgroundFX_Output' if os.path.exists('/content/drive') else 'BackgroundFX_Output'
os.makedirs(GDRIVE_OUTPUT_DIR, exist_ok=True)

# --- AI Model Availability & Loading ---
SAM2_AVAILABLE = False
SAM2_PREDICTOR = None

try:
    # This import will be attempted in the Colab environment after installation
    from sam2.build_sam import build_sam2_video_predictor
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    # Load the large model as requested
    SAM2_PREDICTOR = SAM2ImagePredictor.from_pretrained("facebook/sam2-hiera-large")
    SAM2_AVAILABLE = True
    logger.info("✅ SAM2 (Large Model) loaded successfully")
except ImportError:
    logger.warning("⚠️ SAM2 not available. Please ensure it's installed.")
except Exception as e:
    logger.error(f"🚨 Error loading SAM2 model: {e}")

# --- Core Processing Logic (Adapted from hf_space_app.py) ---

def get_background_options():
    return {
        "Brick Wall": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=1280&h=720&fit=crop",
        "Simple Office": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1280&h=720&fit=crop",
        "Executive Office": "https://images.unsplash.com/photo-1586953208448-b95a79798f07?w=1280&h=720&fit=crop",
        "Modern Conference Room": "https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=1280&h=720&fit=crop",
    }

def segment_person_sam2(frame):
    if not SAM2_AVAILABLE or SAM2_PREDICTOR is None:
        logger.warning("SAM2 not available, falling back to color segmentation.")
        return segment_person_fallback(frame)
    try:
        SAM2_PREDICTOR.set_image(frame)
        h, w = frame.shape[:2]
        center_point = np.array([[w // 2, h // 2]])
        center_label = np.array([1])
        masks, _, _ = SAM2_PREDICTOR.predict(point_coords=center_point, point_labels=center_label, multimask_output=False)
        return masks[0] if len(masks) > 0 else None
    except Exception as e:
        logger.error(f"SAM2 segmentation failed: {e}")
        return segment_person_fallback(frame)

def segment_person_fallback(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
    lower_skin = np.array([0, 20, 70])
    upper_skin = np.array([20, 255, 255])
    skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
    kernel = np.ones((5, 5), np.uint8)
    skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return None
    largest_contour = max(contours, key=cv2.contourArea)
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [largest_contour], 255)
    return cv2.dilate(mask, np.ones((20, 20), np.uint8), iterations=2).astype(bool)

def insert_green_screen(frame, person_mask):
    green_background = np.zeros_like(frame)
    green_background[:, :] = [0, 255, 0]
    return np.where(person_mask[..., None], frame, green_background)

def chroma_key_replacement(green_screen_frame, new_background):
    h, w, _ = green_screen_frame.shape
    background_resized = cv2.resize(new_background, (w, h))
    hsv = cv2.cvtColor(green_screen_frame, cv2.COLOR_RGB2HSV)
    lower_green = np.array([40, 50, 50])
    upper_green = np.array([80, 255, 255])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    mask_normalized = green_mask.astype(float) / 255
    result = green_screen_frame.copy()
    for c in range(3):
        result[:, :, c] = result[:, :, c] * (1 - mask_normalized) + background_resized[:, :, c] * mask_normalized
    return result.astype(np.uint8)

# --- Main Processing Function for Gradio ---

def process_video(video_path, background_choice, custom_bg_image, solid_color, progress=gr.Progress(track_tqdm=True)):
    if video_path is None:
        raise gr.Error("Please upload a video first.")

    # Load or create background
    if background_choice == "Custom":
        if custom_bg_image is None:
            raise gr.Error("Please upload a custom background image.")
        background_image = np.array(custom_bg_image)
    elif background_choice == "Solid Color":
        if solid_color is None:
            raise gr.Error("Please choose a color.")
        # Create a solid color image
        color_rgb = tuple(int(solid_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        # Assuming a default resolution, which we'll resize later anyway
        background_image = np.full((720, 1280, 3), color_rgb, dtype=np.uint8)
    else:
        background_url = get_background_options()[background_choice]
        background_image = np.array(Image.open(BytesIO(requests.get(background_url).content)))

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    temp_output_path = tempfile.mktemp(suffix='.mp4')
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_output_path, fourcc, fps, (width, height))

    for i in progress.tqdm(range(total_frames), desc="Processing Frames"):
        ret, frame = cap.read()
        if not ret: break
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        person_mask = segment_person_sam2(frame_rgb)
        if person_mask is not None:
            green_screen_frame = insert_green_screen(frame_rgb, person_mask)
            final_frame = chroma_key_replacement(green_screen_frame, background_image)
        else:
            final_frame = frame_rgb # Fallback if segmentation fails
        out.write(cv2.cvtColor(final_frame, cv2.COLOR_RGB2BGR))

    cap.release()
    out.release()

    # Save to Google Drive and return path
    final_filename = f"processed_{os.path.basename(video_path)}"
    drive_path = os.path.join(GDRIVE_OUTPUT_DIR, final_filename)
    shutil.copyfile(temp_output_path, drive_path)
    
    status_message = f"✅ Processing complete! Video saved to: {drive_path}"
    logger.info(status_message)
    
    return temp_output_path, status_message

# --- Gradio UI Definition ---

with gr.Blocks(theme=gr.themes.Soft(), title="BackgroundFX") as demo:
    gr.Markdown("## 🎬 BackgroundFX - AI Video Background Replacement")
    gr.Markdown("Upload a video, choose a new background, and let the AI do the rest. Results are saved to your Google Drive.")

    with gr.Row():
        with gr.Column(scale=1):
            video_input = gr.Video(label="Upload Your Video")
            background_options = list(get_background_options().keys())
            background_choice = gr.Dropdown(background_options + ["Custom", "Solid Color"], label="Choose a Background", value=background_options[0])
            custom_bg_image = gr.Image(type="pil", label="Upload Custom Background", visible=False)
            solid_color_picker = gr.ColorPicker(label="Choose Solid Color", visible=False)
            process_button = gr.Button("🎬 Process Video", variant="primary")

        with gr.Column(scale=1):
            video_output = gr.Video(label="Processed Video")
            status_output = gr.Textbox(label="Status", interactive=False)

    def toggle_background_inputs(choice):
        is_custom = (choice == "Custom")
        is_color = (choice == "Solid Color")
        return gr.update(visible=is_custom), gr.update(visible=is_color)

    background_choice.change(
        fn=toggle_background_inputs, 
        inputs=background_choice, 
        outputs=[custom_bg_image, solid_color_picker]
    )
    
    process_button.click(
        fn=process_video,
        inputs=[video_input, background_choice, custom_bg_image, solid_color_picker],
        outputs=[video_output, status_output],
        # Add this to prevent the function from running on page load
        trigger_mode="once"
    )

if __name__ == "__main__":
    demo.launch(debug=True)
