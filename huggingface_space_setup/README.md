---
title: SAM2 + MatAnyone Video Background Changer
emoji: 🚀
colorFrom: "indigo"
colorTo: "green"
sdk: gradio
sdk_version: "4.36.1"
app_file: app.py
hardware: l4
pinned: false
license: mit
---

# 🚀 SAM2 + MatAnyone Video Background Changer

This Hugging Face Space provides a powerful video background replacement tool using state-of-the-art AI models:

- **Segmentation**: `Segment Anything 2 (SAM2)` for highly accurate foreground detection.
- **Matting**: `MatAnyone` for professional, cinema-quality video matting.

## Key Features

- **Lazy Loading**: Models are loaded into GPU memory only when needed, keeping the Space resource-efficient.
- **GPU Optimization**: The Space is configured to use an L4 GPU for fast processing.
- **Gradio Interface**: A simple and intuitive user interface for uploading videos and background images.
- **Memory Management**: After each run, models are offloaded and the GPU cache is cleared to minimize costs.
