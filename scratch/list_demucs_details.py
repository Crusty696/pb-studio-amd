import sys
sys.path.append('src')
from pb_studio.audio.separator import StemSeparator
import json

sep = StemSeparator()
models = sep.list_models()

print("Demucs Detail-Modelle:")
print(json.dumps(models.get("Demucs", {}), indent=2))
