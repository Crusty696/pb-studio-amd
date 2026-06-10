import sys
sys.path.append('src')
from pb_studio.audio.separator import StemSeparator

sep = StemSeparator()
models = sep.list_models()

print("Verfuegbare Modell-Keys (erste 100):")
keys = list(models.keys())
for k in keys[:100]:
    print(k)
