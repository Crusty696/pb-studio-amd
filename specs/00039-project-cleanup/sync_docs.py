from pathlib import Path
import shutil

out = Path(__file__).resolve().parent
root = out.parents[1]
vault = Path('C:/Users/david/Brain/10_Projects/PB_studio')
entry = ('Bereinigung: 49 belegte Wegwerfziele entfernt, 734648061 logische Bytes. '
         'Getrackte Dateien und Venv-Interpreter hashgleich. 35 Dublettengruppen inventarisiert; '
         'QC-Belege, Sicherheitsstubs, Modelle, offene Arbeiten und Produktionsdaten erhalten. '
         'Keine Produktcodeaenderung oder neue Live-Abnahme. '
         'Beleg: specs/00039-project-cleanup/report.md. Spec00038 bleibt offen.')
for name in ('INDEX.md', 'log.md'):
    source = vault / name
    backup = out / ('vault-' + name + '.before')
    if not backup.exists():
        shutil.copy2(source, backup)
    text = source.read_text(encoding='utf-8')
    if name == 'INDEX.md':
        import re
        text = re.sub(r'(?m)^updated:.*$', 'updated: 2026-11-01', text, count=1)
        end = text.find('\n---', 3) if text.startswith('---') else -1
        pos = text.find('\n', end + 4) + 1 if end >= 0 else 0
        text = text[:pos] + '\n## Bereinigung 2026-11-01\n\n' + entry + '\n\n' + text[pos:]
    else:
        text += '\n\n## 2026-11-01 - Projektbereinigung\n\n' + entry + '\n'
    source.write_text(text, encoding='utf-8')
changelog = root / 'CHANGELOG.md'
text = changelog.read_text(encoding='utf-8')
changelog.write_text(text + '\n\n## 2026-11-01 - Lokale Bereinigung\n\n' + entry + '\n', encoding='utf-8')
tasks = out / 'tasks.md'
tasks.write_text(tasks.read_text(encoding='utf-8').replace('- [ ]', '- [X]'), encoding='utf-8')
