"""
Export Handler
==============

Timeline Import/Export Funktionen.
Unterstützt: JSON (intern), FFmpeg Concat, DaVinci Resolve EDL.

Portiert von NVIDIA-Version, angepasst für AMD DirectML.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime


logger = logging.getLogger(__name__)


def save_timeline(
    timeline: List[Dict[str, Any]],
    output_path: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Speichert eine Timeline als JSON-Datei.
    
    Args:
        timeline: Liste von Timeline-Einträgen
        output_path: Ziel-Pfad für JSON
        metadata: Optionale Metadaten (Projektname, Audio-Pfad, etc.)
        
    Returns:
        True bei Erfolg
    """
    try:
        # Statistiken berechnen
        total_duration = sum(item.get("duration", 0) for item in timeline)
        # BUG-079 FIX: Pruefe video_path und clip_path fuer korrekte Uniqueness-Zaehlung
        unique_clips = len(set(
            item.get("video_path") or item.get("clip_path") or "" 
            for item in timeline
        ))
        
        data = {
            "version": "2.0",
            "created": datetime.now().isoformat(),
            "generator": "PB_Studio_AMD",
            "metadata": metadata or {},
            "stats": {
                "total_clips": len(timeline),
                "total_duration": round(total_duration, 2),
                "unique_videos": unique_clips,
            },
            "timeline": timeline
        }
        
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Timeline gespeichert: {output} ({len(timeline)} Clips)")
        return True
        
    except Exception as e:
        logger.error(f"Timeline-Save fehlgeschlagen: {e}")
        return False


def load_timeline(input_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Lädt eine Timeline aus JSON.
    
    Args:
        input_path: Pfad zur JSON-Datei
        
    Returns:
        Tuple von (timeline_list, metadata_dict)
    """
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        timeline = data.get("timeline", [])
        metadata = data.get("metadata", {})
        
        logger.info(f"Timeline geladen: {input_path} ({len(timeline)} Clips)")
        return timeline, metadata
        
    except Exception as e:
        logger.error(f"Timeline-Load fehlgeschlagen: {e}")
        return [], {}


def export_for_ffmpeg(
    timeline: List[Dict[str, Any]],
    output_path: str
) -> bool:
    """
    Exportiert die Timeline als FFmpeg Concat-Datei.
    
    Format:
        file '/path/to/clip.mp4'
        inpoint 1.5
        outpoint 4.2
    
    Args:
        timeline: Timeline-Einträge
        output_path: Ziel-Pfad für Concat-Datei
        
    Returns:
        True bei Erfolg
    """
    try:
        lines = ["# PB Studio AMD - FFmpeg Concat File", ""]
        
        for item in timeline:
            clip_path = item.get("clip_path", "")
            in_point = item.get("in_point", 0.0)
            out_point = item.get("out_point", 0.0)
            
            if not clip_path:
                continue
            
            # Backslashes für FFmpeg escapen
            clip_path_escaped = clip_path.replace("\\", "/")
            clip_path_escaped = clip_path_escaped.replace("'", "'\\''")
            
            lines.append(f"file '{clip_path_escaped}'")
            lines.append(f"inpoint {in_point:.3f}")
            lines.append(f"outpoint {out_point:.3f}")
            lines.append("")
        
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        logger.info(f"FFmpeg Concat exportiert: {output} ({len(timeline)} Clips)")
        return True
        
    except Exception as e:
        logger.error(f"FFmpeg-Export fehlgeschlagen: {e}")
        return False


def export_for_davinci(
    timeline: List[Dict[str, Any]],
    output_path: str,
    fps: float = 25.0
) -> bool:
    """
    Exportiert die Timeline als CMX3600 EDL für DaVinci Resolve.
    
    Args:
        timeline: Timeline-Einträge
        output_path: Ziel-Pfad für EDL
        fps: Framerate (Standard: 25fps PAL)
        
    Returns:
        True bei Erfolg
    """
    try:
        lines = [
            "TITLE: PB_Studio_AMD_Timeline",
            "FCM: NON-DROP FRAME",
            ""
        ]
        
        for i, item in enumerate(timeline, 1):
            clip_path = item.get("clip_path", "UNKNOWN")
            in_point = item.get("in_point", 0.0)
            out_point = item.get("out_point", 0.0)
            tl_start = item.get("timeline_start", 0.0)
            tl_end = item.get("timeline_end", 0.0)
            
            # SMPTE Timecodes
            src_in = _seconds_to_smpte(in_point, fps)
            src_out = _seconds_to_smpte(out_point, fps)
            rec_in = _seconds_to_smpte(tl_start, fps)
            rec_out = _seconds_to_smpte(tl_end, fps)
            
            # EDL Event
            event_num = f"{i:03d}"
            lines.append(f"{event_num}  AX       V     C        {src_in} {src_out} {rec_in} {rec_out}")
            lines.append(f"* FROM CLIP NAME: {Path(clip_path).name}")
            lines.append("")
        
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        logger.info(f"DaVinci EDL exportiert: {output} ({len(timeline)} Events)")
        return True
        
    except Exception as e:
        logger.error(f"DaVinci-Export fehlgeschlagen: {e}")
        return False


def validate_timeline(timeline: List[Dict[str, Any]]) -> List[str]:
    """
    Prüft eine Timeline auf Fehler.
    
    Returns:
        Liste von Fehlermeldungen (leer = OK)
    """
    errors = []
    
    if not timeline:
        errors.append("Timeline ist leer")
        return errors
    
    for i, item in enumerate(timeline):
        # Pflichtfelder prüfen
        if not item.get("clip_path"):
            errors.append(f"Clip {i+1}: Kein clip_path")
        
        duration = item.get("duration", 0)
        if duration <= 0:
            errors.append(f"Clip {i+1}: Ungültige Duration ({duration})")
        
        in_point = item.get("in_point", 0)
        out_point = item.get("out_point", 0)
        if out_point < in_point:
            errors.append(f"Clip {i+1}: out_point ({out_point}) < in_point ({in_point})")
    
    # Lücken prüfen
    sorted_tl = sorted(timeline, key=lambda x: x.get("timeline_start", 0))
    for i in range(len(sorted_tl) - 1):
        curr_end = sorted_tl[i].get("timeline_end", 0)
        next_start = sorted_tl[i + 1].get("timeline_start", 0)
        gap = next_start - curr_end
        if gap > 0.5:
            errors.append(f"Lücke: {gap:.2f}s zwischen Clip {i+1} und {i+2}")
    
    # Überlappungen prüfen
    for i in range(len(sorted_tl) - 1):
        curr_end = sorted_tl[i].get("timeline_end", 0)
        next_start = sorted_tl[i + 1].get("timeline_start", 0)
        if next_start < curr_end - 0.01:
            overlap = curr_end - next_start
            errors.append(f"Überlappung: {overlap:.2f}s bei Clip {i+1}/{i+2}")
    
    return errors


def _seconds_to_smpte(seconds: float, fps: float = 25.0) -> str:
    """Konvertiert Sekunden in SMPTE Timecode (HH:MM:SS:FF)."""
    total_frames = int(seconds * fps)
    ff = total_frames % int(fps)
    total_seconds = total_frames // int(fps)
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"
