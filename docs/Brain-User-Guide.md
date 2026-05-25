# Anwender-Leitfaden: Das „Hirn“ (AI Director & Pacing) in PB Studio

Willkommen beim Leitfaden für die semantische und rhythmische Steuerungslogik von PB Studio! Dieser Guide erklärt einfach und verständlich, wie das „Hirn“ (Z-BRAIN) hinter den Kulissen funktioniert, wie Sie es bedienen und wie Sie es optimal für Ihre DJ-Mixe nutzen.

---

## 1. Das Kernprinzip: Der AI Director
Der AI Director hat eine einzige Aufgabe: Er nimmt Ihren DJ-Mix (Audio) und wählt aus Ihrer Videobibliothek (tausende Clips) vollautomatisch diejenigen aus, die rhythmisch, energetisch und thematisch am besten zur Musik passen.

Das Herzstück dieser Auswertung basiert auf **17 Matching-Achsen**. Jede Achse bewertet einen bestimmten Aspekt der Harmonie zwischen Ton und Bild.

---

## 2. Die 17 Matching-Achsen (Brücken-Dimensionen)
Das System berechnet für jeden einzelnen Videoschnitt (Cut) eine Übereinstimmung in den folgenden Dimensionen:

### Rhythmische Achsen (Audio-Beat)
*   **Beat (Rhythmus):** Passt die Schnittfrequenz und die Bewegung im Video exakt zum Grundtakt (BPM) der Musik?
*   **Onset (Dynamik):** Werden schnelle, plötzliche Sound-Ereignisse (z. B. Percussions) durch visuelle Wechsel untermalt?
*   **Kick (Bass):** Reagiert das Video auf den dominanten Rhythmus der Bassdrum (z. B. durch optischen Fluss)?
*   **Snare / Hihat (Frequenzen):** Synchronisation mit den mittleren und hohen Perkussions-Elementen.

### Energetische Achsen
*   **Energy (Energieverlauf):** Folgt die visuelle Hektik (schnelle Schnitte, viel Bewegung) der gemessenen Lautstärke und Dichte der Musik?
*   **Pace Match (Geschwindigkeit):** Synchronisation der generellen Schnittfrequenz mit der Geschwindigkeit des Songs.

### Visuelle & Ästhetische Achsen
*   **Motion (Bewegung):** Entspricht der optische Fluss (Kamerabewegungen, fließende Objekte) dem emotionalen Fluss der Musik?
*   **Scene Cuts (Schnittfrequenz):** Vermeidung von unnatürlichen Schnitten mitten im Musik-Takt.
*   **Brightness (Helligkeit) & Color Temp (Farbtemperatur):** Entspricht die visuelle Stimmung (helle/dunkle Bilder, kalte/warme Farben) der spektralen Dichte des Audios.

### Semantische & Stimmungs-Achsen
*   **Semantic Match (Thema):** Passt der Bildinhalt (z. B. "Strand bei Sonnenuntergang", erkannt durch das CLIP-Modell) zur Stimmung des Songs?
*   **Mood Match (Stimmung):** Abgleich der emotionalen Stimmung (z. B. düster, fröhlich, treibend) zwischen Bild und Ton.

---

## 3. Das interaktive Lernen: Der Beta-Bernoulli-Bandit
Das „Hirn“ von PB Studio ist nicht starr – es lernt aktiv von Ihnen! Jedes Mal, wenn Sie im **Scene Editor** oder auf der **Timeline** mit den Cuts interagieren, trainieren Sie das neuronale Matching-Modell:

### Wie Sie dem Hirn Feedback geben:
1.  **Gefällt mir (Positive Verstärkung):** Wenn Sie einen Cut oder ein bestimmtes Pacing gut finden, bestätigen Sie dies in der UI.
2.  **Cut verschieben / Clip austauschen (Negative Verstärkung):** Wenn Sie einen Clip manuell austauschen oder beschneiden, interpretiert das Backend dies als Korrektursignal.

### Was im Hintergrund passiert (Die Bernoulli-Logik):
*   Jede der 17 Achsen besitzt ein dynamisches Gewicht (Wahrscheinlichkeitsverteilung).
*   Geben Sie **positives Feedback**, steigen die Gewichte der dominierenden Achsen für diesen Musikkontext (z. B. *„In deepen House-Passagen gefällt mir Farbtemperatur-Matching am besten“*).
*   Geben Sie **negatives Feedback**, sinkt der Einfluss dieser Achsen für diesen Kontext.
*   Mit jedem Mix, den Sie erstellen, passt sich der AI Director immer präziser Ihrem persönlichen Geschmack an.

---

## 4. Bedienung bei Offline-KI (LLM-Offline-Modus)
Um Ihnen jederzeit maximale Transparenz zu bieten, verfügt PB Studio über ein **Ausfallsicherungs-System**:
*   Wenn Sie in der Timeline über den Confidence-Balken eines Clips hovern, erzeugt die App normalerweise eine natürliche KI-Erklärung (*„Dieser Clip wurde gewählt, da das Meeresrauschen perfekt zur ruhigen Ambient-Passage passt...“*).
*   **Falls LM Studio oder Ollama offline sind**, stürzt die App nicht ab. Das „Hirn“ schaltet autonom in den **Offline-Narrator-Modus** und zeigt Ihnen eine direkte mathematische Aufbereitung der zwei stärksten Matching-Achsen (z. B. *„Ausgewählt wegen hoher Übereinstimmung in: Rhythmus-Synchronität (Beat) und Energieverlauf“*).

So haben Sie jederzeit die volle Kontrolle und Transparenz über die Entscheidungen des AI Directors!
