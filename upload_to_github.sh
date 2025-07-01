#!/bin/bash

# --- Git Upload Skript (Sichere Version) ---
# Lädt Änderungen zum 'v2' Branch hoch.

echo "🚀 Starte den Upload-Prozess zum 'v2' Branch..."

# ... (der Rest des Skripts bleibt gleich) ...

echo "   -> Füge alle geänderten Dateien hinzu (git add .)"
git add .

echo -n "💬 Bitte gib eine Commit-Nachricht ein und drücke [ENTER]: "
read commit_message

if [ -z "$commit_message" ]; then
    commit_message="Update auf dem v2 Branch"
    echo "   -> Keine Nachricht eingegeben. Verwende Standard: '$commit_message'"
fi

git commit -m "$commit_message"

# --- GEÄNDERTE ZEILE ---
echo "   -> Lade Änderungen zu GitHub hoch (git push origin v2)"
git push origin v2

echo "✅ Prozess abgeschlossen."
