import os
from pathlib import Path

def update_vault():
    log_path = Path("C:/Users/david/Brain/10_Projects/PB_studio/log.md")
    memory_path = Path("C:/Users/david/Brain/_meta/agent_memory/gemini/MEMORY.md")
    
    # 1. Update log.md
    if log_path.exists():
        content = log_path.read_text(encoding="utf-8")
        
        # New entry
        new_entry = """## [2026-05-26T01:10] fix | Kritische Speicher- & VRAM-Härtung sowie WPF-DI-Lifecycle-Sanierung abgeschlossen
- **Z-UI (WPF DI-Scope Härtung):** Umstellung von `AudioLibraryView`, `VideoLibraryView` und `ChatView` auf lokales `IServiceScope` Auflösungsmuster. Entlädt transiente IDisposable-ViewModels beim `Unloaded`-Event restlos aus dem Microsoft DI-Cache, was massive Speicherlecks bei Tab-Wechseln vollständig eliminiert.
- **Z-CORE (StemSeparator VRAM):** Integration von `VRAMBudgetManager` (`get_vram_manager()`) in `StemSeparator`. Reserviert, committet und released VRAM sauber vor und nach der Separation, wodurch DirectML OOMs im Multi-Process-Betrieb verhindert werden.
- **Z-AUDIO (SubtrackDetector RAM):** Chunked Chroma CQT Berechnung in 5-Minuten-Intervalle (300 Sekunden) aufgeteilt. Verhindert unkomprimierte Peak-RAM-Spikes bei mehrstündigen DJ-Mixes und schont die Speicherbandbreite.
- **Z-DOCS (Bereinigung):** 16 veraltete Markdown-Auditberichte aus dem Root-Verzeichnis sauber ins Archiv (`archive/audits/`) überführt, um den Workspace übersichtlich zu halten.
- **Verifikation & Compliance**: Gesamte Pytest-Suite (`727 passed, 9 skipped`) fehlerfrei durchlaufen. WPF-Release-Build fehler- und warnungsfrei kompiliert. Alle planmäßigen Gates (`plan.md`, `tasks.md`, `.completed`, `qc-report.md`, `.qc-passed` und `autopilot-log.md`) erfolgreich angelegt und in Git committed.

"""
        # Find where to insert (usually after the header, before the first heading)
        # We can append it after the title and intro, or insert right before the first "## [2026-05-25"
        marker = "## [2026-05-25"
        if marker in content:
            parts = content.split(marker, 1)
            updated_content = parts[0] + new_entry + marker + parts[1]
            log_path.write_text(updated_content, encoding="utf-8")
            print("Successfully updated C:/Users/david/Brain/10_Projects/PB_studio/log.md")
        else:
            # Fallback to append at the end
            log_path.write_text(content + "\n" + new_entry, encoding="utf-8")
            print("Appended to C:/Users/david/Brain/10_Projects/PB_studio/log.md (fallback)")
            
    # 2. Update MEMORY.md
    if memory_path.exists():
        content = memory_path.read_text(encoding="utf-8")
        new_bullet = "- [2026-05-26] Speicher- & VRAM-Härtung: IServiceScope-Musters im WPF-Frontend löst kritische DI-Lebenszyklus-Speicherlecks transienter ViewModels. VRAMBudgetManager-Integration im StemSeparator verhindert DirectML OOMs. Chunked-Chroma-CQT in SubtrackDetector verhindert Peak-RAM-Spikes bei Mix-Importen."
        
        # Insert bullet at the end of the file or at the end of chronologisch list
        if new_bullet not in content:
            updated_content = content.rstrip() + "\n" + new_bullet + "\n"
            memory_path.write_text(updated_content, encoding="utf-8")
            print("Successfully updated C:/Users/david/Brain/_meta/agent_memory/gemini/MEMORY.md")

if __name__ == "__main__":
    update_vault()
