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
        action = QAction("Datei einfügen", self.main_window)
        action.triggered.connect(self.import_file)
        self.main_window.menuBar().addAction(action)
    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Datei auswählen", "",
            "Erlaubte Dateien (*.txt *.md *.py *.pdf)"
        )
        if not path: return
        try:
            if path.endswith(".pdf"):
                if not PDF_AVAILABLE:
                    QMessageBox.warning(self.main_window, "PDF", "PyPDF2 nicht installiert.")
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
            self.main_window.chat.add_message("user", f"Inhalt von {os.path.basename(path)}:\n\n{text}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "Fehler", f"Fehler beim Laden: {e}")

