import toml
from dotenv import load_dotenv
import os
from typing import List, Dict, Any

# Lade Umgebungsvariablen aus der .env-Datei (sucht automatisch nach einer .env)
load_dotenv()

class Config:
    """
    Eine Klasse, die alle Konfigurationen aus .env und config.toml kapselt.
    Attribute werden dynamisch aus den geladenen Konfigurationsdateien erstellt.
    """
    def __init__(self, config_path: str = 'config.toml'):
        # 1. Lade den API-Key aus den Umgebungsvariablen (.env)
        self.api_key: str = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key or self.api_key == "dein_api_key_hier":
            # Wir brechen ab, wenn der Schlüssel nicht gesetzt ist.
            raise ValueError("OPENROUTER_API_KEY nicht in .env gefunden oder nicht gesetzt.")

        # 2. Lade alle anderen Konfigurationen aus der TOML-Datei
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                toml_config: Dict[str, Any] = toml.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {config_path}")

        # 3. Weise die Konfigurationen als Attribute der Klasse zu
        self.api: Dict[str, Any] = toml_config.get('api', {})
        self.prompts: Dict[str, str] = toml_config.get('prompts', {})
        self.gui: Dict[str, Any] = toml_config.get('gui', {})
        self.logging: Dict[str, str] = toml_config.get('logging', {})

        # 4. Erstelle Hilfs-Attribute für den einfachen Zugriff
        self.api_base_url: str = self.api.get('base_url')
        self.default_model: str = self.api.get('default_model')
        self.available_models: List[str] = self.api.get('available_models', [])
        self.system_prompt: str = self.prompts.get('system_prompt')

# Erstelle eine globale Instanz der Konfiguration.
# Diese Instanz wird im gesamten Projekt importiert und verwendet.
config = Config()
