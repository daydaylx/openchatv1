#!/bin/bash

# --- Git Upload Skript ---
# Dieses Skript automatisiert das Hinzufügen, Committen und Pushen von Änderungen.

echo "🚀 Starte den Upload-Prozess nach GitHub..."

# 1. Alle Änderungen zum Staging hinzufügen
echo "   -> Füge alle geänderten Dateien hinzu (git add .)"
git add .

# 2. Nach einer Commit-Nachricht fragen
echo -n "💬 Bitte gib eine Commit-Nachricht ein und drücke [ENTER]: "
read commit_message

# Standard-Nachricht, falls keine eingegeben wurde
if [ -z "$commit_message" ]; then
    commit_message="Regelmäßige Aktualisierung"
    echo "   -> Keine Nachricht eingegeben. Verwende Standard: '$commit_message'"
fi

# 3. Die Änderungen committen
echo "   -> Committe Änderungen mit der Nachricht: '$commit_message'"
git commit -m "$commit_message"

# 4. Die Änderungen auf GitHub pushen (zum 'main' Branch)
echo "   -> Lade Änderungen zu GitHub hoch (git push origin main)"
git push origin main

echo "✅ Prozess abgeschlossen. Deine Änderungen sind jetzt auf GitHub!"
