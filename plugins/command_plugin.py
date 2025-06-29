import os
from plugin_interface import ChatPlugin
from PySide6.QtWidgets import QMessageBox

class CommandPlugin(ChatPlugin):
    """Ein einfaches Plugin zur Implementierung von Slash-Befehlen."""

    def get_name(self) -> str:
        return "Command Handler"

    def get_description(self) -> str:
        return "Verarbeitet Befehle wie /clear und /help."

    def on_user_message(self, message: str) -> bool:
        if message.lower() == "/clear":
            self.main_window.chat.clear()
            return True  # Nachricht verarbeitet

        if message.lower() == "/help":
            help_text = """
            <b>Verfügbare Befehle:</b><br>
            <ul>
                <li><code>/clear</code> - Löscht den gesamten Chatverlauf.</li>
                <li><code>/help</code> - Zeigt diese Hilfe an.</li>
            </ul>
            """
            QMessageBox.information(self.main_window, "Hilfe", help_text)
            return True # Nachricht verarbeitet

        return False # Kein Befehl erkannt
