"""Fail-closed policy for persisted media paths.

Project files may reference media imported from outside the project directory.
Such references are trusted only when they resolve to a local file present in
the active project's registered media catalogue.
"""

from __future__ import annotations

import ctypes
import json
import os
import stat
from pathlib import Path
from typing import Any, Iterable, Mapping


class MediaPathPolicyError(ValueError):
    """Raised before an untrusted media reference reaches a filesystem sink."""


def _reject_unsafe_reference(raw_path: str, *, label: str) -> str:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise MediaPathPolicyError(f"{label} fehlt")
    if "\x00" in raw_path:
        raise MediaPathPolicyError(f"{label} enthaelt ein NUL-Zeichen")

    candidate = raw_path.strip()
    normalized = candidate.replace("/", "\\")
    lowered = normalized.lower()
    if (
        normalized.startswith("\\\\")
        or lowered.startswith("\\\\?\\")
        or lowered.startswith("\\\\.\\")
        or "://" in candidate
    ):
        raise MediaPathPolicyError(
            f"{label} muss ein lokaler Laufwerkspfad sein"
        )

    path = Path(candidate)
    if not path.is_absolute() or not path.drive:
        raise MediaPathPolicyError(f"{label} muss absolut sein")

    # The drive separator is the only colon allowed in a normal Windows path.
    if ":" in normalized[len(path.drive):]:
        raise MediaPathPolicyError(f"{label} enthaelt einen unzulaessigen Stream")
    return candidate


def canonical_local_media_file(raw_path: str, *, label: str = "Medienpfad") -> Path:
    """Return a canonical existing local file without touching network paths."""
    path = canonical_local_media_reference(raw_path, label=label)
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise MediaPathPolicyError(f"{label} ist nicht erreichbar") from exc

    _reject_unsafe_reference(str(resolved), label=label)
    if not resolved.is_file():
        raise MediaPathPolicyError(f"{label} ist keine Datei")
    return resolved


def canonical_local_media_reference(
    raw_path: str,
    *,
    label: str = "Medienpfad",
) -> Path:
    """Validate a catalogue reference without requiring the media to be online."""
    candidate = _reject_unsafe_reference(raw_path, label=label)
    path = Path(candidate)
    if os.name == "nt":
        # DRIVE_REMOTE (4) also covers mapped SMB drive letters.
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(path.anchor)
        if drive_type == 4:
            raise MediaPathPolicyError(
                f"{label} darf kein zugeordnetes Netzlaufwerk verwenden"
            )

    current = Path(path.anchor)
    for component in path.parts[1:]:
        try:
            current /= component
            attributes = getattr(os.lstat(current), "st_file_attributes", 0)
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            if attributes & reparse_flag:
                raise MediaPathPolicyError(
                    f"{label} darf keinen Symlink oder Junction verwenden"
                )
        except FileNotFoundError:
            break
        except MediaPathPolicyError:
            raise
        except OSError as exc:
            raise MediaPathPolicyError(f"{label} ist nicht erreichbar") from exc
    return Path(os.path.abspath(path))


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path))


def validate_registered_media_path(
    raw_path: str,
    registered_paths: Iterable[str],
    *,
    label: str = "Medienpfad",
) -> str:
    """Validate a local file and bind it to the active media catalogue."""
    candidate = canonical_local_media_file(raw_path, label=label)
    approved: set[str] = set()
    for registered_path in registered_paths:
        try:
            approved.add(
                _path_key(
                    canonical_local_media_file(
                        registered_path,
                        label="Registrierter Medienpfad",
                    )
                )
            )
        except MediaPathPolicyError:
            continue

    if _path_key(candidate) not in approved:
        raise MediaPathPolicyError(
            f"{label} ist nicht im aktiven Medienkatalog registriert"
        )
    return str(candidate)


def validate_timeline_media_paths(
    timeline: list[dict[str, Any]],
    registered_video_clips: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Copy a timeline and rebind every path from its registered ``clip_id``."""
    validated: list[dict[str, Any]] = []
    for index, entry in enumerate(timeline):
        if not isinstance(entry, dict):
            raise MediaPathPolicyError(f"Timeline-Cut {index} ist ungueltig")
        clip_id = entry.get("clip_id")
        if not isinstance(clip_id, str) or not clip_id.startswith("clip_"):
            raise MediaPathPolicyError(
                f"Timeline-Cut {index} hat keine gueltige clip_id"
            )
        try:
            video_id = int(clip_id[5:])
        except (TypeError, ValueError) as exc:
            raise MediaPathPolicyError(
                f"Timeline-Cut {index} hat keine gueltige clip_id"
            ) from exc
        registered_clip = registered_video_clips.get(video_id)
        if not registered_clip:
            raise MediaPathPolicyError(
                f"Timeline-Cut {index} ist nicht im aktiven Medienkatalog registriert"
            )

        copied = dict(entry)
        metadata = dict(entry.get("metadata") or {})
        metadata["file_path"] = str(
            canonical_local_media_file(
                str(registered_clip.get("path") or ""),
                label=f"Timeline-Cut {index} file_path",
            )
        )
        copied["metadata"] = metadata
        validated.append(copied)
    return validated


def validate_media_catalog(
    clips: Mapping[int, Mapping[str, Any]],
    *,
    label: str,
) -> dict[int, dict[str, Any]]:
    """Copy a restored catalogue after rejecting network/device references."""
    validated: dict[int, dict[str, Any]] = {}
    for clip_id, clip in clips.items():
        copied = dict(clip)
        copied["path"] = str(
            canonical_local_media_reference(
                str(clip.get("path") or ""),
                label=f"{label} {clip_id} path",
            )
        )
        raw_stems = copied.get("stems_paths")
        if isinstance(raw_stems, str):
            try:
                raw_stems = json.loads(raw_stems)
            except (TypeError, ValueError) as exc:
                raise MediaPathPolicyError(
                    f"{label} {clip_id} stems_paths ist ungueltig"
                ) from exc
        if raw_stems:
            if not isinstance(raw_stems, dict):
                raise MediaPathPolicyError(
                    f"{label} {clip_id} stems_paths ist ungueltig"
                )
            copied["stems_paths"] = {
                str(role): str(
                    canonical_local_media_reference(
                        str(stem_path),
                        label=f"{label} {clip_id} stem {role}",
                    )
                )
                for role, stem_path in raw_stems.items()
                if stem_path
            }
        validated[int(clip_id)] = copied
    return validated


def validate_owned_media_file(
    raw_path: str,
    allowed_root: str | Path,
    *,
    label: str,
) -> str:
    """Validate a local file and require containment in an application-owned root."""
    candidate = canonical_local_media_file(raw_path, label=label)
    try:
        root = Path(allowed_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise MediaPathPolicyError(f"{label} Basisordner ist nicht erreichbar") from exc
    if not root.is_dir() or not candidate.is_relative_to(root):
        raise MediaPathPolicyError(
            f"{label} liegt ausserhalb des anwendungseigenen Ordners"
        )
    return str(candidate)
