import os
from datetime import datetime
from plugin_interface import ChatPlugin

class AutoSavePlugin(ChatPlugin):
    """
    Ein Plugin, das alle Codeblöcke aus KI-Antworten
    automatisch in einem Unterordner speichert.
    """

    def get_name(self) -> str:
        return "Auto-Saver für Code"

    def get_description(self) -> str:
        return "Speichert Python-Codeblöcke aus KI-Antworten automatisch."

    def on_api_response(self, response: str):
        # Einfache Suche nach Python-Codeblöcken
        if "```python" in response:
            try:
                # Extrahiere den Code zwischen den Markern
                code_block = response.split("```python")[1].split("```")[0].strip()
                
                # Erstelle Speicherordner, falls nicht vorhanden
                save_dir = "gespeicherter_code"
                os.makedirs(save_dir, exist_ok=True)
                
                # Generiere einen eindeutigen Dateinamen
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(save_dir, f"code_{timestamp}.py")
                
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(code_block)
                
                # Status-Update im Hauptfenster
                self.main_window.lbl_status.setText(f"Codeblock in '{filename}' gespeichert.")

            except Exception as e:
                print(f"Fehler im AutoSavePlugin: {e}")
