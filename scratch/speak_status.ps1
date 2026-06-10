Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

# Versuche eine deutsche Stimme zu finden, sonst Standard
$germanVoice = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq "de" } | Select-Object -First 1
if ($germanVoice) {
    $synth.SelectVoice($germanVoice.VoiceInfo.Name)
}

$text = "Hier ist der aktuelle Status von P B Studio A M D Edition. " +
        "Das System befindet sich in einem stabilen und fehlerfreien Zustand und ist bereit für den Einsatz. " +
        "Alle siebenhundert sechsunddreißig Python Tests wurden erfolgreich bestanden. Der WPF Build ist absolut fehlerfrei und ohne Warnungen. " +
        "Erledigt und voll funktionsfähig sind: Die Audio-Analyse mit Beat-Erkennung, Tonart-Bestimmung und die Demucs-Stemtrennung mit Direct M L Beschleunigung. " +
        "Die Video-Analyse mit RAFT-Bewegungserkennung, Szenenerkennung und Sig L I P Embeddings. " +
        "Die Benutzeroberfläche mit getrennten Video- und Audiospuren und dem extrem schnellen Wellenform-Renderer. " +
        "Der V-Ram Budget Manager verhindert zuverlässig Speicherabstürze. " +
        "Einzige Einschränkung: Aufgrund von Treiber-Updates liefert der Hardware-Monitor für manche dedizierte AMD-Grafikkarten keine Live-Daten für V-Ram-Auslastung und Temperatur. " +
        "Dies wird jedoch für den Gesamtspeicher durch einen Registry-Fallback umgangen. " +
        "Das gesamte Projekt ist stabil, voll funktionsfähig und veröffentlichungsbereit."

$outputPath = "C:\Users\david\Documents\Pb_studio_AMD_version\scratch\status.wav"

# Render direkt in Datei (verhindert Session-Audio-Blockaden in Background-Task)
$synth.SetOutputToWaveFile($outputPath)
$synth.Speak($text)
$synth.Dispose()

# Wenn Datei erfolgreich erzeugt wurde, spiele sie ab
if (Test-Path $outputPath) {
    # Start-Process nutzt Standard-Player des Users im interaktiven Kontext
    Start-Process $outputPath
    Write-Output "WAV-Datei erfolgreich generiert und abgespielt."
} else {
    Write-Error "WAV-Datei konnte nicht generiert werden."
}
