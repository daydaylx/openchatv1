from plugin_interface import ChatPlugin
from PySide6.QtWidgets import QAction, QMessageBox, QFileDialog
import os
import re

class ScaffoldAndWritePlugin(ChatPlugin):
    def get_name(self):
        return "Projektstruktur & Inhalte anlegen"
    def get_description(self):
        return "Legt KI-generierte Ordner, Dateien und deren Inhalte robust an."

    def __init__(self, main_window):
        super().__init__(main_window)
        action = QAction("Struktur & Inhalte anlegen", self.main_window)
        action.triggered.connect(self.run_scaffold_and_write)

        # Finde das "Datei"-Menü und füge die Aktion dort hinzu
        file_menu = next((m for m in self.main_window.menuBar().actions() if m.text() == "&Datei"), None)
        if file_menu:
            file_menu.menu().addAction(action)
        else:
            # Fallback, falls das Menü nicht gefunden wird
            self.main_window.menuBar().addAction(action)
            
    def extract_structure(self, text):
        """Extrahiert die Struktur aus Markdown-Codeblöcken oder einfachen Listen."""
        match = re.search(r"```(?:[a-zA-Z]*\n)?([\s\S]*?)```", text)
        if match:
            text = match.group(1)
        return [l.strip(" │├─") for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]

    def find_files_and_content(self, messages):
        """Findet alle Datei/Codeblöcke im Chat – erkennt viele Marker-Stile."""
        files = {}
        file_regex = re.compile(r"(?:(?:# ?(?:File|Datei):|// ?(?:File|Datei):)[ \t]*|^)([\w\-/]+\.[\w]+)\s*\n+(?:```[a-zA-Z0-9]*\n)?([\s\S]+?)(?:(?:```)|(?=\n[#/ ]{0,10}(?:File|Datei):)|\Z)", re.MULTILINE)
        for m in messages:
            for match in file_regex.finditer(m.content):
                fname, code = match.group(1).strip(), match.group(2).strip()
                if fname not in files or len(code) > len(files[fname]):
                    files[fname] = code
        return files

    def run_scaffold_and_write(self):
        root_dir = QFileDialog.getExistingDirectory(self.main_window, "Projektziel wählen")
        if not root_dir: return
        messages, errors, created, written = self.main_window.chat.messages, [], [], []
        
        struct_text = next((m.content for m in reversed(messages) if m.role == "assistant" and "/" in m.content), None)
        if struct_text:
            for entry in self.extract_structure(struct_text):
                name = entry.strip(" :"); path = os.path.join(root_dir, name)
                try:
                    if entry.endswith("/") or (not os.path.splitext(name)[1] and not name.startswith(".")):
                        os.makedirs(path, exist_ok=True); created.append(f"Ordner: {name}")
                    else:
                        if (folder := os.path.dirname(path)) and not os.path.exists(folder): os.makedirs(folder)
                        if not os.path.exists(path): open(path, "w").close(); created.append(f"Datei: {name}")
                except Exception as e: errors.append(f"{name}: {e}")

        files = self.find_files_and_content(messages)
        for fname, code in files.items():
            abspath = os.path.join(root_dir, fname)
            try:
                os.makedirs(os.path.dirname(abspath), exist_ok=True)
                overwrite = os.path.exists(abspath)
                with open(abspath, "w", encoding="utf-8") as f: f.write(code)
                written.append(f"{fname}" + (" (überschrieben)" if overwrite else ""))
            except Exception as e: errors.append(f"{fname}: {e}")
            
        summary = f"Aktion abgeschlossen:\n\n- {len(created)} Ordner/Dateien angelegt\n- {len(written)} Dateien geschrieben\n"
        if errors: summary += f"\nFehler:\n" + "\n".join(f"- {e}" for e in errors)
        QMessageBox.information(self.main_window, "Ergebnis", summary)
