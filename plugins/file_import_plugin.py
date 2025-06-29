# plugins/file_import_plugin.py

from plugin_interface import ChatPlugin
from PySide6.QtWidgets import QAction, QFileDialog, QMessageBox
import os
try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

class FileImportPlugin(ChatPlugin):
    def get_name(self):
        return "Datei Import"
    def get_description(self):
        return "Importiert .md, .txt, .py und .pdf Dateien in den Chat."
    def __init__(self, main_window):
        super().__init__(main_window)
        action = QAction("Datei-Inhalt in Chat einfügen...", self.main_window)
        action.triggered.connect(self.import_file)
        
        # --- START: GEÄNDERTER CODE ---
        # Füge die Aktion zum neuen "Plugins"-Menü hinzu
        if hasattr(self.main_window, 'm_plugins'):
            self.main_window.m_plugins.addAction(action)
        else:
            # Fallback, falls das Menü nicht existiert
            self.main_window.menuBar().addMenu("Plugins").addAction(action)
        # --- ENDE: GEÄNDERTER CODE ---

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Datei auswählen", "",
            "Erlaubte Dateien (*.txt *.md *.py *.pdf)"
        )
        if not path: return
        try:
            if path.endswith(".pdf"):
                if not PDF_AVAILABLE:
                    QMessageBox.warning(self.main_window, "PDF-Abhängigkeit fehlt", "Für PDF-Import bitte `PyPDF2` installieren: pip install PyPDF2")
                    return
                text = ""
                reader = PdfReader(path)
                for p in reader.pages:
                    text += p.extract_text() or ""
            else:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            maxlen = 8000
            if len(text) > maxlen:
                text = text[:maxlen] + "\n... (gekürzt)"
            # Fügt den Inhalt als "System"-Nachricht ein, um es klarer zu trennen
            self.main_window.chat.add_message("system", f"Inhalt von {os.path.basename(path)}:\n\n{text}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "Fehler", f"Fehler beim Laden: {e}")
