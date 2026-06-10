import sys
sys.path.append('src')
from pb_studio.audio.separator import StemSeparator

sep = StemSeparator()
models = sep.list_models()

demucs_models = []
for name, info in models.items():
    if "demucs" in name.lower() or "demucs" in info.get("filename", "").lower():
        demucs_models.append((name, info.get("filename")))

print("Demucs Modelle:")
for name, filename in demucs_models:
    print(f"- Name: {name} | Filename: {filename}")
