from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Dict
from datetime import datetime

# Verhindert zirkuläre Imports, ermöglicht aber Type-Hinting für das Hauptfenster
if TYPE_CHECKING:
    from openchat_with_plugins import MainWindow


# =====================================================================
# <<< NEU >>>
# Die Message-Klasse wird hier zentral definiert, damit alle
# Teile der Anwendung (Kern und Plugins) sie von hier importieren können.
# =====================================================================
class Message:
    def __init__(self, role: str, content: str, timestamp: Optional[datetime] = None):
        self.role, self.content = role, content
        self.timestamp = timestamp or datetime.now()
        # 'text' oder 'html'. Plugins können dies ändern, um die Darstellung zu steuern.
        self.display_format = "text"

    def to_dict(self) -> Dict:
        """Konvertiert die Nachricht in ein Dictionary für die Speicherung."""
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp.isoformat()}


# =====================================================================
# Die Plugin-Basisklasse bleibt wie zuvor.
# =====================================================================
class ChatPlugin(ABC):
    """
    Abstrakte Basisklasse für alle Chat-Plugins.
    Jedes Plugin muss von dieser Klasse erben.
    """

    def __init__(self, main_window: 'MainWindow'):
        """
        Der Konstruktor erhält eine Referenz auf das Hauptfenster,
        um auf die UI und andere Komponenten zugreifen zu können.
        """
        self.main_window = main_window

    @abstractmethod
    def get_name(self) -> str:
        """Gibt den Namen des Plugins zurück."""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Gibt eine kurze Beschreibung des Plugins zurück."""
        pass

    def on_user_message(self, message: str) -> bool:
        """
        Hook, der aufgerufen wird, bevor eine Nachricht gesendet wird.
        Wenn das Plugin die Nachricht verarbeitet (z.B. ein Befehl),
        sollte es True zurückgeben, um die weitere Verarbeitung (API-Call) zu stoppen.
        
        :param message: Die rohe Texteingabe des Benutzers.
        :return: True, wenn die Nachricht verarbeitet wurde, sonst False.
        """
        return False

    def on_api_response(self, message_object: "Message"):
        """
        Hook, der aufgerufen wird, nachdem eine vollständige Antwort von der KI empfangen wurde.
        Das Plugin kann das Message-Objekt direkt modifizieren.
        
        :param message_object: Das Message-Objekt der KI-Antwort.
        """
        pass
