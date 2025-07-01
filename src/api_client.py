import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import List, Dict, Optional

# Wir importieren unsere eigenen Module
from .config_loader import config
from .exceptions import APIClientError
from .logger import log

class OpenRouterClient:
    """
    Ein Client für die Interaktion mit der OpenRouter API.
    Verwaltet Authentifizierung, Anfragen, Fehlerbehandlung und Wiederholungsversuche.
    """
    def __init__(self, api_key: str, base_url: str):
        if not api_key:
            raise ValueError("API-Schlüssel darf nicht leer sein.")
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    @retry(
        stop=stop_after_attempt(3),  # Versucht es maximal 3 Mal
        wait=wait_exponential(multiplier=1, min=2, max=10),  # Wartet zwischen Versuchen länger
        reraise=True # Löst die letzte Exception aus, wenn alle Versuche fehlschlagen
    )
    def send_message(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> Optional[str]:
        """Sendet eine Nachricht an die OpenRouter Chat-Completion API."""
        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            log.debug(f"Sende Anfrage an OpenRouter: {payload}")
            # httpx ist eine moderne HTTP-Bibliothek, die requests ersetzt
            with httpx.Client() as client:
                response = client.post(endpoint, json=payload, headers=self.headers, timeout=30.0)
                response.raise_for_status()  # Löst eine HTTPError bei 4xx/5xx Antworten aus

            response_data = response.json()
            log.debug(f"Antwort von OpenRouter erhalten: {response_data}")

            if response_data.get("choices"):
                return response_data["choices"][0]["message"]["content"]
            return None

        except httpx.HTTPStatusError as e:
            log.error(f"HTTP Fehler: {e.response.status_code} - {e.response.text}")
            # Wir lösen hier unsere eigene, saubere Exception aus
            raise APIClientError(e.response.status_code, e.response.text)
        except Exception as e:
            log.error(f"Unerwarteter Fehler im API-Client: {e}")
            raise APIClientError(status_code=500, error_message=str(e))

# Globale Instanz des API-Clients, die auf unsere Konfiguration zugreift
api_client = OpenRouterClient(api_key=config.api_key, base_url=config.api_base_url)
