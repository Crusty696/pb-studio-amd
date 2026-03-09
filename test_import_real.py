
import sys
import logging
from pathlib import Path

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestImport")

# Pfad zur echten Logik
sys.path.append(str(Path.cwd()))
try:
    from src.pb_studio.services.media_service import MediaService
except ImportError:
    # Fallback falls wir nicht im root sind
    sys.path.append(str(Path(r"C:\Users\david\Dokumente\Pb_studio_AMD_version")))
    from src.pb_studio.services.media_service import MediaService

def test_folder_import():
    target_folder = r"C:\Users\david\Videos\Music-Video_Clips\AV"
    logger.info(f"TEST START: Scanning folder '{target_folder}'...")

    path = Path(target_folder)
    if not path.exists():
        logger.error("Target folder does not exist!")
        return

    # Gleiche Extensions wie im GUI-Code
    extensions = {'.mp3', '.wav', '.flac', '.mp4', '.mov', '.avi', '.mkv', '.m4a', '.ogg'}
    files_found = []

    # Rekursiv suchen
    try:
        for p in path.rglob("*"):
            if p.is_file() and p.suffix.lower() in extensions:
                files_found.append(str(p))
                # logger.info(f"Found: {p.name}") # Verbose aus
    except Exception as e:
        logger.error(f"Error during scan: {e}")
        return

    logger.info(f"Total media files found: {len(files_found)}")

    if not files_found:
        logger.warning("No files found! Check path and extensions.")
        return

    # Versuche Import via Service
    service = MediaService()
    project_id = 1 # Default Project
    
    logger.info("Attempting import via MediaService...")
    try:
        results = service.import_files(project_id, files_found)
        # logger.info(f"Import results: {results}") # Zu viel Output bei vielen Files
        
        success_count = results.get("added", 0) + len(results.get("skipped", [])) # Skipped zählt auch als 'da'
        logger.info(f"Import Summary: Added={results.get('added')}, Skipped={len(results.get('skipped', []))}, Errors={len(results.get('errors', []))}")

        # Verify in DB
        db_files = service.get_project_files(project_id)
        # Wir prüfen nur stichprobenartig oder die Anzahl
        
        # Mapping von DB Pfaden zur Prüfung
        db_paths = {f['file_path'] for f in db_files}
        
        missing_in_db = [f for f in files_found if f not in db_paths]
        
        if not missing_in_db:
             logger.info("TEST PASSED: All found files are present in DB.")
        else:
             logger.error(f"TEST FAILED: {len(missing_in_db)} files are missing in DB after import.")
             # logger.error(f"Missing sample: {missing_in_db[:3]}")

    except Exception as e:
        logger.error(f"Import failed with exception: {e}", exc_info=True)

if __name__ == "__main__":
    test_folder_import()
