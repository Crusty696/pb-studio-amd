import sys
import os

# Projektroot zu sys.path hinzufuegen (audio -> pb_studio -> src -> root)
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _project_root)

import logging
import argparse
from src.pb_studio.audio.separator import StemSeparator

# Setup basic logging to stderr so stdout is clean for progress
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("StemRunner")

class ProgressCapturer(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        # Pass through progress from library to stdout for parent process
        if "%" in msg and "/" in msg:
            print(f"PROGRESS:{msg}", flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file_path", help="Path to audio file")
    args = parser.parse_args()

    # Intercept library logs
    lib_logger = logging.getLogger("audio_separator.separator.separator")
    lib_logger.addHandler(ProgressCapturer())
    lib_logger.setLevel(logging.INFO)

    try:
        print("STATUS:Initializing...", flush=True)
        separator = StemSeparator()
        
        print("STATUS:Separating...", flush=True)
        res = separator.separate(args.file_path)
        
        if "error" in res:
            print(f"ERROR:{res['error']}", flush=True)
            sys.exit(1)
        
        stems = res.get("stems", [])
        for s in stems:
            print(f"STEM:{s}", flush=True)
            
        print("DONE", flush=True)
        
    except Exception as e:
        print(f"ERROR:{str(e)}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
