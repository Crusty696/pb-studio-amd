# Scene Ground Truth — 2026-08-11

## Korpus

Im Bestand gab es kein Fixture mit unabhängig bekannten exakten Schnittgrenzen.
Deshalb wurden sechs GUID-isolierte, temporäre 3-Sekunden-Fixtures mit dem
kanonischen `h264_amf`-Encoder erzeugt; Produktmedien und Projektdaten blieben
unverändert.

- Drei kontinuierliche Clips: Ground Truth `[(0.0, 3.0)]`.
- Drei Hard-Cut-Clips: Ground Truth `[(0, 1), (1, 2), (2, 3)]`.
- Temporärer Root (privater Präfix redigiert):
  `<TEMP>\pb_obj76_scene_6f2d1ec931354bb1b8b59f0056cc6a45`.
- SHA-256 kontinuierlich:
  `3774840059a20fedae36f49bdf1ef7c416d5ad14b38b1985af683e5835a96a91`,
  `17867ab10be6801a48633382e9873c66dc02d3893beb6bd9bcc2aaa24844e3fa`,
  `cdfbbda243018f937802e65f9cb981a917943f0d780f0460e0702e0aab6805be`.
- SHA-256 Hard-Cut:
  `0020176fc59fc59f8615feb0f5ba6a3daa5840c8fa6ee3bbd3f62698b5e4a072`,
  `80b7306f12cf0c5f47ca856d91cbeb8572e756ce40fc1ac507d883af77f5475f`,
  `25deb57ff2a5679f7b1fd0290dcc566b37f5856f1cbcd84d1d3bf516f73643f1`.

## Ergebnis

- Reale Funktion: `backend.routers.video_router._run_scene_detection(..., True)`.
- Jeder Clip wurde zweimal analysiert: 12/12 Stage-Receipts
  `scenes:completed`.
- Kontinuierlich: zweimal je `[(0.0, 3.0)]`.
- Hard-Cut: zweimal je `[(0, 1), (1, 2), (2, 3)]`.
- Toleranz: 0,1 s; 6/6 Ground-Truth-Vergleiche exakt und wiederholbar.
- Entscheidung: keine False-Negatives, keine Threshold-Änderung. T017 bestanden.
