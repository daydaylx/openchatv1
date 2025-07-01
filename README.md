# OpenChat v2

Dies ist eine vollständig refaktorisierte und modernisierte Version des OpenChat-Projekts. Die Anwendung bietet eine Weboberfläche für die Interaktion mit verschiedenen LLMs über die OpenRouter-API.

## ✨ Features

- **Modulare Struktur**: Der Code ist sauber in `src`, `plugins`, `tests` und `assets` unterteilt.
- **Zentralisierte Konfiguration**: Alle Einstellungen werden über `config.toml` und `.env` verwaltet.
- **Robustes Logging**: Ein zentraler Logger ersetzt `print`-Anweisungen und schreibt in Konsole und Datei.
- **Sicherer API-Client**: Ein dedizierter API-Client mit Fehlerbehandlung und automatischen Wiederholungsversuchen.
- **Erweiterbar durch Plugins**: Ein einfaches, aber leistungsstarkes Plugin-System.
- **Sauberes Fehlerhandling**: Benutzerdefinierte Exceptions für eine klare Fehlerverfolgung.

## 🚀 Installation

1.  **Klone das Repository** (oder lade die Dateien herunter):
    ```bash
    git clone [https://github.com/DEIN_BENUTZERNAME/openchatv2.git](https://github.com/DEIN_BENUTZERNAME/openchatv2.git)
    cd openchatv2
    ```

2.  **Erstelle eine virtuelle Umgebung und aktiviere sie**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Auf Linux/macOS
    # venv\Scripts\activate    # Auf Windows
    ```

3.  **Installiere die Abhängigkeiten**:
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Konfiguration

1.  Benenne die Datei `.env.example` in `.env` um oder erstelle eine neue `.env`-Datei.
2.  Trage deinen OpenRouter API-Schlüssel in die `.env`-Datei ein:
    ```
    OPENROUTER_API_KEY="dein_api_key_hier"
    ```
3.  Passe bei Bedarf die Einstellungen in `config.toml` an (z.B. Standardmodell, GUI-Titel).

## ▶️ Anwendung starten

Führe den folgenden Befehl im Hauptverzeichnis aus:

```bash
python main_app.py
