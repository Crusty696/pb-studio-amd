Arbeitsplan zur Umsetzung der AMD‑Windows‑Version von PB Studio
Ziel und Kontext

Dieser Arbeitsplan beschreibt Schritt für Schritt, wie eine KI‑Assistenz (z. B. Claude Code CLI und Gemini) die bestehende Anwendung PB Studio von einer NVIDIA‑basierten Architektur auf eine reine AMD‑/Windows‑Implementierung migrieren soll. Die Planung basiert auf dem vorliegenden technischen Konzept für AMD (siehe separate Datei) und fasst alle Aufgaben so zusammen, dass ein agentisches System sie nacheinander ausführen kann. Für jede Phase werden die nötigen Vorbedingungen, die konkreten Aufgaben und Hinweise zur Nutzung der jeweiligen KI‑Werkzeuge erläutert.

Hinweis zu Begriffen: In diesem Plan wird der Gerätename „cuda“ weiterhin in Code‑Beispielen verwendet. Dies bedeutet nicht, dass NVIDIA‑CUDA installiert wird. PyTorch nutzt auch auf AMD‑Hardware den Alias „cuda“ für die ROCm‑Back‑End‑Schnittstelle. Alle Installationsanweisungen beziehen sich ausschließlich auf AMD‑ROCm; es wird keinerlei NVIDIA‑Software installiert.

1. Vorbereitungen und Recherche

Dieser Abschnitt stellt sicher, dass der KI‑Agent den Status quo der Anwendung vollständig versteht, bevor Änderungen vorgenommen werden. Die folgenden Anweisungen sind in klaren, auszuführenden Schritten formuliert, damit keine Mehrdeutigkeit entsteht.

Repository und Dokumentation vorbereiten

Repository klonen: Falls noch keine lokale Kopie vorhanden ist, führe über die Windows‑PowerShell oder ein Git‑Terminal den Befehl git clone <repo-url> aus. Ersetze <repo-url> durch die reale URL des PB‑Studio‑Repositories. Lege das Verzeichnis beispielsweise unter C:\Projects\PBStudio an.

Branch anlegen: Wechsle direkt nach dem Klonen in einen neuen Branch, z. B. amd-migration, mit git checkout -b amd-migration. So bleiben die Änderungen von der NVIDIA‑Version getrennt.

Ordnerstruktur dokumentieren: Benutze Python oder ein Tool wie tree (unter Windows: tree /f > tree.txt), um die Struktur des Projekts auszulesen. Erzeuge aus diesem Output ein Markdown‑Dokument module_overview.md, in dem jedes Hauptmodul aufgeführt wird:

Modulname: Verzeichnisname oder Python‑Package.

Pfad: Absoluter Pfad innerhalb des Repositories.

Beschreibung: Kurzer Satz, was das Modul macht (Audioanalyse, Video‑Rendering usw.).

Relevante Dateien: Liste wichtiger Skripte oder Klassen.
Dieses Dokument dient dem KI‑Agenten als Navigationshilfe.

Eintrittspunkte identifizieren: Öffne Dateien wie main.py, __init__.py, requirements.txt, setup.py oder pyproject.toml. Notiere in module_overview.md, welche Skripte beim Programmstart ausgeführt werden und welche Abhängigkeiten (z. B. GUI‑Framework) geladen werden.

Vergleichsplan (NVIDIA → AMD) erstellen

AMD‑Plan lesen: Öffne die bereitgestellte AMD‑Planungsdatei (z. B. amd_conversion_plan.md) und lies sie vollständig durch. Markiere jede Komponente, die laut Plan angepasst werden muss (CUDA → ROCm, NVENC → AMF, pynvml → amd‑smi, Linux → Windows).

Abhängigkeitsliste extrahieren: Erstelle ein neues Dokument dependency_changes.md. In diesem Dokument legst du eine Tabelle mit folgenden Spalten an:

alte_Abhängigkeit (z. B. torch==2.4.1+cu121)

neue_Abhängigkeit (z. B. torch==2.4.1+rocm6.1)

Version (numerisch, z. B. 2.4.1)

Begründung (z. B. „ROCm‑Variante für AMD‑GPU“)

Installationsbefehl (exakter pip‑Befehl)
Recherchiere mithilfe von Gemini, ob die neue Abhängigkeit mit den anderen Paketen kompatibel ist. Füge nur dann einen Eintrag hinzu, wenn eine offizielle Quelle oder ein Release‑Hinweis die Kompatibilität bestätigt. Falls Unsicherheit besteht, vermerke dies explizit.

CPU‑Fallback markieren: Für Komponenten, die möglicherweise nicht auf ROCm laufen (z. B. Moondream), notiere im Dokument eine Spalte Fallback, in der du angibst, ob ein CPU‑Modus implementiert werden muss. Markiere diese Stellen für spätere Aufgaben.

Konfiguration der KI‑Werkzeuge

