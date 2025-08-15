# modules/rvm_processor.py

import os
import cv2
import numpy as np
import torch
import onnxruntime as ort
from PIL import Image
from moviepy.editor import VideoFileClip, AudioFileClip
from pathlib import Path

def resize_background(bg, target_size):
    return cv2.resize(bg, (target_size[1], target_size[0]))

def load_image(avatar_url):
    image = Image.open(avatar_url).convert("RGB")
    return np.array(image)

def apply_rvm_matting(video_path, avatar_url, output_path, model_path="rvm_mobilenetv3_fp32.onnx"):
    # Load ONNX model
    ort_session = ort.InferenceSession(model_path)

    # Prepare background image
    background = load_image(avatar_url)

    # Read video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    tmp_video_path = "temp/tmp_output_video.mp4"
    out = cv2.VideoWriter(tmp_video_path, fourcc, fps, (width, height))

    background_resized = resize_background(background, (height, width))

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Fake alpha mask: here you should insert the RVM model inference
        # For now, simulate a simple rectangular mask for demo:
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.rectangle(mask, (width//4, height//4), (3*width//4, 3*height//4), 255, -1)

        mask_3ch = cv2.merge([mask, mask, mask])
        foreground = cv2.bitwise_and(frame, mask_3ch)
        inverse_mask = cv2.bitwise_not(mask)
        bg_part = cv2.bitwise_and(background_resized, background_resized, mask=inverse_mask)
        combined = cv2.add(foreground, bg_part)

        out.write(combined)

    cap.release()
    out.release()

    # Add original audio
    original = VideoFileClip(video_path)
    processed = VideoFileClip(tmp_video_path)
    final = processed.set_audio(original.audio)
    final.write_videofile(output_path, codec="libx264", audio_codec="aac")
    os.remove(tmp_video_path)

def replace_background(video_path, avatar_url, output_path):
    print(f"Processing {video_path} with background {avatar_url}")
    apply_rvm_matting(video_path, avatar_url, output_path)
    print(f"Output saved to {output_path}")
