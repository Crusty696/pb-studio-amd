#!/usr/bin/env python3
"""
PB Studio AMD Edition - Model Download Script

Downloads ONNX models from HuggingFace for DirectML acceleration:
- Moondream2 Vision Encoder (FP16) - GPU-beschleunigte Bilderkennung
- RAFT Optical Flow (Small) - Motion-Analyse
- Moondream2 Tokenizer - Text-Verarbeitung

Usage:
    python download_models.py                  # Status pruefen
    python download_models.py --moondream      # Moondream herunterladen
    python download_models.py --all            # Alles herunterladen
    python download_models.py --quality fp16   # Qualitaet waehlen (fp16/int8/q4)

Requirements:
    pip install huggingface_hub
"""

import os
import sys
import shutil
import argparse
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"

# Moondream2 ONNX Dateien von Xenova/moondream2 (Community ONNX Export)
# Quelle: https://huggingface.co/Xenova/moondream2
MOONDREAM_CONFIGS = {
    "fp16": {
        "description": "FP16 (Empfohlen - beste Qualitaet auf DirectML)",
        "files": {
            "onnx/vision_encoder_fp16.onnx": "moondream_encoder.onnx",
            "onnx/embed_tokens_fp16.onnx": "moondream_embed_tokens.onnx",
        },
        "total_size_mb": 1089,
    },
    "int8": {
        "description": "INT8 (Kleiner, etwas weniger Qualitaet)",
        "files": {
            "onnx/vision_encoder_int8.onnx": "moondream_encoder.onnx",
            "onnx/embed_tokens_int8.onnx": "moondream_embed_tokens.onnx",
        },
        "total_size_mb": 549,
    },
    "q4": {
        "description": "Q4 (Kleinste Variante, niedrigste Qualitaet)",
        "files": {
            "onnx/vision_encoder_q4.onnx": "moondream_encoder.onnx",
            "onnx/embed_tokens_q4.onnx": "moondream_embed_tokens.onnx",
        },
        "total_size_mb": 699,
    },
}

MOONDREAM_REPO = "Xenova/moondream2"
MOONDREAM_TOKENIZER_REPO = "vikhyatk/moondream2"


