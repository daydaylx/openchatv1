from pydantic import BaseModel, Field
from typing import List, Literal

# Pydantic-Modelle sorgen für Typsicherheit und klare Datenstrukturen.

class Message(BaseModel):
    """
    Stellt eine einzelne Nachricht in der Konversation dar.
    """
    # Die Rolle ist auf diese drei Werte beschränkt, um Fehler zu vermeiden
    role: Literal["system", "user", "assistant"]
    content: str

class ChatHistory(BaseModel):
    """
    Verwaltet die gesamte Konversationshistorie intelligent.
    """
    # Stellt sicher, dass 'messages' eine Liste von Message-Objekten ist
    messages: List[Message] = Field(default_factory=list)
    max_length: int = 20 # Maximale Anzahl an Nachrichten zur Kontextbegrenzung

    def add_message(self, message: Message):
        """Fügt eine neue Nachricht zur Historie hinzu."""
        self.messages.append(message)
        # Kürzt die Historie, wenn sie die maximale Länge überschreitet
        self._trim_history()

    def _trim_history(self):
        """Interne Methode, um die Historie zu kürzen."""
        if len(self.messages) > self.max_length:
            # Behält die System-Nachricht (falls vorhanden) und die letzten Nachrichten
            system_message = self.messages[0] if self.messages and self.messages[0].role == "system" else None
            
            relevant_messages = self.messages[-self.max_length:]
            
            # Stelle sicher, dass die System-Nachricht nicht doppelt ist
            if system_message and system_message not in relevant_messages:
                self.messages = [system_message] + relevant_messages
            else:
                self.messages = relevant_messages


    def get_history_for_api(self) -> List[dict]:
        """Gibt die Historie als Liste von Dictionaries zurück (für API-Aufrufe)."""
        return [msg.model_dump() for msg in self.messages]

    def clear(self):
        """Löscht die gesamte Chathistorie."""
        self.messages.clear()
