import sys
sys.path.append('src')
from pb_studio.audio.separator import StemSeparator
import json

sep = StemSeparator()
models = sep.list_models()
print("Unterstuetzte Modelle in audio-separator:")
print(json.dumps(models, indent=2))