def ensure_models_dir():
    """Models-Verzeichnis erstellen falls noetig."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def download_from_huggingface(repo_id: str, filename: str, local_name: str) -> bool:
    """Datei von HuggingFace Hub herunterladen."""
    try:
        from huggingface_hub import hf_hub_download

        target_path = MODELS_DIR / local_name

        if target_path.exists():
            size_mb = target_path.stat().st_size / (1024 * 1024)
            logger.info(f"  Bereits vorhanden: {local_name} ({size_mb:.0f} MB)")
            return True

        logger.info(f"  Lade herunter: {filename} -> {local_name}")

        downloaded = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(MODELS_DIR / "_hf_cache"),
            local_dir_use_symlinks=False
        )

        # In Zielverzeichnis verschieben mit richtigem Namen
        downloaded_path = Path(downloaded)
        if downloaded_path.exists():
            shutil.copy2(str(downloaded_path), str(target_path))
            size_mb = target_path.stat().st_size / (1024 * 1024)
            logger.info(f"  [OK] {local_name} ({size_mb:.0f} MB)")
            return True

        return False

    except ImportError:
        logger.error("huggingface_hub nicht installiert. Run: pip install huggingface_hub")
        return False
    except Exception as e:
        logger.error(f"  [FEHLER] Download fehlgeschlagen: {e}")
        return False


def download_moondream(quality: str = "fp16") -> bool:
    """Moondream2 Vision Encoder herunterladen."""
    if quality not in MOONDREAM_CONFIGS:
        logger.error(f"Unbekannte Qualitaet: {quality}. Verfuegbar: {', '.join(MOONDREAM_CONFIGS)}")
        return False

    config = MOONDREAM_CONFIGS[quality]

    logger.info("=" * 60)
    logger.info(f"Moondream2 Vision Encoder - {config['description']}")
    logger.info(f"Geschaetzte Groesse: ~{config['total_size_mb']} MB")
    logger.info("=" * 60)

    success = True

    # ONNX Modelle herunterladen
    for hf_path, local_name in config["files"].items():
        if not download_from_huggingface(MOONDREAM_REPO, hf_path, local_name):
            success = False

    # Tokenizer herunterladen (von Original-Repo)
    tokenizer_dir = MODELS_DIR / "moondream_tokenizer"
    if tokenizer_dir.exists() and any(tokenizer_dir.iterdir()):
        logger.info(f"  Bereits vorhanden: moondream_tokenizer/")
    else:
        logger.info("  Lade Tokenizer herunter...")
        try:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                MOONDREAM_TOKENIZER_REPO,
                trust_remote_code=True
            )
            tokenizer_dir.mkdir(parents=True, exist_ok=True)
            tokenizer.save_pretrained(str(tokenizer_dir))
            logger.info("  [OK] Tokenizer gespeichert")
        except ImportError:
            logger.warning("  transformers nicht installiert - Tokenizer wird beim ersten Start geladen")
        except Exception as e:
            logger.warning(f"  Tokenizer-Download fehlgeschlagen: {e}")
            logger.info("  Tokenizer wird beim ersten App-Start automatisch geladen")

    if success:
        logger.info("\n[OK] Moondream2 bereit fuer DirectML!")
        logger.info("     Vision Encoder laeuft auf AMD GPU")
        logger.info("     Text Decoder nutzt PyTorch CPU Fallback")

    return success


def download_raft() -> bool:
    """RAFT Optical Flow Model pruefen/herunterladen."""
    logger.info("=" * 60)
    logger.info("RAFT Optical Flow Model")
    logger.info("=" * 60)

    # Pruefe beide moeglichen Dateinamen
    raft_small = MODELS_DIR / "raft_small.onnx"
    raft_standard = MODELS_DIR / "raft.onnx"

    if raft_small.exists():
        size_mb = raft_small.stat().st_size / (1024 * 1024)
        logger.info(f"  [OK] raft_small.onnx vorhanden ({size_mb:.1f} MB)")
        return True

    if raft_standard.exists():
        size_mb = raft_standard.stat().st_size / (1024 * 1024)
        logger.info(f"  [OK] raft.onnx vorhanden ({size_mb:.1f} MB)")
        return True

    logger.warning("  [FEHLT] RAFT ONNX Modell nicht gefunden")
    logger.info("  RAFT wird automatisch durch OpenCV Farneback ersetzt (CPU Fallback)")
    return False


def check_existing_models():
    """Status aller Modelle pruefen."""
    logger.info("\nModell-Status:")
    logger.info("-" * 40)

    existing = []
    missing = []

    # Moondream Vision Encoder
    moondream_files = [
        MODELS_DIR / "moondream_encoder.onnx",
        MODELS_DIR / "moondream_vision.onnx",
        MODELS_DIR / "moondream.onnx",
    ]
    if any(f.exists() for f in moondream_files):
        found = next(f for f in moondream_files if f.exists())
        size_mb = found.stat().st_size / (1024 * 1024)
        existing.append("moondream")
        logger.info(f"  [OK] Moondream Vision Encoder: {found.name} ({size_mb:.0f} MB)")
    else:
        missing.append("moondream")
        logger.warning("  [FEHLT] Moondream Vision Encoder ONNX")

    # Moondream PyTorch Fallback
    pytorch_model = MODELS_DIR / "moondream_pytorch.pt"
    if pytorch_model.exists():
        size_gb = pytorch_model.stat().st_size / (1024 * 1024 * 1024)
        logger.info(f"  [OK] Moondream PyTorch Fallback: {size_gb:.1f} GB")
    else:
        logger.info("  [--] Moondream PyTorch Fallback: nicht vorhanden")

    # Moondream Tokenizer
    tokenizer_dir = MODELS_DIR / "moondream_tokenizer"
    if tokenizer_dir.exists() and any(tokenizer_dir.iterdir()):
        logger.info("  [OK] Moondream Tokenizer: vorhanden")
    else:
        logger.info("  [--] Moondream Tokenizer: wird bei Bedarf geladen")

    # RAFT
    raft_files = [
        MODELS_DIR / "raft_small.onnx",
        MODELS_DIR / "raft.onnx",
    ]
    if any(f.exists() for f in raft_files):
        found = next(f for f in raft_files if f.exists())
        size_mb = found.stat().st_size / (1024 * 1024)
        existing.append("raft")
        logger.info(f"  [OK] RAFT Motion: {found.name} ({size_mb:.1f} MB)")
    else:
        missing.append("raft")
        logger.warning("  [FEHLT] RAFT Motion ONNX (CPU Fallback aktiv)")

    # SigLIP Vision
    siglip = MODELS_DIR / "siglip_vision.onnx"
    if siglip.exists():
        size_gb = siglip.stat().st_size / (1024 * 1024 * 1024)
        logger.info(f"  [OK] SigLIP Vision: {size_gb:.1f} GB")

    # UVR MDX-Net
    uvr_files = list(MODELS_DIR.glob("UVR*.onnx"))
    if uvr_files:
        existing.append("uvr-mdx")
        size_mb = uvr_files[0].stat().st_size / (1024 * 1024)
        logger.info(f"  [OK] UVR MDX-Net: {uvr_files[0].name} ({size_mb:.0f} MB)")
    else:
        missing.append("uvr-mdx")
        logger.warning("  [FEHLT] UVR MDX-Net ONNX")

    logger.info("-" * 40)
    return existing, missing


def cleanup_hf_cache():
    """HuggingFace Download-Cache aufraeumen."""
    cache_dir = MODELS_DIR / "_hf_cache"
    if cache_dir.exists():
        shutil.rmtree(str(cache_dir), ignore_errors=True)
        logger.info("HuggingFace Cache aufgeraeumt")


def main():
    parser = argparse.ArgumentParser(
        description="ONNX Modelle fuer PB Studio AMD Edition herunterladen"
    )
    parser.add_argument("--all", action="store_true", help="Alle Modelle herunterladen")
    parser.add_argument("--moondream", action="store_true", help="Moondream2 herunterladen")
    parser.add_argument("--raft", action="store_true", help="RAFT pruefen")
    parser.add_argument("--check", action="store_true", help="Nur Status anzeigen")
    parser.add_argument(
        "--quality", choices=["fp16", "int8", "q4"], default="fp16",
        help="Moondream Qualitaet (default: fp16)"
    )
    parser.add_argument("--cleanup", action="store_true", help="Download-Cache aufraeumen")

    args = parser.parse_args()

    if not any([args.all, args.moondream, args.raft, args.check, args.cleanup]):
        args.check = True

    ensure_models_dir()

    if args.cleanup:
        cleanup_hf_cache()
        return 0

    if args.check:
        existing, missing = check_existing_models()
        if missing:
            logger.info(f"\nFehlende Modelle: {', '.join(missing)}")
            logger.info("Starte Download mit: python download_models.py --all")
        else:
            logger.info("\nAlle Modelle vorhanden!")
        return 0 if not missing else 1

    # Downloads ausfuehren
    results = []

    if args.all or args.moondream:
        results.append(("Moondream", download_moondream(args.quality)))

    if args.all or args.raft:
        results.append(("RAFT", download_raft()))

    # Cache aufraeumen
    cleanup_hf_cache()

    # Zusammenfassung
    logger.info("\n" + "=" * 60)
    logger.info("Zusammenfassung")
    logger.info("=" * 60)

    check_existing_models()

    failed = [name for name, ok in results if not ok]
    if failed:
        logger.warning(f"\nFehlgeschlagen: {', '.join(failed)}")
        return 1

    logger.info("\nAlle Downloads abgeschlossen!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
