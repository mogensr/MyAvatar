"# MyAvatar Video Background Replacement Service

This project provides a video background replacement service using state-of-the-art machine learning models, deployed as a Gradio application on Hugging Face Spaces.

## Features

- **High-Quality Matting**: Utilizes the MatAnyone model for professional-grade video matting.
- **Advanced Segmentation**: Employs the SAM2 model for precise object segmentation.
- **Simple Interface**: An easy-to-use Gradio interface for uploading a video and a background image.
- **Containerized Deployment**: Packaged with Docker for easy and consistent deployment on Hugging Face Spaces.

## How to Run Locally

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the Application**:
    ```bash
    python app.py
    ```
    The application will be available at `http://127.0.0.1:7860`.

## Hugging Face Spaces Deployment

This application is designed to be deployed on a Hugging Face Space.

### `Dockerfile`

The `Dockerfile` in the root directory defines the container environment for the application. It performs the following steps:
1.  Uses the `python:3.11-slim` base image.
2.  Sets the working directory to `/code`.
3.  Copies and installs the Python dependencies from `requirements.txt`.
4.  Copies the application code into the container.
5.  Specifies the command `python app.py` to run the Gradio application.

When you create a new Space on Hugging Face and link it to this repository, it will use this `Dockerfile` to build and run the application automatically.
