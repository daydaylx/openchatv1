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
        
        # Finde das "Datei"-Menü und füge die Aktion dort hinzu
        file_menu = next((m for m in self.main_window.menuBar().actions() if m.text() == "&Datei"), None)
        if file_menu:
            # Füge einen Separator hinzu, um es von den Standardaktionen zu trennen
            file_menu.menu().addSeparator()
            file_menu.menu().addAction(action)
        else:
            # Fallback, falls das Menü nicht gefunden wird
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
            self.main_window.chat.add_message("user", f"Inhalt von {os.path.basename(path)}:\n\n{text}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "Fehler", f"Fehler beim Laden: {e}")