Installation prüfen: Stelle sicher, dass die KI‑Tools Claude Code CLI und Gemini bereits in der Antigravity‑Umgebung installiert sind. Rufe in der Windows‑Konsole claude code --version und gemini run --version auf. Falls die Befehle nicht verfügbar sind, installiere sie gemäß der Herstelleranleitung (z. B. via pip install claude-cli).

Testläufe ausführen: Erzeuge ein Testskript hello_test.py, das einen simplen „Hello World“‑Code‑String generiert. Starte dieses Skript über die beiden Tools:

claude code hello_test.py

gemini run hello_test.py
Überprüfe, ob die Ausgabe korrekt ist. Dokumentiere das Ergebnis und eventuelle Fehlermeldungen in ai_usage_plan.md.

Rollenverteilung definieren: Lege in ai_usage_plan.md genau fest, wann welcher KI‑Agent verwendet wird:

Gemini: Analyse von Quellcode, Suchen nach bestimmten Funktionen (grep‑ähnliche Aufgaben), Generieren von Testfällen, Prüfen von Abhängigkeitslisten, Verifikation von Kompatibilitätshinweisen.

Claude Code CLI: Erzeugen von neuem Quellcode, automatisiertes Refactoring, Anpassung von Skripten, Schreiben von Unit‑Tests.

Gib jeweils Beispiele und die exakten CLI‑Befehle an, damit der ausführende Agent sie ohne Rückfragen ausführen kann.

2. Einrichtung der Entwicklungsumgebung

In dieser Phase wird die technische Basis auf einem Windows‑Rechner eingerichtet. Jeder Schritt ist exakt beschrieben, um Fehlinterpretationen zu vermeiden.

Installation des Basissystems

Windows 11 verifizieren: Stelle sicher, dass das System Windows 11 (64‑Bit) ausführt. Öffne dazu Einstellungen → System → Info und notiere die genaue Build‑Nummer in env_setup_log.md.

Python 3.11 installieren: Lade den Windows‑Installer von der offiziellen Python‑Website (z. B. python-3.11.6-amd64.exe). Führe ihn aus mit den Optionen „Add Python to PATH“ und „Install for all users“. Nach der Installation öffne eine neue Eingabeaufforderung und führe python --version aus. Verifiziere, dass die Ausgabe 3.11.x zeigt und dokumentiere den Pfad in env_setup_log.md.

ROCm‑Preview für Windows installieren: Lade das neueste ROCm‑Installer‑Paket von AMD (z. B. amd-rocm-6.1.1.exe). Führe das Setup als Administrator aus. Akzeptiere die Standardpfade und notiere in env_setup_log.md das Installationsverzeichnis sowie die Versionsnummer. Starte das System neu, falls der Installer dies verlangt.

