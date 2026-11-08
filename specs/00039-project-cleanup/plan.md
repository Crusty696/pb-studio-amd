# Project cleanup Implementation Plan

**Goal:** Belegte Wegwerfartefakte entfernen und verbleibende Kandidaten klassifizieren.
**Architecture:** Einmalige lokale Inventarisierung, explizite Zielmenge, keine Linkverfolgung.
**Tech Stack:** Python 3.11, Git, Windows.
**Spec:** spec.md

## Schritte
1. Gitbestand und Prozesslage erfassen, Kandidaten inventarisieren.
2. Pytest-/Ruff-Caches, Bytecode in Quellordnern und Refactor-Testkopien entfernen.
3. Getrackte Dateien hashvergleichen; ungeklaerte Archive und Medien separat ausweisen.
4. Quellhashes und Venv-Erhalt pruefen, Bericht und Vault pflegen.

## Grenzen
Keine pauschale Loeschung von scratch, archive, Medien, Modellen, Release-Binaries oder Specs. Keine Umbenennung bestehender Nutzerpfade.
