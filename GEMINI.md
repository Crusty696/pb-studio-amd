# PB Studio (AMD-Version)

## Project Overview

PB Studio is a specialized local AI multimedia workstation designed for complex media processing and AI-assisted analysis directly on the user's machine. It operates completely offline, without cloud dependencies, and provides full support for AMD hardware via DirectML.

Its primary use case is the autonomous creation of visual accompaniment for long DJ mixes. It acts as an "AI Director" by analyzing audio (rhythm, energy, mood) and thousands of video clips (content, motion, color) using local AI models (e.g., Moondream2, Phi-3, FAISS). It intelligently assembles a video that matches the music's beat and thematic progression to create a cohesive narrative flow.

## Persistent Context

- **Obsidian Vault:** `C:\Users\david\Brain`
- **Vault-Konventionen:** siehe `C:\Users\david\Brain\_meta\AGENT_RULES.md`
- **Decisions-Ablage:** `C:\Users\david\Brain\10_Projects\PB_studio\_wiki\decisions\`
- **Aktuelle Status-Quelle:** Repository CHANGELOG und neueste Decision-Notes im Vault
  (Status-Felder werden hier nicht mehr gepflegt um Drift zu vermeiden)

## Agent-Symmetrie & Kern-Prinzipien

Dieses Repo wird mit Claude Code, OpenAI Codex und Gemini CLI / Antigravity bearbeitet.
Verbindliche agent-übergreifende Regeln stehen in `_meta/AGENT_RULES.md` im Brain-Vault sowie in `AGENTS.md` und `CLAUDE.md`.

1. **Caveman-Modus Standard**: Alle Agenten antworten primär im ultra-komprimierten Caveman-Stil (`[Subjekt] [Aktion] [Grund]. [Nächster Schritt].`), um ~75% Token einzusparen bei 100% technischer Genauigkeit.
2. **100% Ehrlichkeit & Live-Verifikation**: Keine Annahmen, kein Raten, keine Halluzinationen. Alle Aussagen und Fixes müssen an echten Dateien und Tests verifiziert werden.
3. **Anti-Starrheits-Prinzip (Adaptive Flexibilität)**: Keine starren Dogmen bei Normabweichungen. Intention verstehen, bestehenden Code und Nutzen prüfen, Full-Stack-Verdrahtung (WPF UI + FastAPI + DirectML DSP) ganzheitlich anpassen.
4. **Spezialisierte Coding-Skills**: Für Audio-Video-Pacing, BPM/Beat-Grid, EDM-Groove (21+ Genres) und Cut-Point-Kalkulation steht der Full-Stack-Skill `audio-video-pacing-specialist` bereit.
