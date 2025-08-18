# app/tools/huggingface_app.py
# Adapted from huggingface_space_setup/app.py to be importable by the main application.
# This version uses SAM2 + MatAnyone for production-quality background removal.

import gradio as gr
import torch
import numpy as np
import cv2
from PIL import Image
import tempfile
import os
import gc
from moviepy.editor import VideoFileClip
from huggingface_hub import hf_hub_download

# --- 1. Global State and Configuration ---
MODELS = {
    "sam_predictor": None,
    "matanyone_processor": None
}
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# --- 2. Model Management (Lazy Loading & Offloading) ---

def load_models(progress=gr.Progress()):
    """Loads models into memory, downloading from Hugging Face Hub if necessary."""
    progress(0, desc="Initializing models...")
    global MODELS

    if MODELS["sam_predictor"] is not None and MODELS["matanyone_processor"] is not None:
        print("Models already loaded.")
        return

    print("Loading models...")
    import hydra
    from omegaconf import OmegaConf
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from matanyone import InferenceCore
    import logging

    logger = logging.getLogger("HuggingFaceAppLoader")

    def load_sam2_predictor(device="cuda"):
        configs_dir = os.path.join(os.getcwd(), "Configs")
        tried = []

        def try_load(config_name, checkpoint_name):
            try:
                # Download model from Hugging Face Hub if it doesn't exist
                cache_dir = os.path.expanduser("~/.cache/sam2")
                os.makedirs(cache_dir, exist_ok=True)
                checkpoint_path = os.path.join(cache_dir, checkpoint_name)

                if not os.path.exists(checkpoint_path):
                    logger.info(f"Downloading {checkpoint_name} from Hugging Face Hub...")
                    progress(0.1, desc=f"Downloading {checkpoint_name}...")
                    hf_hub_download(
                        repo_id=f"facebook/{config_name.replace('.yaml', '')}",
                        filename=checkpoint_name,
                        local_dir=cache_dir,
                        local_dir_use_symlinks=False
                    )
                    logger.info(f"✅ Download complete: {checkpoint_path}")

                # Load model using hydra config
                hydra.core.global_hydra.GlobalHydra.instance().clear()
                hydra.initialize(config_path=configs_dir)
                cfg = hydra.compose(config_name=config_name)

                logger.info(f"Trying to load {config_name} on {device} with checkpoint {checkpoint_path}")
                progress(0.3, desc=f"Loading {config_name}...")
                sam2_model = build_sam2(cfg.model, checkpoint_path, device=device)
                predictor = SAM2ImagePredictor(sam2_model)
                logger.info(f"✅ Loaded {config_name} successfully on {device}")
                return predictor
            except Exception as e:
                tried.append(f"{config_name}: {e}")
                logger.warning(f"Failed to load {config_name}: {e}")
                return None

        predictor = try_load("sam2_hiera_large.yaml", "sam2_hiera_large.pt")
        if predictor is None:
            logger.warning("Could not load large model, falling back to tiny model.")
            predictor = try_load("sam2_hiera_tiny.yaml", "sam2_hiera_tiny.pt")
            if predictor:
                logger.warning("⚠️ Using Tiny model as fallback (less accurate, but faster and lighter).")
        
        if predictor is None:
            error_message = "SAM2 loading failed for both large and tiny. Reasons: \n" + "\n".join(tried)
            logger.error(f"❌ {error_message}")
            raise gr.Error(error_message)

        return predictor

    # Load SAM2
    MODELS["sam_predictor"] = load_sam2_predictor(device=DEVICE)

    # Load MatAnyone
    progress(0.6, desc="Loading MatAnyone Model...")
    MODELS["matanyone_processor"] = InferenceCore(model_name="PeiqingYang/MatAnyone-v1.0", device=DEVICE)
    print("MatAnyone loaded.")
    progress(1, desc="Models loaded!")

def offload_models():
    """Offloads models from memory to save resources."""
    global MODELS
    print("Offloading models...")
    for key in MODELS:
        MODELS[key] = None
    gc.collect()
    torch.cuda.empty_cache()
    print("Models offloaded and cache cleared.")

# --- 3. Core Video Processing Logic ---

def process_video(video_path, bg_image_path, progress=gr.Progress()):
    """Main function to process the video."""
    try:
        load_models(progress)
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise gr.Error("Error opening video file.")

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        output_path = tempfile.mktemp(suffix='.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        bg_image = Image.open(bg_image_path).convert("RGB").resize((width, height))
        bg_image_np = np.array(bg_image)

        for i in progress.tqdm(range(total_frames), desc="Processing Frames"):
            ret, frame = cap.read()
            if not ret:
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Get SAM mask
            # This part is simplified. A real implementation would need user input for points/boxes.
            # For a fully automatic approach, we'll assume the largest object is the person.
            # Note: This is a placeholder for a more sophisticated object selection.
            sam_input = torch.from_numpy(frame_rgb).to(DEVICE).permute(2, 0, 1)
            # A full bounding box is a simple way to segment the whole image content
            input_box = np.array([0, 0, width, height])
            sam_mask = MODELS["sam_predictor"].predict(sam_input, box=input_box, multimask_output=False)[0]
            sam_mask_np = sam_mask.cpu().numpy().astype(np.uint8) * 255

            # Get MatAnyone alpha matte
            alpha_matte = MODELS["matanyone_processor"].infer(Image.fromarray(frame_rgb), Image.fromarray(sam_mask_np))
            alpha_matte_np = np.array(alpha_matte).astype(float) / 255.0
            if len(alpha_matte_np.shape) == 2:
                alpha_matte_np = np.stack([alpha_matte_np]*3, axis=-1)

            # Composite frame
            composite = frame_rgb * alpha_matte_np + bg_image_np * (1 - alpha_matte_np)
            composite_bgr = cv2.cvtColor(composite.astype(np.uint8), cv2.COLOR_RGB2BGR)
            out.write(composite_bgr)

        cap.release()
        out.release()

        # Add original audio
        progress(0.95, desc="Adding audio...")
        video_clip = VideoFileClip(output_path)
        original_audio = VideoFileClip(video_path).audio
        if original_audio:
            final_clip = video_clip.set_audio(original_audio)
            final_output_path = tempfile.mktemp(suffix='_final.mp4')
            final_clip.write_videofile(final_output_path, codec='libx264', audio_codec='aac')
            os.remove(output_path)
            output_path = final_output_path

        return output_path

    except Exception as e:
        raise gr.Error(f"An error occurred: {e}")
    finally:
        offload_models()

# --- 4. Gradio App Creation ---
def create_huggingface_app():
    """Creates and returns the Gradio app."""
    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("""
        # 🚀 SAM2 + MatAnyone Video Background Changer
        Upload a video and a background image to replace the background with cinema-quality results.
        Powered by Segment Anything 2 and MatAnyone.
        """)

        with gr.Row():
            with gr.Column():
                video_input = gr.Video(label="Your Video")
                bg_input = gr.Image(label="Background Image", type="filepath")
                process_button = gr.Button("Process Video", variant="primary")
            
            with gr.Column():
                video_output = gr.Video(label="Result")

        process_button.click(
            fn=process_video,
            inputs=[video_input, bg_input],
            outputs=video_output
        )
    return demo

# Create the app instance to be imported by FastAPI
huggingface_gradio_app = create_huggingface_app()
