# modules/videotix.py

import streamlit as st
from pathlib import Path
from modules.rvm_processor import replace_background

def run_videotix_gui():
    st.header("🎬 Videotix – Video Baggrundsudskiftning")

    video_file = st.file_uploader("🎥 Upload video (.mp4/.mov)", type=["mp4", "mov"])
    image_file = st.file_uploader("🖼️ Upload baggrundsbillede (.png/.jpg)", type=["png", "jpg", "jpeg"])

    if video_file and image_file:
        temp_dir = Path("uploads")
        output_dir = Path("processed")
        temp_dir.mkdir(exist_ok=True)
        output_dir.mkdir(exist_ok=True)

        # Gem video
        video_path = temp_dir / video_file.name
        with open(video_path, "wb") as f:
            f.write(video_file.read())

        # Gem billede
        image_path = temp_dir / image_file.name
        image_bytes = image_file.read()

        if len(image_bytes) < 100:
            st.error("❌ Det uploadede billede er tomt eller defekt.")
            return
        else:
            with open(image_path, "wb") as f:
                f.write(image_bytes)

        try:
            st.image(image_bytes, caption="Valgt baggrund")
        except Exception as e:
            st.warning(f"⚠️ Kunne ikke vise billedet: {e}")

        st.video(str(video_path))

        if st.button("🚀 Erstat baggrund"):
            output_path = output_dir / f"processed_{video_file.name}"

            with st.spinner("Behandler video, vent venligst..."):
                replace_background(str(video_path), str(image_path), str(output_path))

            st.success("✅ Video færdigbehandlet!")
            st.video(str(output_path))

            with open(output_path, "rb") as f:
                st.download_button("📥 Download video", f, file_name=output_path.name)

            st.markdown(f"📂 Gemt til: `{output_path}`")
