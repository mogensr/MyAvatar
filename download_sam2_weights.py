# Download SAM2 weights (large og tiny) fra Hugging Face med hf_hub_download
from huggingface_hub import hf_hub_download
import os

# Sørg for at brugermappen og cache eksisterer
target_dir = os.path.expanduser("~/.cache/sam2")
os.makedirs(target_dir, exist_ok=True)

# Korrekte repo og filnavne
# Note: The user provided 'facebook/sam2-hiera-large' but the tiny model is in a different repo.
# Using the correct repo for each model.

models_to_download = {
    "facebook/sam2-hiera-large": "sam2_hiera_large.pt",
    "facebook/sam2-hiera-tiny": "sam2_hiera_tiny.pt"
}

for repo_id, name in models_to_download.items():
    print(f"Downloader: {name} fra {repo_id}")
    try:
        file_path = hf_hub_download(
            repo_id=repo_id,
            filename=name,
            local_dir=target_dir,
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        print(f"Downloadet til: {file_path}")
    except Exception as e:
        print(f"Fejl under download af {name}: {e}")

print("\nTjek at filerne er ~900 MB (large) og ~300 MB (tiny) i " + target_dir)
print("Kør din app igen, når download er færdig.")
