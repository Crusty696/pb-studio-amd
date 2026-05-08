import zlib
import base64
import json
import numpy as np

def compress_array(arr: list[float]) -> str:
    \"\"\"Komprimiert ein numerisches Array in einen Base64-String.\"\"\"
    if not arr:
        return \"\"
    data = np.array(arr, dtype=np.float32).tobytes()
    compressed = zlib.compress(data)
    return base64.b64encode(compressed).decode('utf-8')

def decompress_array(b64_str: str) -> list[float]:
    \"\"\"Dekomprimiert einen numerischen Base64-String zurück in eine Liste.\"\"\"
    if not b64_str:
        return []
    compressed = base64.b64decode(b64_str)
    decompressed = zlib.decompress(compressed)
    arr = np.frombuffer(decompressed, dtype=np.float32)
    return arr.tolist()
