# PB Studio — Cowork Batch 2: P2.2 + P2.3 + P1.5 + earlier work
# 2026-05-15

if (Test-Path .git/index.lock) {
    Remove-Item -Force .git/index.lock
    Write-Host "[OK] Lock entfernt" -ForegroundColor Green
}

# 1. P2.2 Compressed depth metadata
git add src/pb_studio/data/repositories/media_repository.py
git commit -m @"
feat(data): gzip-compress meta-JSON over 10KB (Spec 00009 T006)

media_repository.py: _serialize_meta() + _deserialize_meta_str() Helpers.
JSON-meta > 10KB wird gzip-komprimiert mit Magic-Prefix 'GZ1:' + b64.
_row_to_dict() decodiert transparent beim Lesen.

Test (REPL roundtrip):
- klein (65 B) -> plain JSON, kein Magic
- gross (93 KB raw -> 2.9 KB compressed) = 96.8% disk-saving
- malformed GZ1: -> graceful fallback {} mit warning

Bytes: 11815 -> 14425 (+2610).

Cross-Zone-Hinweis: backend/app_state.py + scripts/media_dedup_*.py lesen
metadata_json teilweise direkt aus Roh-Rows (umgehen die transparente
Decompression). Schreibseiten gehen alle durch MediaRepository, daher kein
Datenkorruptionsrisiko. Follow-up: Identische Helper in app_state.py
einfuehren wenn das Schema in Produktion komprimierte Rows hat.

Refs: specs/00009-data-depth-visualization T006
"@

# 2. P2.3 Downsampling marker comment
git add PBStudio.UI/ViewModels/TimelineViewModel.cs
git commit -m @"
docs(ui): explicit Spec-00009-T008 marker fuer Downsampling-Block

XML-Doc-Comment ueber UpdateSpectralPoints() in TimelineViewModel.cs:
'/// Spec 00009 T008 / STF-001: Dynamic Downsampling fuer SpectralPoints.'

Macht das Performance-Ziel (AD-004: <16ms downsample-time bei 1000 raw
points) explizit auffindbar fuer zukuenftige Refactorings.

Bytes: 28757 -> 29119 (+362). Brace-Balance unveraendert (128/128).
Pure-Doc, keine Code-Aenderung.

Refs: specs/00009-data-depth-visualization T008
"@

# 3. P1.5 Coverage-Hang-Fix (Test-Config-Files)
git add pytest-coverage.ini .coveragerc coverage_run_v2.bat
git commit -m @"
test(coverage): dedicated config + hardware-test exclusion (P1.5)

P1.5 Pytest+Coverage Hang Bug: Coverage-instrumented Runs hingen bei
test_gpu_load_fallback.py wegen CLR/pythonnet-Init-Deadlock unter
coverage.py-Instrumentierung.

Fixes:
- pytest-coverage.ini: dedizierte pytest-Config mit --timeout=20 +
  --ignore fuer Hardware-Tests (test_gpu_load/temperature_fallback,
  test_separator). Separate von pytest.ini damit Standard-Runs alle
  Tests laufen lassen.
- .coveragerc: coverage-Source-Definition + omit-Pattern fuer
  ui_legacy_archived, migrations, workers, Tests.
- coverage_run_v2.bat: Wrapper-Skript fuer Doppelklick-Run.

Verwendung:
  doppelklick coverage_run_v2.bat
  -> erzeugt coverage_v2_output.log mit Top-30 + TOTAL + Worst-20 Modulen

Wenn User die Coverage-Daten will: bat starten, ca. 2 min warten,
coverage_v2_output.log lesen.

Refs: PLAN_OPEN_TASKS_2026-05-15.md P1.5
"@

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Green
git log --oneline -8