FFmpeg mit AMF‑Encoder installieren: Lade ein vorcompiliertes FFmpeg‑Paket mit AMF‑Support (z. B. von https://www.gyan.dev/ffmpeg/builds/). Entpacke es nach C:\ffmpeg. Füge den Ordner C:\ffmpeg\bin dauerhaft zum PATH hinzu. Überprüfe die Installation mit ffmpeg -encoders | findstr amf – es sollten u. a. h264_amf und hevc_amf gelistet sein. Dokumentiere das Ergebnis in env_setup_log.md.

Einrichten der Python‑Umgebung und Installieren der Abhängigkeiten

Virtuelle Umgebung anlegen: Wechsle im Terminal in das Projektverzeichnis (C:\Projects\PBStudio) und führe python -m venv venv aus. Aktiviere sie mit venv\Scripts\activate. Vergewissere dich, dass (venv) vor der Eingabeaufforderung erscheint.

Paketmanager aktualisieren: Führe python -m pip install --upgrade pip setuptools wheel aus, um sicherzustellen, dass der Paketmanager auf dem neuesten Stand ist.

Kritische Bibliotheken installieren: Installiere zunächst die zeitkritischen Pakete einzeln, um Versionskonflikte zu erkennen:

pip install numpy==1.25.4

pip install scipy==1.15.1
Dokumentiere jeweils die Ausgaben von pip show numpy und pip show scipy in env_setup_log.md, um die installierten Versionen festzuhalten.

ROCm‑PyTorch installieren: Installiere die ROCm‑angepassten Pakete mit dem offiziellen Index von PyTorch:
pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/rocm6.1
Nach der Installation erstelle ein kleines Skript check_rocm.py mit folgendem Inhalt:

import torch
print("Torch Version:", torch.__version__)
print("ROCm Version:", torch.version.hip)
print("CUDA available:", torch.cuda.is_available())
print("Device count:", torch.cuda.device_count())


Führe das Skript aus (python check_rocm.py) und stelle sicher, dass torch.cuda.is_available() True und torch.version.hip nicht None ausgibt. Halte diese Ergebnisse in env_setup_log.md fest.

Weitere Pakete installieren: Installiere alle übrigen Pakete aus requirements_amd.txt. Nutze pip install -r requirements_amd.txt. Wenn Fehler auftreten, notiere sie in env_setup_log.md und löse sie, indem du die Versionen anpasst oder fehlende Abhängigkeiten manuell nachinstallierst.

Versionsverwaltung organisieren

Git‑Konfiguration: Falls nicht bereits geschehen, initialisiere im Projektverzeichnis ein Git‑Repository (git init) oder stelle sicher, dass die Remote‑URL eingetragen ist (git remote -v). Konfiguriere den Benutzernamen und die E‑Mail (git config user.name, git config user.email).

Branch‑Strategie: Verwende für jeden Arbeitsschritt einen separaten Commit. Beispielsweise:

git commit -m "docs: add module overview"

git commit -m "feat: replace NVENC encoder with AMF encoder"

git commit -m "test: add unit tests for ROCm device detection"
Dokumentiere diese Commit‑Nachrichten im migration_report.md, damit Nachverfolgbarkeit gewährleistet ist.

3. Anpassung der Core‑Abhängigkeiten

Diese Phase betrifft die Kernbibliotheken des Projekts. Ziel ist es, alle Stellen im Code zu identifizieren, die GPU‑spezifisch sind, und sie für AMD ROCm unter Windows anzupassen.

CUDA‑Aufrufe auffinden und abstrahieren

Suche nach CUDA‑Referenzen: Verwende Gemini oder ein CLI‑Tool (grep -R "torch\.cuda" -n .) im Projektverzeichnis, um alle Vorkommen von torch.cuda, device="cuda" oder torch.device("cuda") zu finden. Sammle die Ergebnisse in einer Datei cuda_usage_report.md mit Zeilennummern und Dateipfaden.

Abstrakte Geräteeinstellung implementieren: Erstelle eine zentrale Hilfsfunktion (z. B. get_device()), die folgende Logik enthält:

import torch
def get_device():
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


Ersetze mithilfe von Claude Code CLI alle direkten Verweise auf torch.device("cuda") im Projekt durch get_device(). Dadurch wird eine einheitliche Gerätesteuerung erreicht, ohne den Namen „cuda“ zu entfernen (ROCm setzt weiterhin cuda als Alias).

Erläuterung: Auch wenn "cuda" im Code erscheint, wird keine NVIDIA‑CUDA‑Runtime installiert. Die ROCm‑Bibliothek nutzt den Bezeichner cuda, um die Hardware‑Abstraktion für AMD‑GPUs kompatibel zu halten.

NVIDIA‑Spezifische Imports entfernen: Durchsuche die Codebasis nach Imports wie import pynvml oder from pynvml import …. Lasse Claude Code CLI diese entfernen oder durch zukünftige AMD‑Monitoring‑Aufrufe (siehe Abschnitt 7) ersetzen.

Numerische Bibliotheken und Inkompatibilitäten

Kompatibilitätsprüfung: Nutze Gemini, um im Code nach Funktionen zu suchen, die von veralteten Versionen von numpy oder scipy abhängen (z. B. Funktionen, die in Version 2.x entfernt wurden). Erstelle eine Liste deprecated_usage.md mit Fundstellen.

Anpassungen erstellen: Für jede Fundstelle generiert Claude Code CLI Alternativen. Beispiel: Wenn numpy.matrix verwendet wird, ersetze sie durch numpy.array oder moderne @‑Operatoren. Dokumentiere die Änderungen im Commit‑Protokoll.

Versionstests einbauen: Füge am Anfang kritischer Module kleine Assertions ein (z. B. assert numpy.__version__.startswith("1.25")). So wird sichergestellt, dass bei späteren Updates eine Fehlermeldung erscheint, falls inkompatible Versionen installiert sind.

Transformers‑ und Vision‑Modelle validieren

Modellunterstützung prüfen: Für jedes verwendete Modell (CLIP, Moondream, SigLIP, RAFT usw.) recherchiere mit Gemini, ob es mit ROCm‑PyTorch kompatibel ist. Notiere die Ergebnisse in model_support.md mit Spalten Modell, ROCm unterstützt (Ja/Nein), Quelle, Anmerkungen.

CPU‑Fallback implementieren: Wenn ein Modell nicht GPU‑unterstützt ist oder nur experimentell auf ROCm läuft, implementiere einen optionalen Flag use_cpu. Beispiel:

device = get_device()
if force_cpu:
    device = torch.device("cpu")


Aktualisiere Ladefunktionen wie model.to(device) entsprechend. Claude Code CLI erstellt diese Anpassungen.

Speicher‑Management: Achte darauf, Speicherzugriffe zu synchronisieren (torch.cuda.synchronize()), falls asynchrone Operationen benutzt werden. Prüfe mit Gemini, ob solche Synchronisationen vorhanden sind oder ergänzt werden müssen.

4. Audio‑Pipeline anpassen

Die Audio‑Pipeline nutzt vor allem CPU‑basierte Bibliotheken, es gibt jedoch einzelne GPU‑optimierte Komponenten. Alle Schritte sind so formuliert, dass sie ohne Unklarheit ausgeführt werden können.

Demucs konfigurieren

GPU‑Parameter prüfen: Untersuche vorhandene Skripte auf Befehle wie demucs -d cuda oder demucs --device cuda. Ersetze diese durch eine dynamische Auswahl:

# Beispielaufruf für GPU
python -m demucs --device cuda --out outputs_dir input.wav
# Beispielaufruf für CPU
python -m demucs --device cpu --out outputs_dir input.wav


Implementiere in den Audio‑Wrapper‑Skripten eine Funktion, die vor dem Aufruf prüft, ob eine GPU verfügbar ist (torch.cuda.is_available()) und entsprechend den Parameter --device setzt. Claude Code CLI soll diesen Wrapper erstellen.

Wichtig: Auch wenn hier das Schlüsselwort cuda verwendet wird, wird keine NVIDIA‑CUDA‑Installation benötigt. Die ROCm‑Version von PyTorch akzeptiert weiterhin cuda als Gerätenamen. Diese Einstellung aktiviert die AMD‑GPU.

Fehlerbehandlung: Fange mögliche Laufzeitfehler ab (z. B. „GPU not available“ oder „Unsupported device type“). Gib bei Fehlern eine verständliche Fehlermeldung aus und wechsle automatisch in den CPU‑Modus. Dokumentiere dieses Verhalten im Code.

Parameter validieren: Überprüfe, ob in den ursprünglichen Demucs‑Aufrufen zusätzliche Parameter wie --segment, --overlap oder --two-stems verwendet werden. Stelle sicher, dass diese Parameter unverändert bleiben und bei der Migration nicht versehentlich gelöscht werden.

Beat‑Detection‑Bibliotheken

Bibliotheksversionen prüfen: Obwohl beatnet, madmom und librosa CPU‑basiert arbeiten, hängen sie von numpy und scipy ab. Verifiziere in der virtuellen Umgebung mit pip show beatnet, pip show madmom und pip show librosa, welche Versionen installiert sind. Notiere sie in env_setup_log.md.

Kompatibilitätsfixes: Wenn madmom Patches benötigt (z. B. wegen des Imports von collections.MutableMapping in Python 3.11), implementiere eine zentrale Patch‑Funktion in utils/compat.py. Gemini soll prüfen, ob solche Patches bereits an mehreren Stellen eingefügt sind, und Claude Code CLI soll sie bereinigen und zusammenführen.

Testdateien anlegen: Lege Beispiel‑Audio‑Dateien (z. B. example_beat.wav) im Ordner test_assets ab. Erstelle Skripte (test_beat_detection.py), die diese Dateien mit allen drei Bibliotheken analysieren. Vergleiche die Ergebnisse (Beats pro Minute, Beat‑Zeitstempel) und dokumentiere sie in benchmark.md.

5. Video‑Pipeline anpassen

Die Videokomponenten müssen auf AMD‑Hardware und Windows lauffähig sein, daher werden Encodierung und Decodierung entsprechend angepasst. Jeder Schritt beinhaltet explizite Anweisungen für den KI‑Agenten.

Optical‑Flow‑Modul (RAFT)

Kompatibilitätsprüfung: Nutze Gemini, um nach Vorkommen des Aufrufs raft = torchvision.models.optical_flow.raft_large(pretrained=True) oder ähnlicher Funktionen zu suchen. Sammle die Fundstellen in raft_usage.md.

Gerät anpassen: Erstelle mit Claude Code CLI einen Wrapper load_raft_model(device), der das Modell mit dem übergebenen Gerät lädt. Beispiel:

from torchvision.models.optical_flow import raft_large
def load_raft_model(device):
    model = raft_large(pretrained=True).to(device)
    model.eval()
    return model


Rufe diese Funktion überall dort auf, wo das Modell benötigt wird, und verwende device = get_device() aus Abschnitt 3.

Testskript erstellen: Schreibe ein Skript test_raft.py, das zwei Beispiel‑Frames (z. B. aus test_assets/frame1.png und frame2.png) lädt und den Optical‑Flow‑Output ausgibt. Führe das Skript einmal im GPU‑ und einmal im CPU‑Modus aus; vergleiche die Laufzeiten und dokumentiere sie in benchmark.md.

Frame‑Extraktion und Video‑Decoding

Entfernen von VAAPI und Linux‑Pfaden: Suche im Code nach Argumenten wie -hwaccel vaapi, -vaapi_device, oder Linux‑spezifischen Pfaden (/dev/dri). Entferne diese Optionen. Gemini soll eine Liste aller betroffenen Zeilen erstellen.

AMF‑ und DirectX‑Decoding: Ersetze die Dekodierung durch Optionen, die unter Windows funktionieren. Bei FFmpeg‑Aufrufen im Python‑Code sollte die Videodecodierung ohne explizite Hardwareoption funktionieren (FFmpeg wählt automatisch DirectX). Für Hardware‑Encoding wird der AMF‑Encoder genutzt (siehe Abschnitt 6). Claude Code CLI soll die subprocess.run‑Aufrufe so anpassen, dass sie unter Windows laufen.

Pfadseparatoren vereinheitlichen: Stelle sicher, dass alle Dateipfade im Code mit os.path.join oder pathlib.Path erstellt werden. Dadurch werden Linux‑Pfadtrennzeichen (/) durch die korrekte Windows‑Schreibweise (\) ersetzt. Gemini soll nach harten Pfadstrings suchen und eine Liste path_fix_report.md generieren, die dann von Claude Code CLI korrigiert wird.

Video‑Captioning (Moondream)

GPU/CPU‑Schalter einbauen: Implementiere in der Klasse oder Funktion, die Moondream aufruft, einen Parameter use_cpu. Wenn dieser Parameter True ist oder get_device().type == "cpu", initialisiere das Modell ohne GPU. Beispiel:

def load_moondream_model(use_cpu=False):
    device = torch.device("cpu") if use_cpu or not torch.cuda.is_available() else torch.device("cuda")
    model = Moondream.from_pretrained(...).to(device)
    return model


Lasse Gemini alle Aufrufe von Moondream identifizieren und passe sie an.

Performance testen: Erstelle ein Skript test_moondream.py, das eine kleine Videodatei lädt, Untertitel generiert und sowohl die Laufzeit als auch den Speicherbedarf misst. Dokumentiere, ob die Ausgabe identisch ist, wenn GPU und CPU verwendet werden.

Scene Detection & ChromaDB

Datenbankpfade anpassen: Stelle sicher, dass die Pfade zu ChromaDB‑Datenbanken (.db‑Dateien) über Path().resolve() erzeugt werden. Gemini soll nach statischen Strings wie ./database/ suchen und diese durch plattformunabhängige Pfaderzeugung ersetzen.

Dateisystemkompatibilität: Prüfe, ob Funktionen, die auf Timestamps oder Dateirechte achten (z. B. os.stat), unter Windows dieselben Ergebnisse liefern. Dokumentiere Abweichungen und korrigiere die Funktionalität bei Bedarf.

6. Rendering‑Pipeline aktualisieren

Das Rendering‑Modul ist besonders anfällig für Fehlkonfigurationen, da es stark hardwareabhängig ist. Die nachfolgenden Schritte führen systematisch durch die Anpassung.

Encoder‑Ersatz (NVENC → AMF)

Vorkommen identifizieren: Mit Gemini eine vollständige Liste aller Skripte erstellen, in denen FFmpeg‑Encoder wie h264_nvenc, hevc_nvenc oder av1_nvenc vorkommen. Speichere diese Liste in encoder_usage.md inklusive Codeauszug.

Encoder‑Auswahl abstrahieren: Implementiere eine Hilfsfunktion, z. B. select_encoder(codec), die basierend auf dem gewünschten Codec (h264, hevc oder av1) den passenden Encoder zurückgibt:

def select_encoder(codec: str) -> str:
    if codec == "h264":
        return "h264_amf"
    elif codec == "hevc":
        return "hevc_amf"
    elif codec == "av1":
        return "libaom-av1"  # Software‑Fallback, da AMF noch keinen AV1‑Encoder bietet
    else:
        raise ValueError(f"Unbekannter Codec: {codec}")


Claude Code CLI soll alle Hardcodierungen von NVENC ersetzen, indem es die Rückgabe dieser Funktion in die FFmpeg‑Befehle einfügt.

Parameter für AMF: Dokumentiere in encoder_params.md die empfohlenen Presets für AMD: Für H.264/HEVC bietet AMF die Optionen -usage (0=Transcoding, 1=LowLatency, 2=Webcam, 3=ScreenCapture) und -quality (0=p1 höchste Qualität, 3=p4 ausgewogen, 6=p7 niedrigste Qualität). Definiere Standardwerte wie -usage 1 -quality 3 für Low‑Latency‑Export. Gemini soll diese Parameter für alle Encoding‑Befehle vorschlagen.

FFmpeg‑Befehle anpassen

API vs. Subprocess: Prüfe, ob das Projekt ffmpeg-python verwendet oder Kommandozeilen mit subprocess.run ausführt. In beiden Fällen müssen die neuen Encoder und Parameter integriert werden. Ersetze NVIDIA‑spezifische Flags wie -gpu, -hwaccel cuda oder -preset p7 durch AMF‑Äquivalente (-usage, -quality).

Beispielbefehle: Füge in ffmpeg_cmd_examples.md mehrere Beispielbefehle ein, damit der KI‑Agent weiß, wie die korrekten Aufrufe aussehen. Beispiel:

ffmpeg -i input.mp4 -c:v h264_amf -usage 1 -quality 3 -c:a copy output.mp4
ffmpeg -i input.mp4 -c:v hevc_amf -usage 1 -quality 3 -c:a aac -b:a 192k output_hevc.mp4


Pipelines testen: Erstelle ein Skript test_ffmpeg_encode.py, das kurze Beispielvideos rendert. Vergleiche die Qualität und Dateigröße mit der ursprünglichen NVENC‑Version (falls vorhanden) und dokumentiere die Ergebnisse in benchmark.md. Claude Code CLI soll das Skript schreiben, und Gemini soll die Ergebnisse interpretieren.

7. GPU‑Monitoring ersetzen

Zur Überwachung der GPU‑Ressourcen muss das bisherige NVIDIA‑Monitoring vollständig ersetzt werden. Diese Schritte stellen sicher, dass sowohl eine Python‑API als auch ein Kommandozeilen‑Fallback verfügbar sind.

Migration von pynvml zu amd‑smi

Import‑Austausch: Durchsuche das Projekt nach import pynvml oder from pynvml. Erstelle mit Gemini eine Liste pynvml_usage.md. Claude Code CLI ersetzt diese Imports durch from amd_smi import amdsmi_get_gpu_vram_usage bzw. andere benötigte Funktionen.

Neue API nutzen: Implementiere eine Klasse AmdGpuMonitor in gpu_manager.py mit Methoden wie get_vram_usage() und get_temperature(). Diese Methoden rufen intern amdsmi_get_gpu_vram_usage und andere Funktionen der Python‑Bibliothek auf. Beispiel:

from amd_smi import amdsmi_initialize, amdsmi_device_handle_by_index, amdsmi_get_gpu_vram_usage, amdsmi_get_temp_metric
class AmdGpuMonitor:
    def __init__(self):
        amdsmi_initialize()
        self.handle = amdsmi_device_handle_by_index(0)
    def get_vram_usage(self):
        total, used = amdsmi_get_gpu_vram_usage(self.handle)
        return total, used
    def get_temperature(self):
        return amdsmi_get_temp_metric(self.handle, 0)


Verwende diese Klasse anstelle der bisherigen NVML‑Objekte.

Kommandozeilen‑Fallback

Verfügbarkeit prüfen: Da die AMD‑Python‑API nur verfügbar ist, wenn die ROCm‑Schnittstelle installiert ist, implementiere einen Fallback. Prüfe zunächst im Code, ob das Modul amd_smi importiert werden kann (try…except ImportError). Wenn der Import fehlschlägt, verwende die amd‑smi.exe aus dem ROCm‑Installer.

Subprocess‑Parsing: Schreibe eine Funktion parse_amd_smi_output(), die subprocess.run(["amd‑smi.exe", "--showmemuse"]...) aufruft, die Ausgabe in eine temporäre Datei oder in einen String schreibt und dann per regulärem Ausdruck die Werte für „VRAM Total“ und „VRAM Used“ herausfiltert. Beispiel einer Zeile aus der Ausgabe:

GPU[0] : VRAM Total (B): 2147483648, VRAM Used (B): 1073741824


Gemini soll eine robuste Parsing‑Funktion entwerfen; Claude Code CLI implementiert sie im Code.

Fallback‑Klasse: Implementiere in gpu_manager.py eine Klasse AmdGpuMonitorCLI, die diese Parsing‑Funktion verwendet. Entscheide zur Laufzeit, welche Klasse genutzt wird.

Integration in die GUI

Signal‑und‑Slot‑Struktur beibehalten: Die Oberfläche (z. B. Qt‑Signal gpuDataUpdated) soll unverändert bleiben, um keine Frontend‑Änderungen zu verursachen. Passe lediglich die Datenquelle an, sodass AmdGpuMonitor oder AmdGpuMonitorCLI die Werte liefert.

Tests erstellen: Schreibe mit Claude Code CLI Unit‑Tests für beide Monitor‑Klassen, die eine simulierte Ausgabe der API bzw. des CLI verwenden. So wird sichergestellt, dass die GUI auch bei unerwarteten Ausgaben stabil bleibt.

8. Test‑ und Validierungsphase

Das Testkonzept muss sicherstellen, dass alle Änderungen korrekt funktionieren und keine Leistungseinbußen auftreten. Die folgenden Aufgaben sind klar getrennt und ausführbar.

Unit‑Tests anpassen und erweitern

Identifikation der GPU‑Tests: Nutze pytest --collect-only oder Gemini, um eine Liste aller Testfälle zu erhalten. Suche speziell nach Tests, die torch.cuda oder NVENC‑Funktionen nutzen. Dokumentiere sie in gpu_tests.md.

Änderung der Assertions: Ersetze in diesen Tests alle direkten Abfragen an torch.cuda.device_count() durch Aufrufe des neuen Monitorings (AmdGpuMonitor().get_vram_usage() oder torch.cuda.is_available()). Claude Code CLI soll die Änderungen vornehmen.

Neue Tests hinzufügen: Schreibe Unit‑Tests, die die neuen Funktionen wie select_encoder(), get_device(), AmdGpuMonitor und AmdGpuMonitorCLI abdecken. Nutze Mock‑Objekte, um die AMD‑API und die CLI‑Ausgabe zu simulieren. Achte darauf, sowohl Erfolgs- als auch Fehlerpfade zu testen.

End‑to‑End‑Tests durchführen

Testdaten vorbereiten: Lege im Ordner test_assets mehrere kurze Audio‑ und Video‑Dateien ab. Die Dateien sollten verschiedene Formate und Auflösungen abdecken (z. B. MP3, WAV, MP4 in 1080p und 4K).

Testskripte generieren: Claude Code CLI erstellt ein Skript run_pipeline_test.py, das folgende Schritte ausführt:

Importiert eine Testdatei und führt die Audioanalyse (Demucs, Beat‑Detection) aus.

Startet die Videoanalyse (Optical Flow, Captioning, Scene Detection).

Rendert ein kurzes Ausgabematerial mit der neuen AMF‑Encoder‑Pipeline.

Protokolliert Speicherverbrauch (VRAM), Laufzeit und erzeugte Dateigröße in eine Log‑Datei e2e_test_log.json.

Ergebnisprüfung: Schreibe ein weiteres Skript verify_results.py, das die Log‑Datei parst und prüft, ob alle Metriken innerhalb akzeptabler Grenzen liegen (z. B. VRAM‑Nutzung < 8 GB, Laufzeit pro Minute Video < 120 s). Wenn Grenzwerte überschritten werden, gibt das Skript eine Fehlermeldung aus.

Performance‑Benchmarking

Vergleichskonfiguration: Wenn Zugriff auf die ursprüngliche NVIDIA‑Version besteht, führe dieselben End‑to‑End‑Tests dort durch und sammle die Metriken in e2e_test_log_nvidia.json. Ansonsten notiere als Referenz die internen Benchmarkwerte aus der Dokumentation (falls vorhanden).

Benchmark‑Skript: Erstelle benchmark_comparison.py, das beide Log‑Dateien einliest, die Metriken tabellarisch gegenüberstellt und pro Kategorie (Laufzeit, VRAM, Dateigröße) die prozentuale Differenz berechnet. Ein Beispiel‑Tabellenformat kann wie folgt aussehen:

Metrik	AMD‑Wert	NVIDIA‑Wert	Differenz
Laufzeit s	115	100	+15 %
VRAM (MB)	6500	6200	+4.8 %

Gemini soll das Format definieren und die Ausgabe überprüfen. Claude Code CLI implementiert das Skript.

9. Dokumentation und Übergabe

Eine umfassende Dokumentation verhindert Missverständnisse und erleichtert die Übergabe. Erstelle die folgenden Dokumente mit klaren Strukturen und detaillierten Inhalten.

README.md aktualisieren

Installationsanleitung: Ergänze die README um einen Abschnitt „Installation auf Windows“, der Schritt für Schritt erläutert:

Voraussetzungen (Windows 11, AMD GPU, Python 3.11, ROCm Public Preview, FFmpeg). Liste spezifische GPU‑Modelle (z. B. Radeon RX 7000‑Serie).

Download‑Links und Befehle, die aus Abschnitt 2 entnommen werden können (z. B. URLs zu ROCm‑Installer, Python‑Installer).

Einrichtung der virtuellen Umgebung (python -m venv venv usw.) und Installation der Pakete.

Ausführen der Anwendung (z. B. python main.py) und Hinweise zur Konfiguration.

Feature‑Überblick: Beschreibe kurz die Hauptfunktionen von PB Studio (Audioanalyse, Video‑Matching, Rendering) und weise darauf hin, dass die AMD‑Version identische Features bietet. Verweise auf den AMD‑Plan und auf bekannte Einschränkungen (z. B. experimenteller ROCm‑Support).

Bekannte Probleme: Füge einen Abschnitt „Bekannte Einschränkungen“ hinzu, der aktuelle Einschränkungen wie „ROCm auf Windows ist Public Preview und unterstützt nur bestimmte GPUs“ und „Moondream läuft ggf. nur auf CPU“ aufführt. Verlinke auf model_support.md.

Quellen und Verweise: Stelle sicher, dass alle verwendeten externen Quellen (Dokumentationslinks, Blogs, Issues) mit Fußnoten oder Endnoten in der README verlinkt sind.

Beitragsrichtlinien (CONTRIBUTING.md)

Workflows erläutern: Beschreibe, wie neue Beiträge eingereicht werden (Fork → Branch → Pull Request). Definiere Namenskonventionen für Branches (z. B. feature/<beschreibung>, fix/<bug>).

Nutzung der KI‑Tools: Lege fest, dass Gemini für Recherchen, Analysen und Testplanung genutzt wird und Claude Code CLI für Code‑Erzeugung. Beschreibe, wie Ergebnisse der KI von menschlichen Reviewer:innen geprüft werden müssen.

Code‑Stil und Linter: Verweise auf pylint oder flake8‑Regeln, die im Projekt eingesetzt werden, und auf das Format für Commit‑Nachrichten (Conventional Commits). Füge Beispiel‑Commit‑Nachrichten hinzu.

Abschluss‑ und Migrationsbericht

Dokumentation der Schritte: Erstelle migration_report.md, in dem jeder im Arbeitsplan beschriebene Schritt chronologisch dokumentiert ist. Zu jedem Schritt gehören: Ziel, durchgeführte Aktion, genutzte Tools (Gemini/Claude Code CLI), auftretende Probleme und Lösungswege.

Offene Punkte und Empfehlungen: Liste Probleme, die nicht vollständig gelöst werden konnten (z. B. fehlende GPU‑Unterstützung für ein bestimmtes Modell). Gib Empfehlungen für zukünftige Arbeiten (z. B. Updates auf neuere ROCm‑Versionen, Integration weiterer AMD‑Modelle).

Lessons Learned: Fasse Erkenntnisse aus der Migration zusammen, z. B. „ROCm unter Windows benötigt längere Initialisierungszeiten“ oder „AMF‑Encoder erfordert Feinabstimmung der -quality‑Parameter“. Diese Erfahrungswerte helfen späteren Entwickler:innen.

10. Automatisierung in Antigravity

Die Antigravity‑Plattform ermöglicht die Orchestrierung aller Arbeitsphasen durch eine automatisierte Pipeline. Um eine fehlerfreie Automatisierung sicherzustellen, sind folgende Schritte erforderlich:

Workflow‑Definition in Antigravity

Phasen als Tasks modellieren: Lege für jede Phase des Arbeitsplans (Vorbereitung, Einrichtung, Core‑Anpassung, Audio‑ und Video‑Pipeline, Rendering, Monitoring, Testen, Dokumentation) einen separaten Task an. Benutze die Antigravity‑Schnittstelle, um die Ausführungsreihenfolge festzulegen.

CLI‑Aufrufe konfigurieren: Hinterlege für jeden Task die exakten Befehle, die ausgeführt werden sollen, z. B. gemini run find_cuda_usage.py oder claude code generate_wrapper.py. Stelle sicher, dass die Arbeitsverzeichnisse und Umgebungsvariablen (z. B. Aktivierung der virtuellen Umgebung) korrekt gesetzt sind.

Eingabe‑/Ausgabe‑Abhängigkeiten festlegen: Definiere, welche Dateien ein Task als Input benötigt (z. B. module_overview.md, dependency_changes.md) und welche Dateien er erzeugt (z. B. encoder_usage.md, benchmark.md). Diese Angaben werden in der Pipeline‑Definition referenziert, damit die Reihenfolge der Aufgaben logisch bleibt.

Konfigurationsdateien für die KI‑Agenten

YAML/JSON‑Schema erstellen: Erstelle ein Schema (z. B. ai_tasks.yaml) mit folgenden Feldern:

task_name: Name des Arbeitsschritts

tool: gemini oder claude-code

command: CLI‑Befehl, der ausgeführt werden soll

inputs: Liste der benötigten Dateien

outputs: Liste der erzeugten Dateien

description: Menschlich lesbare Beschreibung des Schritts
Claude Code CLI soll ein Skript schreiben, das dieses YAML liest und die Pipeline in Antigravity anlegt.

Parameter übergeben: Für wiederkehrende Parameter wie Pfade oder GPU‑Flags nutze Variablen in der YAML (z. B. ${PROJECT_DIR}), die beim Start der Pipeline ersetzt werden. Dadurch kann die Pipeline in verschiedenen Umgebungen laufen.

Monitoring und Logging

Statusabfragen implementieren: Verwende die Antigravity‑API, um den Status jedes Tasks zu überwachen (Queued, Running, Success, Failed). Schreibe ein Python‑Skript monitor_pipeline.py, das periodisch den Pipeline‑Status abfragt und in pipeline_log.json speichert.

Fehlerbehandlung: Definiere in der Pipeline einheitliche Fehlerreaktionen. Wenn ein Task fehlschlägt, soll die Pipeline entweder stoppen oder einen vordefinierten Recovery‑Task ausführen (z. B. erneutes Installieren eines Pakets). Dokumentiere diese Logik in ai_tasks.yaml.

GUI‑Signal‑Anbindung: Nutze, falls vorhanden, die GUI‑Progress‑Signale der Anwendung, um den Fortschritt der Antigravity‑Pipeline anzuzeigen. Implementiere dazu einen Listener, der bei Änderungen im pipeline_log.json die GUI aktualisiert.

11. Abschluss

Dieser Arbeitsplan bildet die Grundlage für eine vollständig automatisierte, dennoch nachvollziehbare Migration von PB Studio. Durch die detaillierten, nicht missverständlichen Anweisungen kann eine KI‑gestützte Entwicklungsassistenz alle Aufgaben sequenziell und ohne zusätzliche Interpretationsleistung ausführen. Die Kombination aus Gemini für Recherchen und Analysen, Claude Code CLI für Code‑Generation und Antigravity für Orchestrierung sorgt für einen strukturierten und reproduzierbaren Prozess. Vor der finalen Veröffentlichung sollte der migrierte Build dennoch von einer menschlichen Entwicklerin oder einem Entwickler geprüft werden, um etwaige Edge‑Cases zu erkennen und die Benutzer‑Dokumentation auf Verständlichkeit zu testen.