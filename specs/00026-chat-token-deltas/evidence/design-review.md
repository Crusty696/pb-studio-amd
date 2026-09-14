# Design Review: Chat Token Deltas (Spec 00026)

Datum: 2026-09-12

## Architekturentscheidungen
1. Streaming Token Deltas: text_delta Events werden direkt gestreamt, waehrend final_text die vollstaendige Historie abschliesst. UI dedupliziert sauber.
2. Isolierung von reasoning_content: Modell-Reasoning (<think> Blöcke o.ä.) wird strikt isoliert und fliesst nicht in die sichtbare Assistant-Antwort ein.
3. Fragmentierte Tool-Calls: Werden ueber alle Chunks hinweg akkumuliert und erst nach gueltigem Finish und Schema-Validierung ausgefuehrt.
4. Fallback-Garantie: Modell-Fallback nur ERLAUBT, BEVOR das erste Token an den Nutzer gesendet wurde. Wurde bereits Text gestreamt, bricht ein Fehler kontrolliert ab statt eine zweite Antwort anzuhaengen.
