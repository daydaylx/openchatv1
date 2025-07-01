from abc import ABC, abstractmethod

class BasePlugin(ABC):
    """
    Abstrakte Basisklasse für alle Plugins.
    Jedes Plugin muss einen Namen definieren und eine execute-Methode implementieren.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """Der eindeutige Name des Plugins."""
        pass

    @abstractmethod
    def execute(self, text: str) -> str:
        """
        Die Hauptmethode des Plugins, die auf einen Text angewendet wird.

        Args:
            text: Der Eingabetext (z. B. eine Benutzer- oder Assistentennachricht).

        Returns:
            Der modifizierte Text.
        """
        pass
