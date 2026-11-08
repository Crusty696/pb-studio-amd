"""Publish the verified bounded status to the user's replacement KI-Hirn."""
import hashlib
import json
import urllib.request
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent
validation = json.loads((OUT / "final-validation.json").read_text())
assert validation["distinct_passed"] == 186 and validation["protected_unchanged_after_cpu_tests"]
text = (
    "PB-STUDIO T055 T056 ABSCHLUSS 2026-10-19. Aktualisiert T054-Nachfolgestand, keine Gesamtqualitaetsfreigabe. "
    "T05542 echte Caption-Aufrufe:16 Vorschau/nativ JPEG/PNG,8 Reasoning,18 native Bilder sechs Clips drei Zeitpunkte. "
    "T053/T054 waren480x270-Vorschau-Eingaenge; kein Originalframe-Nachweis. Native Aufloesung verbessert V03-Zweizahl; "
    "spaeterer Zeitpunkt erkennt Wasserfall und Clipmerge behaelt ihn. Mittlerer V03-Wasserfallfehler und V02-Tor/Ort verbleiben. "
    "PNG/Reasoning nicht global umgestellt, kein zusaetzlicher Caption-Produktfix gerechtfertigt. Gemma4E4B lokal Vulkan, "
    "Qwen-Override fehlt weiter im Inventar; kein Download/Providerwechsel. "
    "T056 belegter SigLIP-Codefehler: CLIP- statt SigLIP-Normalisierung. Lokale registrierte Processorconfig verlangt mean/std0.5/0.5; "
    "ONNX normalisiert nicht intern. src/pb_studio/ai/siglip_wrapper.py korrigiert und Einzel/Batchpfad vereinheitlicht. "
    "42 echte DirectML-Inferenzen:18 gleiche native RGB-Bilder wie Caption je zweimal plus6 Altvergleich;18 bitidentische Wiederholungen, "
    "Dimension1152, endlich und normiert. Beide DML-Memoryflags false. Kein Textencoder, keine Text/Bild- oder semantische Rangqualifikation. "
    "Neue Identitaet siglip_vision/onnx-dml-v2: Producer, Queryherkunft, Kandidaten, Reuse, Persistenz/Reload, Braincache, Backfill abgesichert. "
    "Alte/unbekannte Vektoren werden nicht neu etikettiert. VideoSpecialist schuetzt auch Custom-Indizes und In-memory; generische andere "
    "VectorStore-Indizes sind nicht pauschal videoidentitaetsgebunden. Alte Projektorgewichte bei Versionskonflikt unveraendert abgelehnt. "
    "Keine Migration/automatische Bestands-Neuanalyse/Neutraining; semantische Altbestandsfunktionen koennen deshalb unavailable sein. "
    "186 verschiedene gezielte Tests bestanden:108 Caption/Preprocessing/Pipeline und78 Identity/Persistenz/Vector/Brain, je6 Dependencywarnungen. "
    "23 neue Faelle (7 Preprocessing,16 Identity). Vorherfehler reproduziert, unabhaengiger Review mit Query/Nebenpfad-Findings behoben. "
    "Bestehender10ms-Cooldown-Testflake nur im Test auf kontrollierte Uhr umgestellt, Produktzeitverhalten unangetastet. "
    "Alle4 Medienserien und abschliessendeCPU-Pruefung Original/Config/erfassteDB/Recoveryhashes gleich; eigene Modelle entladen. "
    "Keine Generierung/Installation/ComfyUI-Auftragsaenderung. Kein Listener8765 am Schluss; kein Produktneustart/GUI-/volleAPI-Abnahme, "
    "keine CSharp/Aussen-HTTP-Schemaaenderung, kein Binarybuild. Aktuelle Pythonquelle echt ausgefuehrt. Lokal nicht committed/gepusht. "
    "T055-Untersuchung/T056-Reparatur im begrenzten Scope abgeschlossen. T002/G1/GesamtT045/Holdout/Qualitaet offen;5von45 "
    "urspruenglichenPaketen fertig unveraendert. Rest: semantische Referenzen, SigLIP-Qualitaet/Textencoder, Beat/Downbeat/Szenenreferenzen, "
    "Tonart/Stems/Volltrack/Langdatei/Ressourcen/GUI. Kein Alles-fertig-Claim. Masterplan current-status,plan,tasks,phase-manifests," 
    "benchmark-spec und CHANGELOG aktualisiert. Belege specs/00037-comfyui-control-center/t055-vision-2026-10-19/report.md," 
    "review.md,media-validation.json,final-validation.json,pytest-caption-final.txt,pytest-identity-final.txt. Neues KI-Hirn ersetzt Obsidian."
)

def post(endpoint, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:3000/" + endpoint, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

receipt = {"timestamp":datetime.now().astimezone().isoformat(), "text":text}
receipt["write_response"] = post("remember", {"text":text,"agentName":"Codex","kind":"pb-studio-status"})
assert receipt["write_response"].get("success"), receipt["write_response"]
receipt["text_sha256"] = hashlib.sha256(text.encode()).hexdigest()
(OUT / "ki-hirn-sync.json").write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding="utf-8")
reply = post("recall", {"frage":"PB-STUDIO T055 T056 ABSCHLUSS 2026-10-19 SigLIP onnx-dml-v2", "limit":20})
receipt["exact_readback_confirmed"] = any(
    str(item.get("id")) == str(receipt["write_response"]["id"]) and item.get("text") == text
    for item in reply.get("results", [])
)
(OUT / "ki-hirn-sync.json").write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding="utf-8")
assert receipt["exact_readback_confirmed"], "Write succeeded but exact recall not yet confirmed"
print(json.dumps({"id":receipt["write_response"]["id"],"exact_readback_confirmed":True}))
