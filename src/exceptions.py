class OpenChatException(Exception):
    """Basis-Exception für alle benutzerdefinierten Fehler in der Anwendung."""
    def __init__(self, message="Ein unerwarteter Fehler in OpenChat ist aufgetreten."):
        self.message = message
        super().__init__(self.message)

class APIClientError(OpenChatException):
    """Wird ausgelöst, wenn der API-Client einen Fehler zurückgibt."""
    def __init__(self, status_code: int, error_message: str):
        full_message = f"API-Fehler mit Statuscode {status_code}: {error_message}"
        super().__init__(full_message)
        self.status_code = status_code

class ConfigError(OpenChatException):
    """Wird ausgelöst, wenn ein Konfigurationsfehler auftritt."""
    def __init__(self, message="Fehler beim Laden der Konfiguration."):
        super().__init__(message)

class PluginError(OpenChatException):
    """Wird ausgelöst, wenn ein Fehler im Plugin-System auftritt."""
    def __init__(self, message="Fehler im Plugin-System."):
        super().__init__(message)
