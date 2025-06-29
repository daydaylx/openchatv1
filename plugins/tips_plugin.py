# plugins/tips_plugin.py

import random
from plugin_interface import ChatPlugin
from PySide6.QtWidgets import QLabel

# Eine Liste von hilfreichen Tipps für den Nutzer.
# Diese können einfach erweitert werden.
TIPS = [
    "Tipp: Bitten Sie die KI, Code 'Schritt für Schritt' zu erklären.",
    "Tipp: Nutzen Sie das Rechtsklick-Menü im Editor, um Code zu refaktorisieren.",
    "Tipp: Laden Sie eine Datei per 'Datei' -> 'Datei einfügen' hoch, um Kontext zu geben.",
    "Tipp: Definieren Sie ein Ausgabeformat, z.B. 'Gib die Antwort als JSON aus'.",
    "Tipp: Nutzen Sie '/clear' im Eingabefeld, um den gesamten Chat zu löschen.",
    "Tipp: Speichern Sie eine Konversation über 'Datei' -> 'Speichern...' und laden Sie sie später wieder.",
    "Tipp: Wechseln Sie das KI-Modell in den Einstellungen für andere Aufgaben (z.B. kreatives Schreiben)."
]

class TipsPlugin(ChatPlugin):
    """
    Ein einfaches Plugin, das einen zufälligen, hilfreichen Tipp
    in der Statusleiste des Hauptfensters anzeigt.
    """
    
    def get_name(self) -> str:
        """Gibt den Namen des Plugins zurück."""
        return "Tipps des Tages"

    def get_description(self) -> str:
        """Gibt eine kurze Beschreibung des Plugins zurück."""
        return "Zeigt nützliche Tipps für die Bedienung in der Statusleiste an."

    def __init__(self, main_window):
        """
        Der Konstruktor wird beim Start der Anwendung aufgerufen.
        Hier wird das UI-Element erstellt und zur Statusleiste hinzugefügt.
        """
        super().__init__(main_window)
        
        # Wähle einen zufälligen Tipp aus der Liste
        tip_text = random.choice(TIPS)
        
        # Erstelle ein Label-Widget für den Tipp
        self.tip_label = QLabel(tip_text)
        
        # Füge das Label als "permanentes Widget" zur Statusleiste hinzu.
        # Dadurch wird es rechts neben der normalen Statusanzeige ("Bereit", "Warte auf Antwort...") platziert.
        self.main_window.statusBar().addPermanentWidget(self.tip_label)
